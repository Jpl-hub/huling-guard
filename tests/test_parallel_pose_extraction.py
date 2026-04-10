import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_parallel_pose_extraction import collect_completed_sample_ids, merge_pose_manifests


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def test_collect_completed_sample_ids_merges_base_and_shards(tmp_path: Path) -> None:
    merged_manifest = tmp_path / "poses.jsonl"
    shard_dir = tmp_path / "pose_manifests"

    _write_jsonl(merged_manifest, [{"sample_id": "a"}, {"sample_id": "b"}])
    _write_jsonl(shard_dir / "poses_shard_00.jsonl", [{"sample_id": "b"}, {"sample_id": "c"}])
    _write_jsonl(shard_dir / "poses_shard_01.jsonl", [{"sample_id": "d"}])

    completed_ids, counts = collect_completed_sample_ids(
        merged_output_manifest=merged_manifest,
        shard_manifest_dir=shard_dir,
    )

    assert completed_ids == {"a", "b", "c", "d"}
    assert counts["merged_manifest_rows"] == 2
    assert counts["shard_manifest_rows"] == 3


def test_collect_completed_sample_ids_handles_missing_inputs(tmp_path: Path) -> None:
    completed_ids, counts = collect_completed_sample_ids(
        merged_output_manifest=tmp_path / "missing.jsonl",
        shard_manifest_dir=tmp_path / "missing_dir",
    )

    assert completed_ids == set()
    assert counts["merged_manifest_rows"] == 0
    assert counts["shard_manifest_rows"] == 0


def test_merge_pose_manifests_merges_base_and_shards_without_duplicates(tmp_path: Path) -> None:
    merged_manifest = tmp_path / "poses.jsonl"
    shard_dir = tmp_path / "pose_manifests"

    _write_jsonl(merged_manifest, [{"sample_id": "a"}, {"sample_id": "b"}])
    _write_jsonl(shard_dir / "poses_shard_00.jsonl", [{"sample_id": "b"}, {"sample_id": "c"}])
    _write_jsonl(shard_dir / "poses_shard_01.jsonl", [{"sample_id": "d"}])

    rows = merge_pose_manifests(
        merged_output_manifest=merged_manifest,
        shard_manifest_dir=shard_dir,
    )

    assert rows == 4
    merged_payload = [json.loads(line) for line in merged_manifest.read_text(encoding="utf-8").splitlines()]
    assert [row["sample_id"] for row in merged_payload] == ["a", "b", "c", "d"]
