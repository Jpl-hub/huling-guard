import json

from huling_guard.evaluation import (
    EventRecord,
    load_annotation_events,
    load_prediction_events,
    summarize_event_detection,
)


def test_summarize_event_detection_matches_events_and_counts_false_positives() -> None:
    summary = summarize_event_detection(
        ground_truth_events=[
            EventRecord(kind="confirmed_fall", timestamp=10.0),
            EventRecord(kind="prolonged_lying", timestamp=25.0),
        ],
        predicted_events=[
            EventRecord(kind="confirmed_fall", timestamp=10.8, confidence=0.93),
            EventRecord(kind="confirmed_fall", timestamp=42.0, confidence=0.71),
            EventRecord(kind="prolonged_lying", timestamp=24.3, confidence=0.88),
        ],
        tolerance_seconds=2.0,
        duration_seconds=120.0,
    )

    assert summary["tp"] == 2
    assert summary["fp"] == 1
    assert summary["fn"] == 0
    assert round(summary["precision"], 6) == round(2 / 3, 6)
    assert round(summary["recall"], 6) == 1.0
    assert round(summary["false_positives_per_hour"], 6) == 30.0
    assert summary["per_kind"]["confirmed_fall"]["fp"] == 1
    assert round(summary["per_kind"]["prolonged_lying"]["mean_abs_delay_seconds"], 6) == 0.7


def test_event_loaders_parse_annotation_json_and_prediction_jsonl(tmp_path) -> None:
    annotation_path = tmp_path / "annotations.json"
    prediction_path = tmp_path / "predictions.jsonl"

    annotation_path.write_text(
        json.dumps(
            {
                "video_id": "clip_001",
                "duration_seconds": 18.0,
                "events": [
                    {"kind": "near_fall_warning", "timestamp": 5.0},
                    {"kind": "confirmed_fall", "timestamp": 9.5},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prediction_lines = [
        {
            "timestamp": 4.0,
            "incidents": [],
        },
        {
            "timestamp": 5.1,
            "incidents": [
                {"kind": "near_fall_warning", "timestamp": 5.1, "confidence": 0.62},
            ],
        },
        {
            "timestamp": 9.6,
            "incidents": [
                {"kind": "confirmed_fall", "timestamp": 9.6, "confidence": 0.91},
                {"kind": "confirmed_fall", "timestamp": 9.6, "confidence": 0.91},
            ],
        },
    ]
    prediction_path.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in prediction_lines) + "\n",
        encoding="utf-8",
    )

    annotations, duration_seconds = load_annotation_events(annotation_path)
    predictions, inferred_duration = load_prediction_events(prediction_path)

    assert duration_seconds == 18.0
    assert inferred_duration == 9.6
    assert [event.kind for event in annotations] == ["near_fall_warning", "confirmed_fall"]
    assert len(predictions) == 2
    assert predictions[0].confidence == 0.62
