import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_sample_review_queue import build_sample_review_queue, build_markdown
from export_interval_labels import export_interval_labels


def _build_pose_clip(num_frames: int) -> np.ndarray:
    clip = np.zeros((num_frames, 17, 3), dtype=np.float32)
    clip[:, :, 2] = 1.0
    return clip


def test_build_sample_review_queue_exports_full_sample_candidates(tmp_path: Path) -> None:
    pose_path = tmp_path / "sample_pose.npz"
    np.savez(
        pose_path,
        keypoints=_build_pose_clip(5),
        timestamps=np.asarray([0.0, 0.5, 1.0, 1.5, 2.0], dtype=np.float32),
    )

    sample_manifest = tmp_path / "sample_manifest.jsonl"
    sample_manifest.write_text(
        json.dumps(
            {
                "sample_id": "sample_a",
                "pose_path": str(pose_path),
                "num_frames": 5,
                "internal_label": "recovery",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    sample_summary = tmp_path / "sample_summary.json"
    sample_summary.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "sample_id": "sample_a",
                        "label_id": 3,
                        "predicted_id": 2,
                        "label_name": "recovery",
                        "predicted_name": "fall",
                        "mean_probs": [0.01, 0.0, 0.91, 0.08, 0.0],
                        "window_count": 2,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    queue = build_sample_review_queue(
        sample_summary,
        sample_manifest,
        top_k=10,
    )

    assert queue["clip_count"] == 1
    clip = queue["clips"][0]
    assert clip["sample_id"] == "sample_a"
    assert clip["predicted_name"] == "fall"
    assert clip["candidates"][0]["start_time"] == 0.0
    assert clip["candidates"][0]["end_time"] == 2.0
    assert "sample_confusion:recovery->fall" in clip["candidates"][0]["reason"]

    clip["candidates"][0]["status"] = "approved"
    clip["candidates"][0]["accepted_label"] = "recovery"
    review_queue_path = tmp_path / "review_queue.json"
    review_queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")

    intervals = export_interval_labels(review_queue_path)
    assert len(intervals["intervals"]) == 1
    assert intervals["intervals"][0]["sample_id"] == "sample_a"
    assert intervals["intervals"][0]["start_time"] == 0.0
    assert intervals["intervals"][0]["end_time"] == 2.0
    assert intervals["intervals"][0]["label"] == "recovery"


def test_build_sample_review_queue_markdown_lists_items(tmp_path: Path) -> None:
    sample_manifest = tmp_path / "sample_manifest.jsonl"
    sample_manifest.write_text("", encoding="utf-8")
    sample_summary = tmp_path / "sample_summary.json"
    sample_summary.write_text(json.dumps({"samples": []}, ensure_ascii=False), encoding="utf-8")

    queue = build_sample_review_queue(sample_summary, sample_manifest, top_k=5)
    markdown = build_markdown(queue)

    assert "# 样本级复查队列" in markdown
    assert "- clip_count: 0" in markdown


def test_build_sample_review_queue_accepts_nested_checkpoint_eval_payload(tmp_path: Path) -> None:
    pose_path = tmp_path / "sample_pose.npz"
    np.savez(
        pose_path,
        keypoints=_build_pose_clip(4),
        timestamps=np.asarray([0.0, 0.5, 1.0, 1.5], dtype=np.float32),
    )

    sample_manifest = tmp_path / "sample_manifest.jsonl"
    sample_manifest.write_text(
        json.dumps(
            {
                "sample_id": "sample_b",
                "pose_path": str(pose_path),
                "num_frames": 4,
                "internal_label": "prolonged_lying",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    sample_summary = tmp_path / "checkpoint_eval.json"
    sample_summary.write_text(
        json.dumps(
            {
                "window": {"accuracy": 0.0},
                "sample": {
                    "samples": [
                        {
                            "sample_id": "sample_b",
                            "label_id": 4,
                            "predicted_id": 0,
                            "label_name": "prolonged_lying",
                            "predicted_name": "normal",
                            "mean_probs": [0.88, 0.01, 0.0, 0.0, 0.11],
                            "window_count": 1,
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    queue = build_sample_review_queue(
        sample_summary,
        sample_manifest,
        top_k=10,
    )

    assert queue["clip_count"] == 1
    assert queue["clips"][0]["sample_id"] == "sample_b"
    assert queue["clips"][0]["predicted_name"] == "normal"
