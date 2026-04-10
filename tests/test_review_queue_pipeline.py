import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_hard_case_review_queue import build_review_queue

from huling_guard.review import export_review_intervals


def test_review_queue_and_interval_export_pipeline(tmp_path: Path) -> None:
    hard_cases_path = tmp_path / "hard_cases.json"
    hard_cases_path.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "clip_id": "clip_01",
                        "sample_id": "public__clip_01",
                        "input": "videos/clip_01.mp4",
                        "predictions": "predictions/clip_01.jsonl",
                        "duration_seconds": 12.0,
                        "hard_score": 0.81,
                        "max_state_probs": {
                            "near_fall": 0.74,
                            "fall": 0.22,
                            "recovery": 0.61,
                            "prolonged_lying": 0.1,
                        },
                        "first_high_confidence_ts": {
                            "near_fall": 4.0,
                            "fall": None,
                            "recovery": 9.0,
                            "prolonged_lying": None,
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    queue = build_review_queue(hard_cases_path, top_k=10, min_state_probability=0.55)
    assert queue["clip_count"] == 1
    assert len(queue["clips"][0]["candidates"]) == 2

    queue["clips"][0]["candidates"][0]["status"] = "approved"
    queue["clips"][0]["candidates"][0]["accepted_label"] = "near_fall"
    review_queue_path = tmp_path / "review_queue.json"
    review_queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")

    intervals = export_review_intervals(review_queue_path)
    assert intervals["skipped_without_sample"] == 0
    assert len(intervals["intervals"]) == 1
    assert intervals["intervals"][0]["sample_id"] == "public__clip_01"
    assert intervals["intervals"][0]["label"] == "near_fall"
