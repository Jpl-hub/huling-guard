import json

from huling_guard.evaluation import load_event_evaluation_manifest, summarize_event_corpus


def test_summarize_event_corpus_aggregates_clip_metrics(tmp_path) -> None:
    annotation_a = tmp_path / "ann_a.json"
    annotation_b = tmp_path / "ann_b.json"
    prediction_a = tmp_path / "pred_a.jsonl"
    prediction_b = tmp_path / "pred_b.jsonl"
    manifest_path = tmp_path / "corpus.json"

    annotation_a.write_text(
        json.dumps(
            {
                "video_id": "clip_a",
                "duration_seconds": 20.0,
                "events": [
                    {"kind": "confirmed_fall", "timestamp": 8.0},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    annotation_b.write_text(
        json.dumps(
            {
                "video_id": "clip_b",
                "duration_seconds": 40.0,
                "events": [
                    {"kind": "near_fall_warning", "timestamp": 5.0},
                    {"kind": "confirmed_fall", "timestamp": 14.0},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prediction_a.write_text(
        "\n".join(
            [
                json.dumps({"timestamp": 8.5, "incidents": [{"kind": "confirmed_fall", "timestamp": 8.5}]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    prediction_b.write_text(
        "\n".join(
            [
                json.dumps({"timestamp": 4.6, "incidents": [{"kind": "near_fall_warning", "timestamp": 4.6}]}),
                json.dumps({"timestamp": 30.0, "incidents": [{"kind": "confirmed_fall", "timestamp": 30.0}]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "clip_id": "clip_a",
                        "predictions": "pred_a.jsonl",
                        "annotations": "ann_a.json",
                    },
                    {
                        "clip_id": "clip_b",
                        "predictions": "pred_b.jsonl",
                        "annotations": "ann_b.json",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    clips = load_event_evaluation_manifest(manifest_path)
    summary = summarize_event_corpus(clips, tolerance_seconds=2.0)

    assert summary["clip_count"] == 2
    assert summary["tp"] == 2
    assert summary["fp"] == 1
    assert summary["fn"] == 1
    assert round(summary["precision"], 6) == round(2 / 3, 6)
    assert round(summary["recall"], 6) == round(2 / 3, 6)
    assert round(summary["false_positives_per_hour"], 6) == 60.0
    assert summary["per_kind"]["confirmed_fall"]["tp"] == 1
    assert summary["per_kind"]["confirmed_fall"]["fn"] == 1
    assert summary["per_kind"]["near_fall_warning"]["tp"] == 1
