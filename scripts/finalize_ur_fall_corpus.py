from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


def _count_jsonl_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()

    processed_root = data_root / "processed"
    work_root = processed_root / "parallel_extract_ur_fall"
    shard_manifest_dir = work_root / "pose_manifests"
    output_manifest = processed_root / "poses_ur_fall.jsonl"
    valid_manifest = data_root / "manifests" / "ur_fall_valid.jsonl"
    invalid_manifest = data_root / "manifests" / "ur_fall_invalid.jsonl"

    subprocess.run(
        [
            args.python,
            "scripts/finalize_parallel_pose_extraction.py",
            "--base-manifest",
            str(output_manifest),
            "--shard-manifest-dir",
            str(shard_manifest_dir),
            "--output",
            str(output_manifest),
        ],
        cwd=repo_root,
        check=True,
    )

    summary = {
        "dataset": "ur_fall",
        "output_manifest": str(output_manifest),
        "valid_rows": _count_jsonl_rows(valid_manifest),
        "invalid_rows": _count_jsonl_rows(invalid_manifest),
        "pose_rows": _count_jsonl_rows(output_manifest),
        "shard_manifest_dir": str(shard_manifest_dir),
    }
    summary_path = data_root / "manifests" / "ur_fall_finalize_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[summary] {summary_path}", flush=True)


if __name__ == "__main__":
    main()
