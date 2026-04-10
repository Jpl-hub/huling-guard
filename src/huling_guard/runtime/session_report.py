from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Sequence


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    state_probs = snapshot.get("state_probs") or {}
    incidents = snapshot.get("incidents") or []
    return {
        "timestamp": _as_float(snapshot.get("timestamp")),
        "ready": bool(snapshot.get("ready")),
        "observed_frames": int(snapshot.get("observed_frames") or 0),
        "window_size": int(snapshot.get("window_size") or 0),
        "window_span_seconds": _as_float(snapshot.get("window_span_seconds")),
        "state_probs": {str(key): _as_float(value) for key, value in state_probs.items()},
        "predicted_state": snapshot.get("predicted_state"),
        "confidence": _as_float(snapshot.get("confidence")),
        "risk_score": _as_float(snapshot.get("risk_score")),
        "incidents": [_normalize_incident(incident) for incident in incidents],
    }


def _normalize_incident(incident: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(incident.get("kind") or "unknown"),
        "timestamp": _as_float(incident.get("timestamp")),
        "confidence": _as_float(incident.get("confidence")),
        "payload": incident.get("payload") or {},
    }


def load_session_snapshots(path: str | Path) -> list[dict[str, Any]]:
    snapshot_path = Path(path)
    snapshots: list[dict[str, Any]] = []
    with snapshot_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            snapshots.append(_normalize_snapshot(json.loads(payload)))
    return snapshots


def _collect_incidents(
    snapshots: Sequence[dict[str, Any]],
    incidents: Sequence[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if incidents is not None:
        return [_normalize_incident(item) for item in incidents]
    flattened: list[dict[str, Any]] = []
    for snapshot in snapshots:
        flattened.extend(snapshot.get("incidents") or [])
    return [_normalize_incident(item) for item in flattened]


def _build_state_segments(snapshots: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    ready_snapshots = [snapshot for snapshot in snapshots if snapshot["ready"] and snapshot.get("predicted_state")]
    if not ready_snapshots:
        return []

    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for snapshot in ready_snapshots:
        state = str(snapshot["predicted_state"])
        timestamp = snapshot["timestamp"]
        if current is None or current["state"] != state:
            if current is not None:
                current["duration_seconds"] = max(0.0, current["end_timestamp"] - current["start_timestamp"])
                segments.append(current)
            current = {
                "state": state,
                "start_timestamp": timestamp,
                "end_timestamp": timestamp,
                "frame_count": 1,
                "max_risk_score": snapshot["risk_score"],
                "max_confidence": snapshot["confidence"],
            }
            continue
        current["end_timestamp"] = timestamp
        current["frame_count"] += 1
        current["max_risk_score"] = max(float(current["max_risk_score"]), snapshot["risk_score"])
        current["max_confidence"] = max(float(current["max_confidence"]), snapshot["confidence"])

    if current is not None:
        current["duration_seconds"] = max(0.0, current["end_timestamp"] - current["start_timestamp"])
        segments.append(current)
    return segments


def build_session_report(
    *,
    snapshots: Sequence[dict[str, Any]],
    incidents: Sequence[dict[str, Any]] | None = None,
    session_name: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    normalized_snapshots = [_normalize_snapshot(snapshot) for snapshot in snapshots]
    normalized_incidents = _collect_incidents(normalized_snapshots, incidents)

    total_frames = len(normalized_snapshots)
    ready_snapshots = [snapshot for snapshot in normalized_snapshots if snapshot["ready"]]
    ready_frames = len(ready_snapshots)
    state_counter = Counter(
        str(snapshot["predicted_state"])
        for snapshot in ready_snapshots
        if snapshot.get("predicted_state")
    )
    incident_counter = Counter(incident["kind"] for incident in normalized_incidents)
    segments = _build_state_segments(normalized_snapshots)

    first_timestamp = normalized_snapshots[0]["timestamp"] if normalized_snapshots else 0.0
    last_timestamp = normalized_snapshots[-1]["timestamp"] if normalized_snapshots else 0.0
    duration_seconds = max(0.0, last_timestamp - first_timestamp)

    peak_snapshot = None
    if ready_snapshots:
        peak_snapshot = max(ready_snapshots, key=lambda snapshot: snapshot["risk_score"])
    elif normalized_snapshots:
        peak_snapshot = max(normalized_snapshots, key=lambda snapshot: snapshot["risk_score"])

    top_risk_moments = sorted(
        (
            {
                "timestamp": snapshot["timestamp"],
                "predicted_state": snapshot.get("predicted_state"),
                "risk_score": snapshot["risk_score"],
                "confidence": snapshot["confidence"],
            }
            for snapshot in ready_snapshots
        ),
        key=lambda item: item["risk_score"],
        reverse=True,
    )[:5]

    longest_segments = sorted(
        segments,
        key=lambda item: (float(item["duration_seconds"]), int(item["frame_count"])),
        reverse=True,
    )[:5]

    mean_risk_score = fmean(snapshot["risk_score"] for snapshot in ready_snapshots) if ready_snapshots else 0.0
    mean_confidence = fmean(snapshot["confidence"] for snapshot in ready_snapshots) if ready_snapshots else 0.0

    report = {
        "session_name": session_name or "session",
        "source_path": source_path,
        "total_frames": total_frames,
        "ready_frames": ready_frames,
        "warmup_frames": max(0, total_frames - ready_frames),
        "ready_ratio": float(ready_frames / total_frames) if total_frames else 0.0,
        "start_timestamp": first_timestamp,
        "end_timestamp": last_timestamp,
        "duration_seconds": duration_seconds,
        "peak_risk": {
            "timestamp": peak_snapshot["timestamp"] if peak_snapshot else 0.0,
            "predicted_state": peak_snapshot.get("predicted_state") if peak_snapshot else None,
            "risk_score": peak_snapshot["risk_score"] if peak_snapshot else 0.0,
            "confidence": peak_snapshot["confidence"] if peak_snapshot else 0.0,
        },
        "mean_risk_score": mean_risk_score,
        "mean_confidence": mean_confidence,
        "dominant_state": state_counter.most_common(1)[0][0] if state_counter else None,
        "predicted_state_counts": dict(state_counter),
        "incident_total": int(sum(incident_counter.values())),
        "incident_counts": dict(incident_counter),
        "first_incident": normalized_incidents[0] if normalized_incidents else None,
        "last_incident": normalized_incidents[-1] if normalized_incidents else None,
        "recent_incidents": normalized_incidents[-5:],
        "top_risk_moments": top_risk_moments,
        "state_segments": segments,
        "longest_segments": longest_segments,
    }
    return report


def format_session_report_markdown(report: dict[str, Any]) -> str:
    peak_risk = report.get("peak_risk") or {}
    lines = [
        "# 会话报告",
        "",
        "## 基本信息",
        f"- 会话名称: {report.get('session_name')}",
        f"- 输入来源: {report.get('source_path') or 'unknown'}",
        f"- 总帧数: {report.get('total_frames', 0)}",
        f"- 有效推理帧数: {report.get('ready_frames', 0)}",
        f"- 预热帧数: {report.get('warmup_frames', 0)}",
        f"- 有效帧占比: {float(report.get('ready_ratio', 0.0)):.4f}",
        f"- 持续时长(秒): {float(report.get('duration_seconds', 0.0)):.2f}",
        "",
        "## 风险摘要",
        f"- 主导状态: {report.get('dominant_state') or 'unknown'}",
        f"- 平均风险分数: {float(report.get('mean_risk_score', 0.0)):.4f}",
        f"- 平均置信度: {float(report.get('mean_confidence', 0.0)):.4f}",
        (
            f"- 峰值风险: state={peak_risk.get('predicted_state') or 'unknown'} "
            f"risk={float(peak_risk.get('risk_score', 0.0)):.4f} "
            f"timestamp={float(peak_risk.get('timestamp', 0.0)):.2f}s"
        ),
        "",
        "## 状态分布",
    ]

    state_counts = report.get("predicted_state_counts") or {}
    if state_counts:
        for state, count in state_counts.items():
            lines.append(f"- {state}: {count}")
    else:
        lines.append("- 无有效推理结果")

    lines.extend(["", "## 事件统计"])
    incident_counts = report.get("incident_counts") or {}
    if incident_counts:
        lines.append(f"- 事件总数: {int(report.get('incident_total', 0))}")
        for kind, count in incident_counts.items():
            lines.append(f"- {kind}: {count}")
    else:
        lines.append("- 本次会话未触发事件")

    longest_segments = report.get("longest_segments") or []
    lines.extend(["", "## 主要状态片段"])
    if longest_segments:
        for segment in longest_segments:
            lines.append(
                (
                    f"- {segment['state']}: start={float(segment['start_timestamp']):.2f}s "
                    f"end={float(segment['end_timestamp']):.2f}s "
                    f"duration={float(segment['duration_seconds']):.2f}s "
                    f"frames={int(segment['frame_count'])} "
                    f"max_risk={float(segment['max_risk_score']):.4f}"
                )
            )
    else:
        lines.append("- 无可用状态片段")

    recent_incidents = report.get("recent_incidents") or []
    lines.extend(["", "## 最近事件"])
    if recent_incidents:
        for incident in recent_incidents:
            lines.append(
                (
                    f"- {incident['kind']}: timestamp={float(incident['timestamp']):.2f}s "
                    f"confidence={float(incident['confidence']):.4f}"
                )
            )
    else:
        lines.append("- 无")

    return "\n".join(lines) + "\n"


def write_session_report(
    report: dict[str, Any],
    *,
    output_json: str | Path | None = None,
    output_markdown: str | Path | None = None,
) -> None:
    if output_json is not None:
        output_json_path = Path(output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if output_markdown is not None:
        output_markdown_path = Path(output_markdown)
        output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        output_markdown_path.write_text(
            format_session_report_markdown(report),
            encoding="utf-8",
        )


def summarize_session_jsonl(
    *,
    predictions_path: str | Path,
    session_name: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    snapshots = load_session_snapshots(predictions_path)
    resolved_source = source_path or str(Path(predictions_path).resolve())
    return build_session_report(
        snapshots=snapshots,
        session_name=session_name or Path(predictions_path).stem,
        source_path=resolved_source,
    )
