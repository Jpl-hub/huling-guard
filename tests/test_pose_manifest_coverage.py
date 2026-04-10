from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from huling_guard.data import export_missing_pose_entries, summarize_pose_manifest_coverage


def test_summarize_pose_manifest_coverage_reports_missing_and_extra(tmp_path: Path) -> None:
    raw_manifest = tmp_path / "raw.jsonl"
    pose_manifest = tmp_path / "pose.jsonl"
    raw_manifest.write_text(
        '{"sample_id":"a"}\n{"sample_id":"b"}\n',
        encoding="utf-8",
    )
    pose_manifest.write_text(
        '{"sample_id":"a"}\n{"sample_id":"c"}\n',
        encoding="utf-8",
    )

    summary = summarize_pose_manifest_coverage(raw_manifest, pose_manifest)

    assert summary.raw_count == 2
    assert summary.pose_count == 2
    assert summary.matched_count == 1
    assert summary.missing_pose_count == 1
    assert summary.extra_pose_count == 1
    assert summary.missing_pose_sample_ids == ["b"]
    assert summary.extra_pose_sample_ids == ["c"]
    assert summary.coverage_ratio == 0.5


def test_export_missing_pose_entries_writes_missing_raw_rows(tmp_path: Path) -> None:
    raw_manifest = tmp_path / "raw.jsonl"
    pose_manifest = tmp_path / "pose.jsonl"
    output_manifest = tmp_path / "missing.jsonl"
    raw_manifest.write_text(
        '{"sample_id":"a","video_ref":"a.mp4"}\n{"sample_id":"b","video_ref":"b.mp4"}\n',
        encoding="utf-8",
    )
    pose_manifest.write_text(
        '{"sample_id":"a","pose_path":"a.npz"}\n',
        encoding="utf-8",
    )

    summary = export_missing_pose_entries(raw_manifest, pose_manifest, output_manifest)

    assert summary.missing_pose_sample_ids == ["b"]
    assert output_manifest.read_text(encoding="utf-8").strip() == '{"sample_id": "b", "video_ref": "b.mp4"}'
