import json

from huling_guard.runtime.session_report import (
    build_session_report,
    format_session_report_markdown,
    summarize_session_jsonl,
)


def test_build_session_report_computes_core_metrics() -> None:
    snapshots = [
        {
            "timestamp": 0.0,
            "ready": False,
            "observed_frames": 1,
            "window_size": 64,
            "window_span_seconds": 0.0,
            "state_probs": {},
            "predicted_state": None,
            "confidence": 0.0,
            "risk_score": 0.0,
            "incidents": [],
        },
        {
            "timestamp": 2.0,
            "ready": True,
            "observed_frames": 64,
            "window_size": 64,
            "window_span_seconds": 2.0,
            "state_probs": {"fall": 0.7},
            "predicted_state": "fall",
            "confidence": 0.7,
            "risk_score": 0.81,
            "incidents": [
                {
                    "kind": "confirmed_fall",
                    "timestamp": 2.0,
                    "confidence": 0.91,
                    "payload": {"source": "test"},
                }
            ],
        },
        {
            "timestamp": 4.5,
            "ready": True,
            "observed_frames": 64,
            "window_size": 64,
            "window_span_seconds": 2.5,
            "state_probs": {"prolonged_lying": 0.8},
            "predicted_state": "prolonged_lying",
            "confidence": 0.8,
            "risk_score": 0.92,
            "incidents": [
                {
                    "kind": "prolonged_lying",
                    "timestamp": 4.5,
                    "confidence": 0.88,
                    "payload": {},
                }
            ],
        },
    ]

    report = build_session_report(
        snapshots=snapshots,
        session_name="demo_session",
        source_path="demo.mp4",
    )

    assert report["session_name"] == "demo_session"
    assert report["source_path"] == "demo.mp4"
    assert report["total_frames"] == 3
    assert report["ready_frames"] == 2
    assert report["warmup_frames"] == 1
    assert report["dominant_state"] in {"fall", "prolonged_lying"}
    assert report["incident_total"] == 2
    assert report["incident_counts"]["confirmed_fall"] == 1
    assert report["peak_risk"]["risk_score"] == 0.92
    assert report["longest_segments"][0]["state"] in {"fall", "prolonged_lying"}


def test_format_session_report_markdown_contains_key_sections() -> None:
    report = {
        "session_name": "demo_session",
        "source_path": "demo.mp4",
        "total_frames": 100,
        "ready_frames": 60,
        "warmup_frames": 40,
        "ready_ratio": 0.6,
        "duration_seconds": 12.5,
        "dominant_state": "normal",
        "mean_risk_score": 0.22,
        "mean_confidence": 0.71,
        "peak_risk": {"predicted_state": "fall", "risk_score": 0.91, "timestamp": 8.0},
        "predicted_state_counts": {"normal": 40, "fall": 20},
        "incident_total": 1,
        "incident_counts": {"confirmed_fall": 1},
        "longest_segments": [
            {
                "state": "normal",
                "start_timestamp": 1.0,
                "end_timestamp": 5.0,
                "duration_seconds": 4.0,
                "frame_count": 24,
                "max_risk_score": 0.3,
            }
        ],
        "recent_incidents": [{"kind": "confirmed_fall", "timestamp": 8.0, "confidence": 0.91}],
    }

    markdown = format_session_report_markdown(report)

    assert "# 会话报告" in markdown
    assert "## 风险摘要" in markdown
    assert "- 主导状态: normal" in markdown
    assert "confirmed_fall" in markdown


def test_summarize_session_jsonl_reads_prediction_stream(tmp_path) -> None:
    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": 0.0,
                        "ready": False,
                        "observed_frames": 1,
                        "window_size": 64,
                        "window_span_seconds": 0.0,
                        "state_probs": {},
                        "predicted_state": None,
                        "confidence": 0.0,
                        "risk_score": 0.0,
                        "incidents": [],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": 3.2,
                        "ready": True,
                        "observed_frames": 64,
                        "window_size": 64,
                        "window_span_seconds": 2.4,
                        "state_probs": {"fall": 0.77},
                        "predicted_state": "fall",
                        "confidence": 0.77,
                        "risk_score": 0.88,
                        "incidents": [
                            {
                                "kind": "confirmed_fall",
                                "timestamp": 3.2,
                                "confidence": 0.9,
                                "payload": {},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = summarize_session_jsonl(predictions_path=predictions_path)

    assert report["session_name"] == "predictions"
    assert report["total_frames"] == 2
    assert report["incident_counts"]["confirmed_fall"] == 1
