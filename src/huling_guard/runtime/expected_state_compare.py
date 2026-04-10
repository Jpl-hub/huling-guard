from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from huling_guard.runtime.batch_summary import enrich_processed_clips, summarize_expected_states


def load_processed_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_expected_state_comparison(
    *,
    baseline_manifest_path: str | Path,
    candidate_manifest_path: str | Path,
    expected_state: str = "normal",
) -> dict[str, Any]:
    baseline_manifest = load_processed_manifest(baseline_manifest_path)
    candidate_manifest = load_processed_manifest(candidate_manifest_path)

    baseline_clips = enrich_processed_clips(baseline_manifest.get("clips", []))
    candidate_clips = enrich_processed_clips(candidate_manifest.get("clips", []))
    baseline_summary = summarize_expected_states(baseline_clips)
    candidate_summary = summarize_expected_states(candidate_clips)

    if expected_state == "normal":
        baseline_total = int(baseline_summary.get("expected_normal_total", 0))
        candidate_total = int(candidate_summary.get("expected_normal_total", 0))
        baseline_incidents = int(baseline_summary.get("expected_normal_with_incidents", 0))
        candidate_incidents = int(candidate_summary.get("expected_normal_with_incidents", 0))
        baseline_drift = int(baseline_summary.get("expected_normal_dominant_non_normal", 0))
        candidate_drift = int(candidate_summary.get("expected_normal_dominant_non_normal", 0))
        baseline_incident_rate = float(baseline_summary.get("expected_normal_incident_rate", 0.0))
        candidate_incident_rate = float(candidate_summary.get("expected_normal_incident_rate", 0.0))
        baseline_drift_rate = float(baseline_summary.get("expected_normal_dominant_non_normal_rate", 0.0))
        candidate_drift_rate = float(candidate_summary.get("expected_normal_dominant_non_normal_rate", 0.0))
    else:
        baseline_per_state = baseline_summary.get("per_expected_state", {}).get(expected_state, {})
        candidate_per_state = candidate_summary.get("per_expected_state", {}).get(expected_state, {})
        baseline_total = int(baseline_per_state.get("total", 0))
        candidate_total = int(candidate_per_state.get("total", 0))
        baseline_incidents = int(baseline_per_state.get("sessions_with_incidents", 0))
        candidate_incidents = int(candidate_per_state.get("sessions_with_incidents", 0))
        baseline_drift = int(baseline_per_state.get("dominant_state_counts", {}).get("normal", 0))
        candidate_drift = int(candidate_per_state.get("dominant_state_counts", {}).get("normal", 0))
        baseline_incident_rate = baseline_incidents / baseline_total if baseline_total > 0 else 0.0
        candidate_incident_rate = candidate_incidents / candidate_total if candidate_total > 0 else 0.0
        baseline_drift_rate = baseline_drift / baseline_total if baseline_total > 0 else 0.0
        candidate_drift_rate = candidate_drift / candidate_total if candidate_total > 0 else 0.0

    def _incident_sum(clips: list[dict[str, Any]]) -> int:
        return sum(
            int(clip.get("incident_total") or 0)
            for clip in clips
            if str(clip.get("expected_state") or "").strip() == expected_state
        )

    baseline_incident_sum = _incident_sum(baseline_clips)
    candidate_incident_sum = _incident_sum(candidate_clips)

    return {
        "expected_state": expected_state,
        "baseline_manifest_path": str(Path(baseline_manifest_path).resolve()),
        "candidate_manifest_path": str(Path(candidate_manifest_path).resolve()),
        "baseline": {
            "total": baseline_total,
            "with_incidents": baseline_incidents,
            "with_incidents_rate": baseline_incident_rate,
            "dominant_drift": baseline_drift,
            "dominant_drift_rate": baseline_drift_rate,
            "incident_sum": baseline_incident_sum,
            "dominant_counts": baseline_summary.get("per_expected_state", {}).get(expected_state, {}).get(
                "dominant_state_counts", {}
            ),
        },
        "candidate": {
            "total": candidate_total,
            "with_incidents": candidate_incidents,
            "with_incidents_rate": candidate_incident_rate,
            "dominant_drift": candidate_drift,
            "dominant_drift_rate": candidate_drift_rate,
            "incident_sum": candidate_incident_sum,
            "dominant_counts": candidate_summary.get("per_expected_state", {}).get(expected_state, {}).get(
                "dominant_state_counts", {}
            ),
        },
        "delta": {
            "with_incidents": candidate_incidents - baseline_incidents,
            "with_incidents_rate": candidate_incident_rate - baseline_incident_rate,
            "dominant_drift": candidate_drift - baseline_drift,
            "dominant_drift_rate": candidate_drift_rate - baseline_drift_rate,
            "incident_sum": candidate_incident_sum - baseline_incident_sum,
        },
    }


def build_expected_state_comparison_markdown(payload: dict[str, Any]) -> str:
    baseline = payload["baseline"]
    candidate = payload["candidate"]
    delta = payload["delta"]
    lines = [
        "# 期望状态对比",
        "",
        f"- expected_state: {payload['expected_state']}",
        f"- baseline_manifest: {payload['baseline_manifest_path']}",
        f"- candidate_manifest: {payload['candidate_manifest_path']}",
        "",
        "## 核心指标",
        f"- with_incidents: {baseline['with_incidents']} -> {candidate['with_incidents']} ({delta['with_incidents']:+d})",
        (
            f"- with_incidents_rate: {baseline['with_incidents_rate']:.4f} -> "
            f"{candidate['with_incidents_rate']:.4f} ({delta['with_incidents_rate']:+.4f})"
        ),
        f"- dominant_drift: {baseline['dominant_drift']} -> {candidate['dominant_drift']} ({delta['dominant_drift']:+d})",
        (
            f"- dominant_drift_rate: {baseline['dominant_drift_rate']:.4f} -> "
            f"{candidate['dominant_drift_rate']:.4f} ({delta['dominant_drift_rate']:+.4f})"
        ),
        f"- incident_sum: {baseline['incident_sum']} -> {candidate['incident_sum']} ({delta['incident_sum']:+d})",
        "",
        "## Baseline dominant counts",
    ]
    for state, count in sorted(baseline.get("dominant_counts", {}).items()):
        lines.append(f"- {state}: {count}")
    lines.extend(["", "## Candidate dominant counts"])
    for state, count in sorted(candidate.get("dominant_counts", {}).items()):
        lines.append(f"- {state}: {count}")
    return "\n".join(lines) + "\n"
