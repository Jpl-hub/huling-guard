from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib import request

import numpy as np

from huling_guard.data.pose_io import load_pose_archive


def _resolve_inputs(inputs: list[str]) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()
    for item in inputs:
        candidate = Path(item).resolve()
        paths = sorted(candidate.rglob("*.npz")) if candidate.is_dir() else [candidate]
        for path in paths:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            discovered.append(path)
    return discovered


def _post_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(base_url: str, path: str) -> dict[str, Any]:
    with request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _replay_pose_archive(base_url: str, pose_archive: Path, *, archive_session: bool) -> dict[str, Any]:
    keypoints, payload = load_pose_archive(pose_archive)
    timestamps = payload.get("timestamps")
    fps = float(np.asarray(payload.get("fps", np.asarray([20.0], dtype=np.float32))).reshape(-1)[0])
    frame_width = payload.get("frame_width")
    frame_height = payload.get("frame_height")
    frame_width_value = float(np.asarray(frame_width).reshape(-1)[0]) if frame_width is not None else None
    frame_height_value = float(np.asarray(frame_height).reshape(-1)[0]) if frame_height is not None else None
    if timestamps is None:
        timestamps_array = np.arange(keypoints.shape[0], dtype=np.float32) / max(fps, 1e-6)
    else:
        timestamps_array = np.asarray(timestamps, dtype=np.float32)

    _post_json(base_url, "/reset")
    ready_frames = 0
    final_snapshot: dict[str, Any] | None = None
    for frame_keypoints, timestamp in zip(keypoints, timestamps_array, strict=False):
        final_snapshot = _post_json(
            base_url,
            "/pose-frame",
            {
                "timestamp": float(timestamp),
                "keypoints": np.asarray(frame_keypoints, dtype=np.float32).tolist(),
                "frame_width": frame_width_value,
                "frame_height": frame_height_value,
            },
        )
        if final_snapshot.get("ready"):
            ready_frames += 1

    session_report = _get_json(base_url, "/session-report")
    archive_record = None
    if archive_session:
        archive_result = _post_json(base_url, "/archive-session")
        archive_record = archive_result.get("record")

    return {
        "pose_archive": str(pose_archive),
        "frame_count": int(keypoints.shape[0]),
        "ready_frames": int(ready_frames),
        "window_size": int(final_snapshot.get("window_size") or 0) if final_snapshot else 0,
        "final_state": final_snapshot.get("predicted_state") if final_snapshot else None,
        "final_risk_score": float(final_snapshot.get("risk_score") or 0.0) if final_snapshot else 0.0,
        "session_report": session_report,
        "archive_record": archive_record,
    }


def _format_summary_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# 运行时骨架回放摘要",
        "",
        f"- 回放会话数: {len(results)}",
        "",
        "## 会话明细",
    ]
    for item in results:
        report = item["session_report"]
        lines.append(
            (
                f"- {Path(item['pose_archive']).name}: frames={item['frame_count']} "
                f"ready_frames={item['ready_frames']} dominant_state={report.get('dominant_state')} "
                f"incident_total={report.get('incident_total')} "
                f"peak_risk={float((report.get('peak_risk') or {}).get('risk_score') or 0.0):.4f}"
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="将已抽取骨架序列回放到运行时服务")
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--inputs", nargs="+", required=True)
    parser.add_argument("--archive-session", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--output-markdown")
    args = parser.parse_args()

    pose_archives = _resolve_inputs(args.inputs)
    results = [
        _replay_pose_archive(
            args.service_url,
            pose_archive,
            archive_session=args.archive_session,
        )
        for pose_archive in pose_archives
    ]

    summary = {
        "service_url": args.service_url,
        "session_count": len(results),
        "results": results,
    }
    if args.output_json:
        output_json_path = Path(args.output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_markdown:
        output_markdown_path = Path(args.output_markdown)
        output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        output_markdown_path.write_text(_format_summary_markdown(results), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), end="")


if __name__ == "__main__":
    main()
