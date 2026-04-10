import json
from pathlib import Path

from huling_guard.runtime.expected_state_compare import (
    build_expected_state_comparison,
    build_expected_state_comparison_markdown,
)


def _write_report(path: Path, *, dominant_state: str, incident_total: int) -> None:
    path.write_text(
        json.dumps(
            {
                "duration_seconds": 8.0,
                "dominant_state": dominant_state,
                "incident_total": incident_total,
                "peak_risk_score": 0.9,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_expected_state_comparison_for_normal_sessions(tmp_path: Path) -> None:
    baseline_report_a = tmp_path / "baseline_a.json"
    baseline_report_b = tmp_path / "baseline_b.json"
    candidate_report_a = tmp_path / "candidate_a.json"
    candidate_report_b = tmp_path / "candidate_b.json"
    _write_report(baseline_report_a, dominant_state="normal", incident_total=1)
    _write_report(baseline_report_b, dominant_state="fall", incident_total=1)
    _write_report(candidate_report_a, dominant_state="normal", incident_total=0)
    _write_report(candidate_report_b, dominant_state="normal", incident_total=1)

    baseline_manifest = tmp_path / "baseline.json"
    candidate_manifest = tmp_path / "candidate.json"
    baseline_manifest.write_text(
        json.dumps(
            {
                "clips": [
                    {"clip_id": "a", "expected_state": "normal", "session_report_json": str(baseline_report_a)},
                    {"clip_id": "b", "expected_state": "normal", "session_report_json": str(baseline_report_b)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    candidate_manifest.write_text(
        json.dumps(
            {
                "clips": [
                    {"clip_id": "a", "expected_state": "normal", "session_report_json": str(candidate_report_a)},
                    {"clip_id": "b", "expected_state": "normal", "session_report_json": str(candidate_report_b)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_expected_state_comparison(
        baseline_manifest_path=baseline_manifest,
        candidate_manifest_path=candidate_manifest,
        expected_state="normal",
    )

    assert payload["baseline"]["with_incidents"] == 2
    assert payload["candidate"]["with_incidents"] == 1
    assert payload["delta"]["with_incidents"] == -1
    assert payload["baseline"]["dominant_drift"] == 1
    assert payload["candidate"]["dominant_drift"] == 0
    assert payload["delta"]["dominant_drift"] == -1

    markdown = build_expected_state_comparison_markdown(payload)
    assert "with_incidents: 2 -> 1 (-1)" in markdown
    assert "dominant_drift: 1 -> 0 (-1)" in markdown
