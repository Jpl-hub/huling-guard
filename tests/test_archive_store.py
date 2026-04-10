import json

from huling_guard.runtime.archive_store import RuntimeArchiveStore


def _build_report() -> dict[str, object]:
    return {
        "session_name": "fall_01_demo",
        "source_path": "runtime://demo/fall_01_demo",
        "total_frames": 120,
        "ready_frames": 96,
        "warmup_frames": 24,
        "ready_ratio": 0.8,
        "start_timestamp": 0.0,
        "end_timestamp": 4.0,
        "duration_seconds": 4.0,
        "peak_risk": {
            "timestamp": 2.1,
            "predicted_state": "fall",
            "risk_score": 0.97,
            "confidence": 0.94,
        },
        "mean_risk_score": 0.48,
        "mean_confidence": 0.72,
        "dominant_state": "fall",
        "predicted_state_counts": {"fall": 60, "normal": 36},
        "incident_total": 1,
        "incident_counts": {"confirmed_fall": 1},
        "first_incident": {"kind": "confirmed_fall", "timestamp": 2.0, "confidence": 0.91, "payload": {}},
        "last_incident": {"kind": "confirmed_fall", "timestamp": 2.0, "confidence": 0.91, "payload": {}},
        "recent_incidents": [
            {"kind": "confirmed_fall", "timestamp": 2.0, "confidence": 0.91, "payload": {}},
        ],
        "top_risk_moments": [
            {"timestamp": 2.1, "predicted_state": "fall", "risk_score": 0.97, "confidence": 0.94},
        ],
        "state_segments": [
            {
                "state": "fall",
                "start_timestamp": 1.8,
                "end_timestamp": 2.6,
                "duration_seconds": 0.8,
                "frame_count": 18,
                "max_risk_score": 0.97,
                "max_confidence": 0.94,
            }
        ],
        "longest_segments": [
            {
                "state": "fall",
                "start_timestamp": 1.8,
                "end_timestamp": 2.6,
                "duration_seconds": 0.8,
                "frame_count": 18,
                "max_risk_score": 0.97,
                "max_confidence": 0.94,
            }
        ],
    }


def test_archive_store_deduplicates_same_report(tmp_path) -> None:
    store = RuntimeArchiveStore(tmp_path / "archive")
    report = _build_report()

    first = store.archive_report(report)
    second = store.archive_report(report)

    assert first["session_id"] == second["session_id"]
    archives = store.list_archives()
    assert len(archives) == 1
    assert archives[0]["session_name"] == "fall_01_demo"


def test_archive_store_imports_existing_session_reports(tmp_path) -> None:
    archive_root = tmp_path / "archive"
    reports_root = tmp_path / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)
    report_path = reports_root / "fall_01_demo.json"
    report_path.write_text(
        json.dumps(_build_report(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    store = RuntimeArchiveStore(archive_root)
    first_summary = store.import_report_files([reports_root])
    second_summary = store.import_report_files([reports_root])

    assert first_summary["imported_count"] == 1
    assert first_summary["skipped_count"] == 0
    assert first_summary["error_count"] == 0
    assert second_summary["imported_count"] == 0
    assert second_summary["skipped_count"] == 1
    assert second_summary["error_count"] == 0

    archives = store.list_archives()
    assert len(archives) == 1
    report = store.load_archive_report(archives[0]["session_id"])
    assert report["session_name"] == "fall_01_demo"
    assert report["dominant_state"] == "fall"
