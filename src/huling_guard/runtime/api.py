from __future__ import annotations

from collections import Counter, deque
from collections.abc import Callable
import json
from pathlib import Path
import re
import shutil
import threading
import time
from uuid import uuid4

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from huling_guard.data.pose_io import normalize_pose_coords
from huling_guard.runtime.archive_store import RuntimeArchiveStore
from huling_guard.runtime.pipeline import PipelineSnapshot, RealtimePipeline
from huling_guard.runtime.rtmo import RTMOPoseEstimator
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


class LiveIngestStartRequest(BaseModel):
    source: str = Field(..., description="RTSP 地址、设备编号或本地视频路径。")
    source_label: str | None = Field(default=None, description="前端显示名称。")
    rtmo_device: str | None = Field(default=None, description="RTMO 推理设备，默认沿用运行时设备。")
    frame_stride: int = Field(default=1, ge=1, le=8)
    preview_stride: int = Field(default=4, ge=1, le=24)
    score_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    loop: bool = Field(default=False, description="视频文件播完后是否循环继续。")


class ArchiveSessionRequest(BaseModel):
    demo_filename: str | None = Field(default=None, description="当前选中的演示或上传视频文件名。")


def _empty_snapshot() -> PipelineSnapshot:
    return PipelineSnapshot(
        timestamp=0.0,
        ready=False,
        observed_frames=0,
        window_size=0,
        window_span_seconds=0.0,
    )


def _missing_frontend_html() -> str:
    return """<!doctype html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>护龄智守</title>
    <style>
      :root { color-scheme: dark; }
      body { margin: 0; font-family: Aptos, Segoe UI, Noto Sans SC, Microsoft YaHei, sans-serif; background: #050b13; color: rgba(241,247,252,.94); }
      main { min-height: 100vh; display: grid; place-items: center; padding: 32px; }
      section { width: min(100%, 640px); padding: 32px; border-radius: 18px; background: rgba(10,18,30,.76); box-shadow: inset 0 0 0 1px rgba(120,146,176,.12); }
      h1 { margin: 0 0 12px; font-size: 28px; }
      p { margin: 0; color: rgba(214,225,237,.74); line-height: 1.7; }
      code { color: #79d4e7; }
    </style>
  </head>
  <body>
    <main>
      <section>
        <h1>前端发布包缺失</h1>
        <p>当前运行时只以 Vue 前端发布包作为唯一界面来源。请先构建并挂载 <code>frontend/dist</code>，再访问 <code>/dashboard</code>。</p>
      </section>
    </main>
  </body>
</html>"""


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
        "quality_controls": [
            "运行时持续监测骨架质量分数、关键点平均置信度和可见关节比例",
            "训练与运行统一使用归一化骨架坐标，避免离线评估与在线推理口径漂移",
            "状态阈值必须基于独立验证视频校准，不能直接沿用训练阶段的经验值",
        ],
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
    poster_root = root.parent / "posters"
    annotated_root = _annotated_videos_root(root)
    for path in sorted(root.glob("*.mp4")):
        report_path = root.parent / "reports" / "sessions" / f"{path.stem}.json"
        metadata = _load_upload_metadata(root, path.stem)
        annotated_path = annotated_root / f"{path.stem}.mp4"
        poster_path = None
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = poster_root / f"{path.stem}{suffix}"
            if candidate.is_file():
                poster_path = candidate
                break
        items.append(
            {
                "name": path.stem,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "url": f"/demo-videos/{path.name}",
                "annotated_url": f"/demo-annotated/{annotated_path.name}" if annotated_path.is_file() else None,
                "poster_url": f"/demo-posters/{poster_path.name}" if poster_path is not None else None,
                "has_session_report": report_path.is_file(),
                "source_kind": str(metadata.get("source_kind") or "demo"),
                "processing_status": str(metadata.get("processing_status") or "ready"),
                "original_name": metadata.get("original_name"),
                "error_message": metadata.get("error_message"),
                "processed_frames": metadata.get("processed_frames"),
                "total_frames": metadata.get("total_frames"),
            }
        )
    return items


def _annotated_videos_root(demo_root: Path) -> Path:
    return demo_root.parent / "annotated"


def _upload_jobs_root(demo_root: Path) -> Path:
    return demo_root.parent / "uploads" / "jobs"


def _upload_metadata_path(demo_root: Path, stem: str) -> Path:
    return _upload_jobs_root(demo_root) / f"{stem}.json"


def _load_upload_metadata(demo_root: Path, stem: str) -> dict[str, object]:
    path = _upload_metadata_path(demo_root, stem)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_upload_metadata(demo_root: Path, stem: str, payload: dict[str, object]) -> dict[str, object]:
    path = _upload_metadata_path(demo_root, stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _delete_upload_artifacts(demo_root: Path, stem: str) -> list[Path]:
    if not stem.startswith("upload_"):
        raise ValueError("only uploaded videos can be deleted")

    removed: list[Path] = []
    candidates = [
        demo_root / f"{stem}.mp4",
        _annotated_videos_root(demo_root) / f"{stem}.mp4",
        demo_root.parent / "predictions" / f"{stem}.jsonl",
        demo_root.parent / "reports" / "sessions" / f"{stem}.json",
        demo_root.parent / "reports" / "markdown" / f"{stem}.md",
        demo_root.parent / "posters" / f"{stem}.jpg",
        _upload_metadata_path(demo_root, stem),
    ]
    for path in candidates:
        try:
            if path.exists():
                path.unlink()
                removed.append(path)
        except Exception:
            continue
    return removed


def _sanitize_upload_name(filename: str) -> str:
    stem = Path(filename).stem.strip().lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return stem or "video"


def _load_demo_session_payload(root: Path | None, stem: str, limit: int = 180) -> dict[str, object]:
    if root is None or not root.is_dir():
        raise FileNotFoundError("demo video root is not enabled")
    report_path = root.parent / "reports" / "sessions" / f"{stem}.json"
    prediction_path = root.parent / "predictions" / f"{stem}.jsonl"
    if not report_path.is_file() and not prediction_path.is_file():
        raise FileNotFoundError(f"demo session report not found: {stem}")

    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    full_timeline_items: list[dict[str, object]] = []
    if prediction_path.is_file():
        for line in prediction_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            full_timeline_items.append(
                {
                    "timestamp": payload.get("timestamp", 0.0),
                    "ready": payload.get("ready", False),
                    "predicted_state": payload.get("predicted_state"),
                    "state_probs": payload.get("state_probs") or {},
                    "risk_score": payload.get("risk_score", 0.0),
                    "confidence": payload.get("confidence", 0.0),
                    "incidents": payload.get("incidents") or [],
                }
            )
    if report is None:
        report = build_session_report(
            snapshots=full_timeline_items,
            session_name=stem,
            source_path=str((root / f"{stem}.mp4").resolve()),
        )
    timeline_items = full_timeline_items
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
    upload_pipeline_factory: Callable[[], RealtimePipeline] | None = None,
    upload_rtmo_device: str = "cpu",
    ingest_runtime_url: str | None = None,
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
        else _missing_frontend_html()
    )
    archive_store = RuntimeArchiveStore(archive_root) if archive_root is not None else None
    active_upload_jobs: set[str] = set()
    active_upload_jobs_lock = threading.Lock()
    resolved_demo_video_root = Path(demo_video_root).resolve() if demo_video_root is not None else None
    live_preview: dict[str, object] = {
        "bytes": None,
        "content_type": "image/jpeg",
        "source": None,
        "source_label": None,
        "timestamp": None,
        "frame_width": None,
        "frame_height": None,
        "annotated": False,
        "updated_at": None,
    }
    live_ingest_lock = threading.Lock()
    live_ingest_stop = threading.Event()
    live_ingest_worker: dict[str, threading.Thread | None] = {"thread": None}
    live_ingest_status: dict[str, object] = {
        "status": "idle",
        "active": False,
        "source": None,
        "source_label": None,
        "rtmo_device": None,
        "frame_stride": None,
        "preview_stride": None,
        "loop": False,
        "processed_frames": 0,
        "started_at": None,
        "finished_at": None,
        "error_message": None,
    }
    profile_payload = system_profile or _default_system_profile(
        pipeline=pipeline,
        archive_enabled=archive_store is not None,
    )

    def _reset_live_preview() -> None:
        live_preview.update(
            {
                "bytes": None,
                "content_type": "image/jpeg",
                "source": None,
                "source_label": None,
                "timestamp": None,
                "frame_width": None,
                "frame_height": None,
                "annotated": False,
                "updated_at": None,
            }
        )

    def _current_live_ingest_status() -> dict[str, object]:
        with live_ingest_lock:
            payload = dict(live_ingest_status)
        thread = live_ingest_worker.get("thread")
        payload["active"] = bool(thread is not None and thread.is_alive())
        return payload

    def _run_live_ingest_job(job: LiveIngestStartRequest) -> None:
        processed_frames = 0
        final_status = "completed"
        error_message: str | None = None
        try:
            from huling_guard.runtime.live_ingest import LiveIngestConfig, run_live_ingest

            with live_ingest_lock:
                live_ingest_status.update(
                    {
                        "status": "running",
                        "active": True,
                        "error_message": None,
                        "finished_at": None,
                    }
                )

            processed_frames = run_live_ingest(
                LiveIngestConfig(
                    runtime_url=str(ingest_runtime_url),
                    source=job.source,
                    source_label=job.source_label,
                    rtmo_device=job.rtmo_device or upload_rtmo_device,
                    frame_stride=job.frame_stride,
                    preview_stride=job.preview_stride,
                    score_threshold=job.score_threshold,
                    loop=job.loop,
                    stop_requested=live_ingest_stop.is_set,
                )
            )
            final_status = "stopped" if live_ingest_stop.is_set() else "completed"
        except Exception as exc:  # pragma: no cover - runtime background path
            final_status = "failed"
            error_message = str(exc)
        finally:
            _reset_live_preview()
            finished_at = time.time()
            with live_ingest_lock:
                live_ingest_status.update(
                    {
                        "status": final_status,
                        "active": False,
                        "processed_frames": processed_frames,
                        "finished_at": finished_at,
                        "error_message": error_message,
                    }
                )
            live_ingest_worker["thread"] = None
            live_ingest_stop.clear()

    def _build_upload_response(stem: str) -> dict[str, object]:
        if resolved_demo_video_root is None:
            raise HTTPException(status_code=503, detail="demo video root is not enabled")
        _maybe_resume_upload(stem)
        path = resolved_demo_video_root / f"{stem}.mp4"
        metadata = _load_upload_metadata(resolved_demo_video_root, stem)
        report_path = resolved_demo_video_root.parent / "reports" / "sessions" / f"{stem}.json"
        annotated_path = _annotated_videos_root(resolved_demo_video_root) / f"{stem}.mp4"
        return {
            "name": stem,
            "filename": path.name,
            "size_bytes": path.stat().st_size if path.is_file() else 0,
            "url": f"/demo-videos/{path.name}",
            "annotated_url": f"/demo-annotated/{annotated_path.name}" if annotated_path.is_file() else None,
            "poster_url": None,
            "has_session_report": report_path.is_file(),
            "source_kind": "upload",
            "processing_status": str(metadata.get("processing_status") or "processing"),
            "original_name": metadata.get("original_name"),
            "error_message": metadata.get("error_message"),
            "processed_frames": metadata.get("processed_frames"),
            "total_frames": metadata.get("total_frames"),
        }

    def _run_upload_job(stem: str) -> None:
        try:
            _process_uploaded_video(stem)
        finally:
            with active_upload_jobs_lock:
                active_upload_jobs.discard(stem)

    def _start_upload_job(stem: str) -> bool:
        with active_upload_jobs_lock:
            if stem in active_upload_jobs:
                return False
            active_upload_jobs.add(stem)
        thread = threading.Thread(target=_run_upload_job, args=(stem,), daemon=True, name=f"upload-job-{stem[:16]}")
        thread.start()
        return True

    def _maybe_resume_upload(stem: str, *, allow_artifact_backfill: bool = False) -> None:
        if resolved_demo_video_root is None:
            return
        metadata = _load_upload_metadata(resolved_demo_video_root, stem)
        if str(metadata.get("source_kind") or "") != "upload":
            return

        input_path = resolved_demo_video_root / f"{stem}.mp4"
        report_path = resolved_demo_video_root.parent / "reports" / "sessions" / f"{stem}.json"
        annotated_path = _annotated_videos_root(resolved_demo_video_root) / f"{stem}.mp4"
        status = str(metadata.get("processing_status") or "")

        if status == "ready":
            if allow_artifact_backfill and input_path.is_file() and report_path.is_file() and not annotated_path.is_file():
                started = _start_upload_job(stem)
                if started:
                    _write_upload_metadata(
                        resolved_demo_video_root,
                        stem,
                        {
                            **metadata,
                            "processing_status": "processing",
                            "error_message": None,
                            "started_at": time.time(),
                        },
                    )
            return

        if status != "processing":
            return

        if report_path.is_file() and annotated_path.is_file():
            with active_upload_jobs_lock:
                job_active = stem in active_upload_jobs
            if job_active:
                return
            _write_upload_metadata(
                resolved_demo_video_root,
                stem,
                {
                    **metadata,
                    "processing_status": "ready",
                    "error_message": None,
                    "finished_at": metadata.get("finished_at") or time.time(),
                },
            )
            return

        if not input_path.is_file():
            _write_upload_metadata(
                resolved_demo_video_root,
                stem,
                {
                    **metadata,
                    "processing_status": "failed",
                    "error_message": "上传文件不存在，无法恢复分析任务。",
                    "finished_at": time.time(),
                },
            )
            return

        _start_upload_job(stem)

    def _process_uploaded_video(stem: str) -> None:
        if resolved_demo_video_root is None:
            return
        metadata = _load_upload_metadata(resolved_demo_video_root, stem)
        input_path = resolved_demo_video_root / f"{stem}.mp4"
        prediction_path = resolved_demo_video_root.parent / "predictions" / f"{stem}.jsonl"
        report_json_path = resolved_demo_video_root.parent / "reports" / "sessions" / f"{stem}.json"
        report_markdown_path = resolved_demo_video_root.parent / "reports" / "markdown" / f"{stem}.md"
        if not input_path.is_file():
            _write_upload_metadata(
                resolved_demo_video_root,
                stem,
                {
                    **metadata,
                    "processing_status": "failed",
                    "error_message": "上传文件不存在，无法开始分析。",
                    "finished_at": time.time(),
                },
            )
            return

        _write_upload_metadata(
            resolved_demo_video_root,
            stem,
            {
                **metadata,
                "processing_status": "processing",
                "error_message": None,
                "started_at": time.time(),
                "processed_frames": 0,
            },
        )
        try:
            if upload_pipeline_factory is None:
                raise RuntimeError("上传视频分析未启用")
            from huling_guard.runtime.video_inference import run_video_inference_with_runtime
            import cv2

            total_frames: int | None = None
            capture = cv2.VideoCapture(str(input_path))
            try:
                if capture.isOpened():
                    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                    total_frames = frame_count if frame_count > 0 else None
            finally:
                capture.release()

            _write_upload_metadata(
                resolved_demo_video_root,
                stem,
                {
                    **metadata,
                    "processing_status": "processing",
                    "error_message": None,
                    "started_at": metadata.get("started_at") or time.time(),
                    "processed_frames": 0,
                    "total_frames": total_frames,
                },
            )

            def _update_upload_progress(processed_frames: int) -> None:
                current = _load_upload_metadata(resolved_demo_video_root, stem)
                _write_upload_metadata(
                    resolved_demo_video_root,
                    stem,
                    {
                        **current,
                        "processing_status": "processing",
                        "error_message": None,
                        "processed_frames": processed_frames,
                        "total_frames": total_frames,
                    },
                )

            inference_pipeline = upload_pipeline_factory()
            estimator = RTMOPoseEstimator(device=upload_rtmo_device)
            annotated_video_path = _annotated_videos_root(resolved_demo_video_root) / f"{stem}.mp4"
            processed_frames = run_video_inference_with_runtime(
                input_path=input_path,
                pipeline=inference_pipeline,
                estimator=estimator,
                output_jsonl=prediction_path,
                output_video=annotated_video_path,
                output_report_json=report_json_path,
                output_report_markdown=report_markdown_path,
                progress_callback=_update_upload_progress,
            )
            _write_upload_metadata(
                resolved_demo_video_root,
                stem,
                {
                    **metadata,
                    "processing_status": "ready",
                    "error_message": None,
                    "finished_at": time.time(),
                    "processed_frames": processed_frames,
                    "total_frames": total_frames,
                },
            )
        except Exception as exc:  # pragma: no cover - runtime side effect path
            _write_upload_metadata(
                resolved_demo_video_root,
                stem,
                {
                    **metadata,
                    "processing_status": "failed",
                    "error_message": str(exc),
                    "finished_at": time.time(),
                    "total_frames": metadata.get("total_frames"),
                },
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
            "data_quality": {
                "pose_quality_score": last_snapshot.pose_quality_score,
                "mean_keypoint_confidence": last_snapshot.mean_keypoint_confidence,
                "visible_joint_ratio": last_snapshot.visible_joint_ratio,
            },
        }

    @app.get("/timeline")
    def timeline(limit: int = Query(default=120, ge=1, le=snapshot_history_size)) -> dict[str, object]:
        items = list(snapshot_history)[-limit:]
        return {"count": len(items), "items": items}

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(dashboard_html)

    @app.get("/", response_class=HTMLResponse)
    def dashboard_root() -> HTMLResponse:
        return HTMLResponse(dashboard_html)

    @app.get("/demo-videos")
    def demo_videos() -> dict[str, object]:
        if resolved_demo_video_root is not None:
            for path in resolved_demo_video_root.glob("upload_*.mp4"):
                _maybe_resume_upload(path.stem)
        items = _list_demo_videos(resolved_demo_video_root)
        return {
            "enabled": resolved_demo_video_root is not None,
            "root": str(resolved_demo_video_root) if resolved_demo_video_root is not None else None,
            "count": len(items),
            "items": items,
        }

    @app.post("/uploaded-videos")
    async def upload_video(video: UploadFile = File(...)) -> dict[str, object]:
        if resolved_demo_video_root is None:
            raise HTTPException(status_code=503, detail="demo video root is not enabled")
        if upload_pipeline_factory is None:
            raise HTTPException(status_code=503, detail="upload inference is not enabled")
        original_name = Path(video.filename or "video.mp4").name
        suffix = Path(original_name).suffix.lower()
        if suffix != ".mp4":
            raise HTTPException(status_code=400, detail="当前仅支持上传 mp4 视频")

        stem = f"upload_{int(time.time())}_{_sanitize_upload_name(original_name)}_{uuid4().hex[:8]}"
        target_path = resolved_demo_video_root / f"{stem}.mp4"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as handle:
            shutil.copyfileobj(video.file, handle)

        metadata = _write_upload_metadata(
            resolved_demo_video_root,
            stem,
            {
                "source_kind": "upload",
                "processing_status": "processing",
                "original_name": original_name,
                "error_message": None,
                "created_at": time.time(),
                "processed_frames": 0,
                "total_frames": None,
            },
        )
        _start_upload_job(stem)
        return {
            "status": "processing",
            "item": _build_upload_response(stem),
            "metadata": metadata,
        }

    @app.delete("/demo-videos/{filename}")
    def delete_demo_video(filename: str) -> dict[str, object]:
        if resolved_demo_video_root is None:
            raise HTTPException(status_code=404, detail="demo video root is not enabled")
        normalized = Path(filename).name
        if normalized != filename:
            raise HTTPException(status_code=400, detail="invalid demo video filename")

        stem = Path(normalized).stem
        metadata = _load_upload_metadata(resolved_demo_video_root, stem)
        if str(metadata.get("source_kind") or "") != "upload":
            raise HTTPException(status_code=400, detail="only uploaded videos can be deleted")

        if archive_store is not None:
            archive_count = archive_store.count_archives_by_session_name(stem)
            if archive_count > 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"该上传视频已被 {archive_count} 条历史留档引用，请先清理对应留档",
                )

        with active_upload_jobs_lock:
            if stem in active_upload_jobs or str(metadata.get("processing_status") or "") == "processing":
                raise HTTPException(status_code=409, detail="upload is still processing")
            active_upload_jobs.discard(stem)

        removed = _delete_upload_artifacts(resolved_demo_video_root, stem)
        if not removed:
            raise HTTPException(status_code=404, detail="upload artifacts not found")

        return {"status": "deleted", "removed": [str(path) for path in removed]}


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


    @app.get("/demo-annotated/{filename}")
    def demo_annotated_file(filename: str) -> FileResponse:
        if resolved_demo_video_root is None:
            raise HTTPException(status_code=404, detail="demo video root is not enabled")
        normalized = Path(filename).name
        if normalized != filename:
            raise HTTPException(status_code=400, detail="invalid annotated video filename")
        annotated_root = _annotated_videos_root(resolved_demo_video_root)
        path = (annotated_root / normalized).resolve()
        try:
            path.relative_to(annotated_root)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid annotated video path") from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"annotated video not found: {filename}")
        return FileResponse(path)

    @app.get("/demo-posters/{filename}")
    def demo_poster_file(filename: str) -> FileResponse:
        if resolved_demo_video_root is None:
            raise HTTPException(status_code=404, detail="demo video root is not enabled")
        normalized = Path(filename).name
        if normalized != filename:
            raise HTTPException(status_code=400, detail="invalid demo poster filename")
        poster_root = resolved_demo_video_root.parent / "posters"
        path = (poster_root / normalized).resolve()
        try:
            path.relative_to(poster_root)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid demo poster path") from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"demo poster not found: {filename}")
        return FileResponse(path)

    @app.get("/demo-sessions/{filename}")
    def demo_session_payload(filename: str, limit: int = Query(default=180, ge=1, le=2048)) -> dict[str, object]:
        normalized = Path(filename).name
        if normalized != filename:
            raise HTTPException(status_code=400, detail="invalid demo session filename")
        stem = Path(normalized).stem
        _maybe_resume_upload(stem, allow_artifact_backfill=True)
        try:
            return _load_demo_session_payload(resolved_demo_video_root, stem=stem, limit=limit)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/live-source")
    def live_source() -> dict[str, object]:
        return {
            "available": live_preview["bytes"] is not None,
            "source": live_preview["source"],
            "source_label": live_preview["source_label"],
            "timestamp": live_preview["timestamp"],
            "frame_width": live_preview["frame_width"],
            "frame_height": live_preview["frame_height"],
            "annotated": live_preview["annotated"],
            "updated_at": live_preview["updated_at"],
        }

    @app.get("/live-ingest")
    def live_ingest() -> dict[str, object]:
        return _current_live_ingest_status()

    @app.post("/live-ingest/start")
    def start_live_ingest(payload: LiveIngestStartRequest) -> dict[str, object]:
        if ingest_runtime_url is None:
            raise HTTPException(status_code=503, detail="live ingest is not enabled")
        source = payload.source.strip()
        if not source:
            raise HTTPException(status_code=400, detail="请输入摄像头编号、RTSP 地址或视频路径")
        thread = live_ingest_worker.get("thread")
        if thread is not None and thread.is_alive():
            raise HTTPException(status_code=409, detail="当前已有实时接入任务在运行")

        request_payload = payload.model_copy(
            update={
                "source": source,
                "source_label": (payload.source_label or "").strip() or None,
                "rtmo_device": payload.rtmo_device or upload_rtmo_device,
            }
        )
        live_ingest_stop.clear()
        _reset_live_preview()
        started_at = time.time()
        with live_ingest_lock:
            live_ingest_status.update(
                {
                    "status": "starting",
                    "active": True,
                    "source": request_payload.source,
                    "source_label": request_payload.source_label,
                    "rtmo_device": request_payload.rtmo_device,
                    "frame_stride": request_payload.frame_stride,
                    "preview_stride": request_payload.preview_stride,
                    "loop": request_payload.loop,
                    "processed_frames": 0,
                    "started_at": started_at,
                    "finished_at": None,
                    "error_message": None,
                }
            )
        thread = threading.Thread(
            target=_run_live_ingest_job,
            args=(request_payload,),
            name="huling-live-ingest",
            daemon=True,
        )
        live_ingest_worker["thread"] = thread
        thread.start()
        return _current_live_ingest_status()

    @app.post("/live-ingest/stop")
    def stop_live_ingest() -> dict[str, object]:
        thread = live_ingest_worker.get("thread")
        if thread is None or not thread.is_alive():
            with live_ingest_lock:
                if live_ingest_status.get("status") in {"running", "starting", "stopping"}:
                    live_ingest_status["status"] = "idle"
                    live_ingest_status["active"] = False
            _reset_live_preview()
            return _current_live_ingest_status()

        live_ingest_stop.set()
        with live_ingest_lock:
            live_ingest_status.update({"status": "stopping", "active": True})
        return _current_live_ingest_status()

    @app.get("/live-frame")
    def live_frame() -> Response:
        frame_bytes = live_preview["bytes"]
        if frame_bytes is None:
            raise HTTPException(status_code=404, detail="live frame is not available")
        return Response(
            content=frame_bytes,
            media_type=str(live_preview["content_type"] or "image/jpeg"),
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.post("/live-frame")
    async def push_live_frame(
        request: Request,
        source: str | None = Query(default=None),
        source_label: str | None = Query(default=None),
        timestamp: float | None = Query(default=None),
        frame_width: int | None = Query(default=None),
        frame_height: int | None = Query(default=None),
        annotated: bool = Query(default=False),
    ) -> dict[str, object]:
        payload = await request.body()
        if not payload:
            raise HTTPException(status_code=400, detail="live frame payload is empty")
        live_preview["bytes"] = payload
        live_preview["content_type"] = request.headers.get("content-type", "image/jpeg")
        live_preview["source"] = source
        live_preview["source_label"] = source_label or source
        live_preview["timestamp"] = timestamp
        live_preview["frame_width"] = frame_width
        live_preview["frame_height"] = frame_height
        live_preview["annotated"] = annotated
        live_preview["updated_at"] = float(timestamp) if timestamp is not None else None
        return {
            "status": "ok",
            "source": live_preview["source"],
            "source_label": live_preview["source_label"],
            "timestamp": live_preview["timestamp"],
            "annotated": live_preview["annotated"],
            "size_bytes": len(payload),
        }

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
    def archive_session(
        payload: ArchiveSessionRequest | None = None,
        limit: int = Query(default=512, ge=1, le=snapshot_history_size),
    ) -> dict[str, object]:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        demo_filename = payload.demo_filename if payload is not None else None
        if demo_filename:
            if resolved_demo_video_root is None:
                raise HTTPException(status_code=503, detail="demo video root is not enabled")
            normalized = Path(demo_filename).name
            if normalized != demo_filename:
                raise HTTPException(status_code=400, detail="invalid demo session filename")
            stem = Path(normalized).stem
            _maybe_resume_upload(stem)
            metadata = _load_upload_metadata(resolved_demo_video_root, stem)
            if str(metadata.get("source_kind") or "") == "upload" and str(metadata.get("processing_status") or "") == "processing":
                raise HTTPException(status_code=409, detail="当前视频还在分析，完成后再保存到历史回看")
            session_payload = _load_demo_session_payload(resolved_demo_video_root, stem=stem, limit=0)
            report = dict(session_payload["session_report"])
        else:
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

    @app.delete("/archives/{session_id}")
    def delete_archive(session_id: str) -> dict[str, object]:
        if archive_store is None:
            raise HTTPException(status_code=503, detail="archive is not enabled")
        try:
            record = archive_store.delete_archive(session_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=f"archive not found: {session_id}") from error
        return {"status": "deleted", "record": record}


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
