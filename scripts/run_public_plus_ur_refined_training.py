from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    parser.add_argument("--run-name", default="public_plus_ur_refined")
    parser.add_argument("--window-size", type=int, default=64)
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--kinematic-feature-set", default="v2")
    parser.add_argument("--clip-focal-gamma", type=float, default=0.0)
    parser.add_argument("--runtime-config-template", type=Path, default=Path("configs/runtime_room.yaml"))
    parser.add_argument("--train-interval-labels", type=Path, required=True)
    parser.add_argument("--eval-interval-labels", type=Path)
    parser.add_argument("--interval-min-overlap", type=float, default=0.5)
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    runtime_template = args.runtime_config_template
    if not runtime_template.is_absolute():
        runtime_template = (repo_root / runtime_template).resolve()

    train_interval_labels = args.train_interval_labels
    if not train_interval_labels.is_absolute():
        train_interval_labels = (repo_root / train_interval_labels).resolve()
    eval_interval_labels = args.eval_interval_labels
    if eval_interval_labels is not None and not eval_interval_labels.is_absolute():
        eval_interval_labels = (repo_root / eval_interval_labels).resolve()

    command = [
        args.python,
        "scripts/run_public_plus_ur_training.py",
        "--python",
        args.python,
        "--repo-root",
        str(repo_root),
        "--data-root",
        str(args.data_root.resolve()),
        "--run-name",
        args.run_name,
        "--window-size",
        str(args.window_size),
        "--stride",
        str(args.stride),
        "--seed",
        str(args.seed),
        "--kinematic-feature-set",
        args.kinematic_feature_set,
        "--clip-focal-gamma",
        str(args.clip_focal_gamma),
        "--runtime-config-template",
        str(runtime_template),
        "--train-interval-labels",
        str(train_interval_labels),
        "--interval-min-overlap",
        str(args.interval_min_overlap),
    ]
    if eval_interval_labels is not None:
        command.extend(["--eval-interval-labels", str(eval_interval_labels)])
    if args.train:
        command.append("--train")

    print("[run]", " ".join(command), flush=True)
    subprocess.run(command, cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
