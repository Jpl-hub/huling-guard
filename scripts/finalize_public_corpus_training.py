from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    print("[run]", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--base-up-fall-manifest",
        type=Path,
        default=Path("/root/autodl-tmp/huling-data/processed/poses_up_fall.jsonl"),
    )
    parser.add_argument(
        "--parallel-shard-dir",
        type=Path,
        default=Path("/root/autodl-tmp/huling-data/parallel_up_fall/pose_manifests"),
    )
    parser.add_argument(
        "--merged-up-fall-manifest",
        type=Path,
        default=Path("/root/autodl-tmp/huling-data/processed/poses_up_fall_merged.jsonl"),
    )
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--run-name", default="public_merged")
    parser.add_argument("--runtime-config-template", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS") or "8"
    env["MKL_NUM_THREADS"] = env.get("MKL_NUM_THREADS") or "8"
    env["OPENBLAS_NUM_THREADS"] = env.get("OPENBLAS_NUM_THREADS") or "1"
    env["NUMEXPR_NUM_THREADS"] = env.get("NUMEXPR_NUM_THREADS") or "1"

    _run(
        [
            args.python,
            "scripts/finalize_parallel_pose_extraction.py",
            "--base-manifest",
            str(args.base_up_fall_manifest.resolve()),
            "--shard-manifest-dir",
            str(args.parallel_shard_dir.resolve()),
            "--output",
            str(args.merged_up_fall_manifest.resolve()),
        ],
        cwd=repo_root,
        env=env,
    )

    if args.train:
        train_command = [
            args.python,
            "scripts/run_public_corpus_training.py",
            "--python",
            args.python,
            "--repo-root",
            str(repo_root),
            "--up-fall-pose-manifest",
            str(args.merged_up_fall_manifest.resolve()),
            "--run-name",
            args.run_name,
            "--train",
        ]
        if args.runtime_config_template is not None:
            train_command.extend(
                ["--runtime-config-template", str(args.runtime_config_template.resolve())]
            )
        _run(
            train_command,
            cwd=repo_root,
            env=env,
        )


if __name__ == "__main__":
    main()
