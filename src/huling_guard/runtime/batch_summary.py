from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_session_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def enrich_processed_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for clip in clips:
        row = dict(clip)
        report_path = row.get("session_report_json")
        needs_session_fields = any(
            key not in row or row.get(key) is None
            for key in ("duration_seconds", "dominant_state", "incident_total", "peak_risk_score")
        )
        if needs_session_fields and isinstance(report_path, str) and report_path.strip():
            report = load_session_report(report_path)
            row.setdefault("duration_seconds", float(report.get("duration_seconds") or 0.0))
            row.setdefault("dominant_state", report.get("dominant_state"))
            row.setdefault("incident_total", int(report.get("incident_total") or 0))
            row.setdefault("peak_risk_score", float(report.get("peak_risk_score") or 0.0))
        enriched.append(row)
    return enriched


def summarize_expected_states(clips: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "with_expected_state": 0,
        "expected_normal_total": 0,
        "expected_normal_with_incidents": 0,
        "expected_normal_dominant_non_normal": 0,
        "expected_positive_total": 0,
        "expected_positive_without_incidents": 0,
        "expected_positive_dominant_normal": 0,
        "per_expected_state": {},
    }

    for clip in clips:
        expected_state = clip.get("expected_state")
        if not isinstance(expected_state, str) or not expected_state:
            continue
        incident_total = int(clip.get("incident_total") or 0)
        dominant_state = str(clip.get("dominant_state") or "").strip() or None
        per_state = summary["per_expected_state"].setdefault(
            expected_state,
            {
                "total": 0,
                "sessions_with_incidents": 0,
                "dominant_state_counts": {},
            },
        )
        per_state["total"] += 1
        if incident_total > 0:
            per_state["sessions_with_incidents"] += 1
        if dominant_state is not None:
            dominant_counts = per_state["dominant_state_counts"]
            dominant_counts[dominant_state] = int(dominant_counts.get(dominant_state, 0)) + 1

        summary["with_expected_state"] += 1
        if expected_state == "normal":
            summary["expected_normal_total"] += 1
            if incident_total > 0:
                summary["expected_normal_with_incidents"] += 1
            if dominant_state is not None and dominant_state != "normal":
                summary["expected_normal_dominant_non_normal"] += 1
        else:
            summary["expected_positive_total"] += 1
            if incident_total <= 0:
                summary["expected_positive_without_incidents"] += 1
            if dominant_state == "normal":
                summary["expected_positive_dominant_normal"] += 1

    expected_normal_total = int(summary["expected_normal_total"])
    expected_positive_total = int(summary["expected_positive_total"])
    summary["expected_normal_incident_rate"] = (
        float(summary["expected_normal_with_incidents"]) / expected_normal_total
        if expected_normal_total > 0
        else 0.0
    )
    summary["expected_normal_dominant_non_normal_rate"] = (
        float(summary["expected_normal_dominant_non_normal"]) / expected_normal_total
        if expected_normal_total > 0
        else 0.0
    )
    summary["expected_positive_missed_incident_rate"] = (
        float(summary["expected_positive_without_incidents"]) / expected_positive_total
        if expected_positive_total > 0
        else 0.0
    )
    summary["expected_positive_dominant_normal_rate"] = (
        float(summary["expected_positive_dominant_normal"]) / expected_positive_total
        if expected_positive_total > 0
        else 0.0
    )
    return summary
