from pathlib import Path

from huling_guard.data.clip_bundle import export_clip_bundle_manifest
from huling_guard.data.manifests import load_jsonl, merge_jsonl_manifests, normalize_internal_label, write_jsonl
from huling_guard.data.splits import split_manifest_by_subject, split_pose_manifest_by_raw_split


def test_subject_split_and_pose_filter(tmp_path: Path) -> None:
    raw_rows = [
        {"sample_id": "a", "metadata": {"subject": 1}},
        {"sample_id": "b", "metadata": {"subject": 2}},
        {"sample_id": "c", "metadata": {"subject": 1}},
    ]
    pose_rows = [
        {"sample_id": "a", "pose_path": "a.npz"},
        {"sample_id": "b", "pose_path": "b.npz"},
        {"sample_id": "c", "pose_path": "c.npz"},
    ]
    raw_path = tmp_path / "raw.jsonl"
    pose_path = tmp_path / "pose.jsonl"
    write_jsonl(raw_path, raw_rows)
    write_jsonl(pose_path, pose_rows)

    raw_train = tmp_path / "raw_train.jsonl"
    raw_val = tmp_path / "raw_val.jsonl"
    pose_train = tmp_path / "pose_train.jsonl"
    pose_val = tmp_path / "pose_val.jsonl"

    result = split_manifest_by_subject(
        input_path=raw_path,
        train_output_path=raw_train,
        val_output_path=raw_val,
        val_subjects={"2"},
    )
    assert result.train_count == 2
    assert result.val_count == 1

    filtered = split_pose_manifest_by_raw_split(
        raw_train_path=raw_train,
        raw_val_path=raw_val,
        pose_manifest_path=pose_path,
        train_output_path=pose_train,
        val_output_path=pose_val,
    )
    assert filtered.train_count == 2
    assert filtered.val_count == 1
    assert [row["sample_id"] for row in load_jsonl(pose_val)] == ["b"]


def test_merge_manifests_dedupes_by_sample_id(tmp_path: Path) -> None:
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    output = tmp_path / "merged.jsonl"

    write_jsonl(left, [{"sample_id": "a"}, {"sample_id": "b"}])
    write_jsonl(right, [{"sample_id": "b"}, {"sample_id": "c"}])

    written = merge_jsonl_manifests([left, right], output_path=output)
    assert written == 3
    assert [row["sample_id"] for row in load_jsonl(output)] == ["a", "b", "c"]


def test_normalize_internal_label_uses_external_label() -> None:
    row = {
        "sample_id": "lying_sample",
        "external_label": "lying",
        "internal_label": "normal",
    }
    normalized = normalize_internal_label(row)
    assert normalized["internal_label"] == "prolonged_lying"


def test_merge_manifests_rewrites_internal_label_from_external_label(tmp_path: Path) -> None:
    left = tmp_path / "left.jsonl"
    output = tmp_path / "merged.jsonl"

    write_jsonl(
        left,
        [
            {
                "sample_id": "lying_sample",
                "external_label": "lying",
                "internal_label": "normal",
            }
        ],
    )

    written = merge_jsonl_manifests([left], output_path=output)
    assert written == 1
    rows = load_jsonl(output)
    assert rows[0]["internal_label"] == "prolonged_lying"


def test_subject_split_supports_dataset_subject_identity(tmp_path: Path) -> None:
    raw_rows = [
        {"sample_id": "a", "metadata": {"dataset": "caucafall", "subject": 1}},
        {"sample_id": "b", "metadata": {"dataset": "up_fall", "subject": 1}},
        {"sample_id": "c", "metadata": {"dataset": "up_fall", "subject": 2}},
    ]
    raw_path = tmp_path / "raw.jsonl"
    write_jsonl(raw_path, raw_rows)

    train_path = tmp_path / "train.jsonl"
    val_path = tmp_path / "val.jsonl"
    result = split_manifest_by_subject(
        input_path=raw_path,
        train_output_path=train_path,
        val_output_path=val_path,
        val_subjects={"up_fall:1"},
        subject_key="dataset_subject",
    )

    assert result.train_count == 2
    assert result.val_count == 1
    assert [row["sample_id"] for row in load_jsonl(val_path)] == ["b"]


def test_prepare_clip_bundle_without_csv_uses_filename_schema(tmp_path: Path) -> None:
    clips_root = tmp_path / "clips"
    subject_dir = clips_root / "Subject.1"
    subject_dir.mkdir(parents=True)
    clip_path = subject_dir / "Subject1Activity1Trial1Camera1_1_2.894_4.994_1_1_up_fall.avi"
    clip_path.write_bytes(b"")
    output = tmp_path / "manifest.jsonl"

    written = export_clip_bundle_manifest(
        csv_path=None,
        clips_root=clips_root,
        output_path=output,
    )

    assert written == 1
    rows = load_jsonl(output)
    assert rows[0]["external_label"] == "fall"
    assert rows[0]["internal_label"] == "fall"
    assert rows[0]["metadata"]["dataset"] == "up_fall"
    assert rows[0]["metadata"]["subject"] == 1
