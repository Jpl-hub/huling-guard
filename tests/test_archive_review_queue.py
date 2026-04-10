import json
from pathlib import Path

from huling_guard.review import build_archive_review_queue, build_video_batch_manifest


def test_build_video_batch_manifest_carries_expected_state(tmp_path: Path) -> None:
    source_manifest = tmp_path / "source.jsonl"
    source_manifest.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "sample_id": "ur_fall__adl_01",
                        "video_ref": "/data/adl-01.mp4",
                        "internal_label": "normal",
                        "metadata": {"dataset": "ur_fall"},
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "sample_id": "ur_fall__fall_01",
                        "video_ref": "/data/fall-01.mp4",
                        "internal_label": "fall",
                        "metadata": {"dataset": "ur_fall"},
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_video_batch_manifest(
        source_manifest,
        internal_labels=("normal",),
        dataset="ur_fall",
    )

    assert len(payload["clips"]) == 1
    assert payload["clips"][0]["sample_id"] == "ur_fall__adl_01"
    assert payload["clips"][0]["expected_state"] == "normal"
    assert payload["clips"][0]["expected_incident"] is False


def test_build_archive_review_queue_extracts_normal_false_positive_segments(tmp_path: Path) -> None:
    video_path = (tmp_path / "adl-01.mp4").resolve()
    processed_manifest = tmp_path / "processed_manifest.json"
    session_report = tmp_path / "adl-01_report.json"
    session_report.write_text(
        json.dumps(
            {
                "duration_seconds": 8.0,
                "dominant_state": "normal",
                "incident_total": 1,
                "state_segments": [
                    {
                        "state": "normal",
                        "start_timestamp": 0.0,
                        "end_timestamp": 2.0,
                        "duration_seconds": 2.0,
                        "frame_count": 10,
                        "max_risk_score": 0.2,
                        "max_confidence": 0.9,
                    },
                    {
                        "state": "fall",
                        "start_timestamp": 2.0,
                        "end_timestamp": 3.4,
                        "duration_seconds": 1.4,
                        "frame_count": 6,
                        "max_risk_score": 0.95,
                        "max_confidence": 0.92,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    processed_manifest.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "clip_id": "adl_01_archive",
                        "sample_id": None,
                        "expected_state": None,
                        "input": str(video_path),
                        "session_report_json": str(session_report),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    reference_manifest = tmp_path / "reference.jsonl"
    reference_manifest.write_text(
        json.dumps(
            {
                "sample_id": "ur_fall__adl_01",
                "video_ref": str(video_path),
                "internal_label": "normal",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    queue = build_archive_review_queue(
        processed_manifest,
        reference_manifest_path=reference_manifest,
        auto_approve=True,
        top_k=10,
    )

    assert queue["clip_count"] == 1
    clip = queue["clips"][0]
    assert clip["sample_id"] == "ur_fall__adl_01"
    assert clip["expected_state"] == "normal"
    assert clip["incident_total"] == 1
    assert len(clip["candidates"]) == 1
    candidate = clip["candidates"][0]
    assert candidate["recommended_label"] == "normal"
    assert candidate["accepted_label"] == "normal"
    assert candidate["status"] == "approved"
    assert candidate["start_time"] == 2.0
    assert candidate["end_time"] == 3.4


def test_build_archive_review_queue_can_limit_to_dominant_drift(tmp_path: Path) -> None:
    video_a = (tmp_path / "adl-a.mp4").resolve()
    video_b = (tmp_path / "adl-b.mp4").resolve()
    report_a = tmp_path / "adl-a_report.json"
    report_b = tmp_path / "adl-b_report.json"
    report_a.write_text(
        json.dumps(
            {
                "duration_seconds": 6.0,
                "dominant_state": "fall",
                "incident_total": 2,
                "state_segments": [
                    {
                        "state": "fall",
                        "start_timestamp": 1.0,
                        "end_timestamp": 3.0,
                        "duration_seconds": 2.0,
                        "max_confidence": 0.93,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_b.write_text(
        json.dumps(
            {
                "duration_seconds": 6.0,
                "dominant_state": "normal",
                "incident_total": 1,
                "state_segments": [
                    {
                        "state": "fall",
                        "start_timestamp": 2.0,
                        "end_timestamp": 2.6,
                        "duration_seconds": 0.6,
                        "max_confidence": 0.91,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    processed_manifest = tmp_path / "processed_manifest.json"
    processed_manifest.write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "clip_id": "adl_a",
                        "sample_id": "ur_fall__adl_a",
                        "expected_state": "normal",
                        "input": str(video_a),
                        "session_report_json": str(report_a),
                    },
                    {
                        "clip_id": "adl_b",
                        "sample_id": "ur_fall__adl_b",
                        "expected_state": "normal",
                        "input": str(video_b),
                        "session_report_json": str(report_b),
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    queue = build_archive_review_queue(
        processed_manifest,
        dominant_drift_only=True,
        min_incident_total=1,
        top_k=10,
    )

    assert queue["clip_count"] == 1
    assert queue["clips"][0]["clip_id"] == "adl_a"
    assert queue["clips"][0]["dominant_state"] == "fall"
