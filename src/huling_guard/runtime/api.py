from __future__ import annotations

from collections import Counter, deque
import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from huling_guard.data.pose_io import normalize_pose_coords
from huling_guard.runtime.archive_store import RuntimeArchiveStore
from huling_guard.runtime.pipeline import PipelineSnapshot, RealtimePipeline
from huling_guard.runtime.session_report import (
    build_session_report,
    format_session_report_markdown,
)


class PoseFrameRequest(BaseModel):
    timestamp: float = Field(..., description="Frame timestamp in seconds.")
    keypoints: list[list[float]] = Field(
        ...,
        description="Single-person 17x3 keypoint array in [x, y, confidence] format.",
    )
    frame_width: float | None = Field(
        default=None,
        description="Optional source frame width used to normalize pixel coordinates.",
    )
    frame_height: float | None = Field(
        default=None,
        description="Optional source frame height used to normalize pixel coordinates.",
    )


def _empty_snapshot() -> PipelineSnapshot:
    return PipelineSnapshot(
        timestamp=0.0,
        ready=False,
        observed_frames=0,
        window_size=0,
        window_span_seconds=0.0,
    )


def _load_dashboard_html() -> str:
    path = Path(__file__).with_name("dashboard.html")
    return path.read_text(encoding="utf-8")


def _resolve_frontend_dist_root(frontend_dist_root: str | Path | None) -> Path | None:
    if frontend_dist_root is None:
        return None
    root = Path(frontend_dist_root).resolve()
    index_path = root / "index.html"
    if not root.is_dir() or not index_path.is_file():
        return None
    return root


def _default_system_profile(
    *,
    pipeline: RealtimePipeline,
    archive_enabled: bool,
) -> dict[str, object]:
    thresholds = pipeline.event_engine.thresholds
    return {
        "product_name": "护龄智守",
        "product_tagline": "单房间固定摄像头安全值守系统",
        "target_users": ["家庭看护者", "护理值班人员", "机构管理人员"],
        "operational_goals": [
            "持续判断当前人员是否处于安全状态",
            "在风险出现时给出明确处置提示",
            "保存历史记录，支持追溯、复核和留档",
        ],
        "detectable_states": [
            {"code": "normal", "label": "正常活动"},
            {"code": "near_fall", "label": "高风险失衡"},
            {"code": "fall", "label": "跌倒"},
            {"code": "recovery", "label": "恢复起身"},
            {"code": "prolonged_lying", "label": "长时间卧倒"},
        ],
        "system_modules": [
            {
                "name": "姿态感知",
                "summary": "RTMO 负责逐帧人体姿态估计，输出 17 点骨架和关键点置信度。",
            },
            {
                "name": "时序理解",
                "summary": "Scene-Pose Temporal Net 结合骨架序列、运动学变化和场景关系判断当前状态。",
            },
            {
                "name": "房间先验",
                "summary": "Grounding DINO 与 SAM 2 仅用于离线房间区域初始化，不进入实时推理链路。",
            },
            {
                "name": "事件引擎",
                "summary": "EventEngine 将连续状态流稳定为预警、跌倒、长卧和恢复事件。",
            },
            {
                "name": "运行平台",
                "summary": "FastAPI 提供接口服务，SQLite 负责会话归档，Docker 用于部署封装。",
            },
        ],
        "runtime_profile": {
            "device": str(pipeline.device),
            "window_size": pipeline.window_size,
            "inference_stride": pipeline.inference_stride,
            "kinematic_feature_set": pipeline.kinematic_feature_set,
            "scene_prior_loaded": pipeline.scene_prior is not None,
            "archive_enabled": archive_enabled,
        },
        "thresholds": {
            "near_fall": thresholds.near_fall_threshold,
            "fall": thresholds.fall_threshold,
            "recovery": thresholds.recovery_threshold,
            "prolonged_lying": thresholds.prolonged_lying_threshold,
            "prolonged_lying_seconds": thresholds.prolonged_lying_seconds,
        },
    }


def _build_runtime_session_report(
    *,
    snapshot_history: deque[dict[str, object]],
    incident_history: deque[dict[str, object]],
    limit: int,
) -> dict[str, object]:
    snapshots = list(snapshot_history)[-limit:]
    incidents = list(reversed(incident_history))
    return build_session_report(
        snapshots=snapshots,
        incidents=incidents,
        session_name="runtime_live",
        source_path="runtime://live",
    )


def _list_demo_videos(root: Path | None) -> list[dict[str, object]]:
    if root is None or not root.is_dir():
        return []
    items: list[dict[str, object]] = []
    for path in sorted(root.glob("*.mp4")):
        report_path = root.parent / "reports" / "sessions" / f"{path.stem}.json"
        items.append(
            {
                "name": path.stem,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "url": f"/demo-videos/{path.name}",
                "has_session_report": report_path.is_file(),
            }
        )
    return items


def _load_demo_session_payload(root: Path | None, stem: str, limit: int = 180) -> dict[str, object]:
    if root is None or not root.is_dir():
        raise FileNotFoundError("demo video root is not enabled")
    report_path = root.parent / "reports" / "sessions" / f"{stem}.json"
    prediction_path = root.parent / "predictions" / f"{stem}.jsonl"
    if not report_path.is_file():
        raise FileNotFoundError(f"demo session report not found: {stem}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    timeline_items: list[dict[str, object]] = []
    if prediction_path.is_file():
        for line in prediction_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            timeline_items.append(
                {
                    "timestamp": payload.get("timestamp", 0.0),
                    "predicted_state": payload.get("predicted_state"),
                    "risk_score": payload.get("risk_score", 0.0),
                    "confidence": payload.get("confidence", 0.0),
                }
            )
    if limit > 0:
        timeline_items = timeline_items[-limit:]
    return {
        "name": stem,
        "session_report": report,
        "timeline": {"count": len(timeline_items), "items": timeline_items},
    }


def create_runtime_app(
    pipeline: RealtimePipeline,
    incident_history_size: int = 512,
    snapshot_history_size: int = 2048,
    archive_root: str | Path | None = None,
    demo_video_root: str | Path | None = None,
    frontend_dist_root: str | Path | None = None,
    system_profile: dict[str, object] | None = None,
) -> FastAPI:
    app = FastAPI(title="HuLing Guard Runtime API", version="0.1.0")
    incident_history: deque[dict[str, object]] = deque(maxlen=incident_history_size)
    snapshot_history: deque[dict[str, object]] = deque(maxlen=snapshot_history_size)
    incident_counts: Counter[str] = Counter()
    last_snapshot: PipelineSnapshot = _empty_snapshot()
    resolved_frontend_dist_root = _resolve_frontend_dist_root(frontend_dist_root)
    dashboard_html = (
        (resolved_frontend_dist_root / "index.html").read_text(encoding="utf-8")
        if resolved_frontend_dist_root is not None
        else _load_dashboard_html()
    )
    archive_store = RuntimeArchiveStore(archive_root) if archive_root is not None else None
    resolved_demo_video_root = Path(demo_video_root).resolve() if demo_video_root is not None else None
    profile_payload = system_profile or _default_system_profile(
        pipeline=pipeline,
        archive_enabled=archive_store is not None,
    )

    if resolved_frontend_dist_root is not None:
        assets_root = resolved_frontend_dist_root / "assets"
        if assets_root.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_root), name="runtime-dashboard-assets")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "window_size": pipeline.window_size, "inference_stride": pipeline.inference_stride}

    @app.get("/meta")
    def meta() -> dict[str, object]:
        thresholds = pipeline.event_engine.thresholds
        return {
            "title": "护龄智守",
            "window_size": pipeline.window_size,
            "inference_stride": pipeline.inference_stride,
            "device": str(pipeline.device),
            "kinematic_feature_set": pipeline.kinematic_feature_set,
            "scene_prior_loaded": pipeline.scene_prior is not None,
            "archive_enabled": archive_store is not None,
            "archive_backend": "sqlite" if archive_store is not None else None,
            "thresholds": {
                "near_fall": thresholds.near_fall_threshold,
                "fall": thresholds.fall_threshold,
                "recovery": thresholds.recovery_threshold,
                "prolonged_lying": thresholds.prolonged_lying_threshold,
                "prolonged_lying_seconds": thresholds.prolonged_lying_seconds,
                "warning_cooldown_seconds": thresholds.warning_cooldown_seconds,
            },
        }

    @app.get("/system-profile")
    def system_profile_endpoint() -> dict[str, object]:
        return profile_payload

    @app.get("/summary")
    def summary() -> dict[str, object]:
        return {
            "ready": last_snapshot.ready,
            "observed_frames": last_snapshot.observed_frames,
            "predicted_state": last_snapshot.predicted_state,
            "risk_score": last_snapshot.risk_score,
            "confidence": last_snapshot.confidence,
            "incident_total": int(sum(incident_counts.values())),
            "incident_counts": dict(incident_counts),
            "last_incident": incident_history[0] if incident_history else None,
            "timeline_points": len(snapshot_history),
        }

    @app.get("/timeline")
    def timeline(limit: int = Query(default=120, ge=1, le=snapshot_history_size)) -> dict[str, object]:
        items = list(snapshot_history)[-limit:]
        return {"count": len(items), "items": items}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(dashboard_html)

    @app.get("/demo-videos")
    def demo_videos() -> dict[str, object]:
        items = _list_demo_videos(resolved_demo_video_root)
        return {
            "enabled": resolved_demo_video_root is not None,
            "root": str(resolved_demo_video_root) if resolved_demo_video_root is not None else None,
            "count": len(items),
            "items": items,
        }

    @app.get("/demo-videos/{filename}")
    def demo_video_file(filename: str) -> FileResponse:
        if resolved_demo_video_root is None:
            raise HTTPException(status_code=404, detail="demo video root is not enabled")
        normalized = Path(filename).name
        if normalized != filename:
            raise HTTPException(status_code=400, detail="invalid demo video filename")
        path = (resolved_demo_video_root / normalized).resolve()
        try:
            path.relative_to(resolved_demo_video_root)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid demo video path") from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"demo video not found: {filename}")
        return FileResponse(path)

    @app.get("/demo-sessions/{filename}")
    def demo_session_payload(filename: str, limit: int = Query(default=180, ge=1, le=2048)) -> dict[str, object]:
        normalized = Path(filename).name
        if normalized != filename:
            raise HTTPException(status_code=400, detail="invalid demo session filename")
        stem = Path(normalized).stem
        try:
            return _load_demo_session_payload(resolved_demo_video_root, stem=stem, limit=limit)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/session-report")
    def session_report(limit: int = Query(default=512, ge=1, le=snapshot_history_size)) -> dict[str, object]:
        return _build_runtime_session_report(
            snapshot_history=snapshot_history,
            incident_history=incident_history,
            limit=limit,
        )

    @app.get("/session-report.md", response_class=PlainTextResponse)
    def session_report_markdown(limit: int = Query(default=512, ge=1, le=snapshot_history_size)) -> PlainTextResponse:
        report = _build_runtime_session_report(
            snapshot_history=snapshot_history,
            incident_history=incident_history,
            limit=limit,
        )
        return PlainTextResponse(format_session_report_markdown(report))

    @app.post("/archive-session")
    def archive_session(limit: int = Query(default=512, ge=1, le=snapshot_history_size)) -> dict[str, object]:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        report = _build_runtime_session_report(
            snapshot_history=snapshot_history,
            incident_history=incident_history,
            limit=limit,
        )
        record = archive_store.archive_report(report)
        return {"status": "archived", "record": record}

    @app.get("/archives")
    def list_archives(
        limit: int = Query(default=20, ge=1, le=200),
        dominant_state: str | None = Query(default=None),
        incidents_only: bool = Query(default=False),
    ) -> dict[str, object]:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        items = archive_store.list_archives(
            limit=limit,
            dominant_state=dominant_state,
            incidents_only=incidents_only,
        )
        return {"count": len(items), "items": items}

    @app.get("/archives/summary")
    def archive_summary() -> dict[str, object]:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        return archive_store.summarize_archives()

    @app.get("/archives/{session_id}")
    def get_archive(session_id: str) -> dict[str, object]:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        try:
            return archive_store.load_archive_report(session_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=f"archive not found: {session_id}") from error

    @app.get("/archives/{session_id}/markdown", response_class=PlainTextResponse)
    def get_archive_markdown(session_id: str) -> PlainTextResponse:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        try:
            return PlainTextResponse(archive_store.load_archive_markdown(session_id))
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=f"archive not found: {session_id}") from error

    @app.post("/pose-frame")
    def push_pose_frame(payload: PoseFrameRequest) -> dict[str, object]:
        nonlocal last_snapshot
        keypoints = np.asarray(payload.keypoints, dtype=np.float32)
        if keypoints.shape != (17, 3):
            raise HTTPException(status_code=400, detail=f"expected keypoints shape (17, 3), got {tuple(keypoints.shape)}")
        keypoints = normalize_pose_coords(
            keypoints,
            frame_width=payload.frame_width,
            frame_height=payload.frame_height,
        )
        last_snapshot = pipeline.push_pose(keypoints=keypoints, timestamp=payload.timestamp)
        snapshot_history.append(last_snapshot.to_dict())
        for incident in last_snapshot.incidents:
            incident_payload = incident.to_dict()
            incident_history.appendleft(incident_payload)
            incident_counts[str(incident.kind)] += 1
        return last_snapshot.to_dict()

    @app.get("/state")
    def get_state() -> dict[str, object]:
        return last_snapshot.to_dict()

    @app.get("/incidents")
    def get_incidents(limit: int = Query(default=50, ge=1, le=incident_history_size)) -> dict[str, object]:
        incidents = list(incident_history)[:limit]
        return {"count": len(incidents), "items": incidents}

    @app.post("/reset")
    def reset_runtime() -> dict[str, object]:
        nonlocal last_snapshot
        pipeline.reset()
        incident_history.clear()
        snapshot_history.clear()
        incident_counts.clear()
        last_snapshot = _empty_snapshot()
        return {"status": "reset"}

    return app
