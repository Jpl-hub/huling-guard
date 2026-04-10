import json
from pathlib import Path
import subprocess
import sys


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def test_finalize_parallel_pose_extraction_handles_missing_base_manifest(tmp_path: Path) -> None:
    shard_dir = tmp_path / "pose_manifests"
    output_path = tmp_path / "poses.jsonl"
    _write_jsonl(shard_dir / "poses_shard_00.jsonl", [{"sample_id": "a"}, {"sample_id": "b"}])
    _write_jsonl(shard_dir / "poses_shard_01.jsonl", [{"sample_id": "b"}, {"sample_id": "c"}])

    subprocess.run(
        [
            sys.executable,
            "scripts/finalize_parallel_pose_extraction.py",
            "--base-manifest",
            str(tmp_path / "missing.jsonl"),
            "--shard-manifest-dir",
            str(shard_dir),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    payload = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [row["sample_id"] for row in payload] == ["a", "b", "c"]
