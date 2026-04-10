import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from summarize_batch_inference import _build_markdown

from huling_guard.runtime.batch_summary import summarize_expected_states


def test_build_markdown_includes_key_metrics_and_clips() -> None:
    processed_manifest = {
        "expected_state_summary": {
            "with_expected_state": 2,
            "expected_normal_total": 1,
            "expected_normal_with_incidents": 1,
            "expected_normal_incident_rate": 1.0,
            "expected_normal_dominant_non_normal": 1,
            "expected_normal_dominant_non_normal_rate": 1.0,
            "expected_positive_total": 1,
            "expected_positive_without_incidents": 0,
            "expected_positive_missed_incident_rate": 0.0,
            "expected_positive_dominant_normal": 0,
            "expected_positive_dominant_normal_rate": 0.0,
        },
        "clips": [
            {
                "clip_id": "clip_01",
                "frames": 120,
                "expected_state": "normal",
                "dominant_state": "fall",
                "incident_total": 1,
                "predictions": "predictions/clip_01.jsonl",
                "annotations": "annotations/clip_01.json",
            },
            {
                "clip_id": "clip_02",
                "frames": 240,
                "expected_state": "fall",
                "dominant_state": "fall",
                "incident_total": 1,
                "predictions": "predictions/clip_02.jsonl",
                "annotations": None,
            },
        ]
    }
    event_summary = {
        "precision": 0.8,
        "recall": 0.75,
        "f1": 0.774193548,
        "false_positives_per_hour": 1.5,
        "mean_abs_delay_seconds": 0.6,
        "kinds": ["confirmed_fall"],
        "per_kind": {
            "confirmed_fall": {
                "tp": 3,
                "fp": 1,
                "fn": 1,
                "precision": 0.75,
                "recall": 0.75,
                "f1": 0.75,
            }
        },
    }

    markdown = _build_markdown(processed_manifest, event_summary)

    assert "# 批量视频验证汇总" in markdown
    assert "- 视频数量: 2" in markdown
    assert "- 总帧数: 360" in markdown
    assert "- normal 误报会话数: 1 / 1 (1.0000)" in markdown
    assert "- precision: 0.8000" in markdown
    assert "clip_01" in markdown
    assert "dominant_state=fall" in markdown
    assert "confirmed_fall" in markdown


def test_summarize_expected_states_tracks_normal_false_positives() -> None:
    summary = summarize_expected_states(
        [
            {"expected_state": "normal", "incident_total": 1, "dominant_state": "fall"},
            {"expected_state": "normal", "incident_total": 0, "dominant_state": "normal"},
            {"expected_state": "fall", "incident_total": 0, "dominant_state": "normal"},
        ]
    )

    assert summary["with_expected_state"] == 3
    assert summary["expected_normal_total"] == 2
    assert summary["expected_normal_with_incidents"] == 1
    assert summary["expected_normal_dominant_non_normal"] == 1
    assert summary["expected_normal_incident_rate"] == 0.5
    assert summary["expected_positive_total"] == 1
    assert summary["expected_positive_without_incidents"] == 1
    assert summary["expected_positive_dominant_normal"] == 1
