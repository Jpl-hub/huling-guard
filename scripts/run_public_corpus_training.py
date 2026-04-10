from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import yaml
from huling_guard.data import summarize_pose_manifest_coverage
from huling_guard.features import get_kinematic_feature_dim


DEFAULT_VAL_SUBJECTS = (
    "caucafall:9",
    "caucafall:10",
    "up_fall:16",
    "up_fall:17",
)


def _run(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("[run]", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def _validate_pose_coverage(*, raw_manifests: list[Path], pose_manifests: list[Path]) -> None:
    coverage_reports: list[str] = []
    for raw_manifest, pose_manifest in zip(raw_manifests, pose_manifests, strict=True):
        summary = summarize_pose_manifest_coverage(
            raw_manifest_path=raw_manifest,
            pose_manifest_path=pose_manifest,
        )
        coverage_reports.append(
            (
                f"{raw_manifest.name} -> {pose_manifest.name}: "
                f"coverage={summary.coverage_ratio:.4f} "
                f"raw={summary.raw_count} pose={summary.pose_count} "
                f"missing={summary.missing_pose_count} extra={summary.extra_pose_count}"
            )
        )
        if summary.missing_pose_count > 0:
            preview = ", ".join(summary.missing_pose_sample_ids[:10])
            raise ValueError(
                "pose manifest coverage is incomplete for "
                f"{raw_manifest.name}: missing {summary.missing_pose_count} sample(s); "
                f"first missing ids: {preview}"
            )
    for report in coverage_reports:
        print(f"[coverage] {report}", flush=True)


def build_config(
    *,
    train_manifest: Path,
    eval_manifest: Path,
    output_dir: Path,
    window_size: int,
    stride: int,
    seed: int,
    kinematic_feature_set: str,
    clip_focal_gamma: float,
) -> dict[str, object]:
    kinematic_dim = get_kinematic_feature_dim(kinematic_feature_set)
    return {
        "data": {
            "manifest_path": str(train_manifest),
            "eval_manifest_path": str(eval_manifest),
            "window_size": window_size,
            "stride": stride,
            "num_joints": 17,
        },
        "model": {
            "pose_dim": 3,
            "kinematic_dim": kinematic_dim,
            "kinematic_feature_set": kinematic_feature_set,
            "scene_dim": 8,
            "hidden_dim": 256,
            "num_heads": 8,
            "depth": 6,
            "dropout": 0.1,
        },
        "augmentation": {
            "temporal_jitter_frames": 4,
            "time_mask_prob": 0.25,
            "time_mask_max_frames": 6,
            "pose_noise_std": 0.012,
            "kinematic_noise_std": 0.01,
            "confidence_dropout_prob": 0.04,
        },
        "training": {
            "seed": seed,
            "batch_size": 64,
            "epochs": 30,
            "learning_rate": 3e-4,
            "min_learning_rate": 3e-5,
            "weight_decay": 1e-4,
            "clip_focal_gamma": clip_focal_gamma,
            "risk_loss_weight": 0.3,
            "class_balance_beta": 0.999,
            "num_workers": 8,
            "pin_memory": True,
            "amp": True,
            "grad_clip_norm": 1.0,
            "scheduler": "cosine",
            "balanced_sampling": True,
            "device": "cuda",
            "output_dir": str(output_dir),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    parser.add_argument("--caucafall-pose-manifest", type=Path)
    parser.add_argument("--up-fall-pose-manifest", type=Path)
    parser.add_argument("--window-size", type=int, default=64)
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--kinematic-feature-set", default="v2")
    parser.add_argument("--clip-focal-gamma", type=float, default=0.0)
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--run-name", default="public_merged")
    parser.add_argument("--runtime-config-template", type=Path)
    parser.add_argument("--val-subjects", nargs="+", default=list(DEFAULT_VAL_SUBJECTS))
    parser.add_argument("--raw-manifests", nargs="*")
    parser.add_argument("--pose-manifests", nargs="*")
    parser.add_argument("--train-interval-labels", type=Path)
    parser.add_argument("--eval-interval-labels", type=Path)
    parser.add_argument("--interval-min-overlap", type=float, default=0.5)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    python_bin = args.python

    raw_dir = data_root / "raw"
    manifest_dir = data_root / "manifests"
    processed_dir = data_root / "processed"
    window_dir = processed_dir / f"windows_{args.run_name}"
    config_dir = data_root / "configs"
    output_dir = data_root / "outputs" / args.run_name

    default_raw_manifests = [
        raw_dir / "caucafall_manifest.jsonl",
        manifest_dir / "up_fall_valid.jsonl",
    ]
    default_pose_manifests = [
        args.caucafall_pose_manifest.resolve()
        if args.caucafall_pose_manifest is not None
        else processed_dir / "poses_caucafall.jsonl",
        args.up_fall_pose_manifest.resolve()
        if args.up_fall_pose_manifest is not None
        else processed_dir / "poses_up_fall.jsonl",
    ]
    raw_manifests = [Path(path).resolve() for path in args.raw_manifests] if args.raw_manifests else default_raw_manifests
    pose_manifests = [Path(path).resolve() for path in args.pose_manifests] if args.pose_manifests else default_pose_manifests
    if len(raw_manifests) != len(pose_manifests):
        raise ValueError("raw_manifests and pose_manifests must have the same length")
    for path in (*raw_manifests, *pose_manifests):
        _require_file(path)
    _validate_pose_coverage(raw_manifests=raw_manifests, pose_manifests=pose_manifests)
    train_interval_labels = args.train_interval_labels.resolve() if args.train_interval_labels is not None else None
    eval_interval_labels = args.eval_interval_labels.resolve() if args.eval_interval_labels is not None else None
    for path in (train_interval_labels, eval_interval_labels):
        if path is not None:
            _require_file(path)

    merged_raw = raw_dir / "public_merged_raw.jsonl"
    raw_train = raw_dir / "public_merged_train.jsonl"
    raw_val = raw_dir / "public_merged_val.jsonl"
    merged_pose = processed_dir / "poses_public_merged.jsonl"
    pose_train = processed_dir / "poses_public_merged_train.jsonl"
    pose_val = processed_dir / "poses_public_merged_val.jsonl"
    feature_root = processed_dir / f"features_{args.run_name}"
    feature_train_dir = feature_root / "train"
    feature_val_dir = feature_root / "val"
    feature_train_manifest = processed_dir / f"features_{args.run_name}_train.jsonl"
    feature_val_manifest = processed_dir / f"features_{args.run_name}_val.jsonl"
    train_windows = window_dir / "train.jsonl"
    val_windows = window_dir / "val.jsonl"
    config_path = config_dir / f"{args.run_name}.yaml"

    for directory in (
        raw_dir,
        manifest_dir,
        processed_dir,
        window_dir,
        config_dir,
        output_dir,
        feature_train_dir,
        feature_val_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS") or "8"
    env["MKL_NUM_THREADS"] = env.get("MKL_NUM_THREADS") or "8"
    env["OPENBLAS_NUM_THREADS"] = env.get("OPENBLAS_NUM_THREADS") or "1"
    env["NUMEXPR_NUM_THREADS"] = env.get("NUMEXPR_NUM_THREADS") or "1"

    cli = [python_bin, "-m", "huling_guard.cli"]

    _run(
        cli
        + [
            "merge-manifests",
            "--inputs",
            *[str(path) for path in raw_manifests],
            "--output",
            str(merged_raw),
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "split-by-subject",
            "--input",
            str(merged_raw),
            "--train-output",
            str(raw_train),
            "--val-output",
            str(raw_val),
            "--val-subjects",
            *args.val_subjects,
            "--subject-key",
            "dataset_subject",
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "merge-manifests",
            "--inputs",
            *[str(path) for path in pose_manifests],
            "--output",
            str(merged_pose),
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "split-pose-by-raw",
            "--raw-train",
            str(raw_train),
            "--raw-val",
            str(raw_val),
            "--pose-manifest",
            str(merged_pose),
            "--train-output",
            str(pose_train),
            "--val-output",
            str(pose_val),
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "cache-features",
            "--pose-manifest",
            str(pose_train),
            "--output-dir",
            str(feature_train_dir),
            "--output-manifest",
            str(feature_train_manifest),
            "--kinematic-feature-set",
            args.kinematic_feature_set,
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "cache-features",
            "--pose-manifest",
            str(pose_val),
            "--output-dir",
            str(feature_val_dir),
            "--output-manifest",
            str(feature_val_manifest),
            "--kinematic-feature-set",
            args.kinematic_feature_set,
        ],
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "build-windows",
            "--pose-manifest",
            str(feature_train_manifest),
            "--output",
            str(train_windows),
            "--window-size",
            str(args.window_size),
            "--stride",
            str(args.stride),
        ]
        + (
            [
                "--interval-labels",
                str(train_interval_labels),
                "--interval-min-overlap",
                str(args.interval_min_overlap),
            ]
            if train_interval_labels is not None
            else []
        ),
        cwd=repo_root,
        env=env,
    )
    _run(
        cli
        + [
            "build-windows",
            "--pose-manifest",
            str(feature_val_manifest),
            "--output",
            str(val_windows),
            "--window-size",
            str(args.window_size),
            "--stride",
            str(args.stride),
        ]
        + (
            [
                "--interval-labels",
                str(eval_interval_labels),
                "--interval-min-overlap",
                str(args.interval_min_overlap),
            ]
            if eval_interval_labels is not None
            else []
        ),
        cwd=repo_root,
        env=env,
    )

    config = build_config(
        train_manifest=train_windows,
        eval_manifest=val_windows,
        output_dir=output_dir,
        window_size=args.window_size,
        stride=args.stride,
        seed=args.seed,
        kinematic_feature_set=args.kinematic_feature_set,
        clip_focal_gamma=args.clip_focal_gamma,
    )
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"[write] {config_path}", flush=True)

    if args.train:
        _run(cli + ["train", "--config", str(config_path)], cwd=repo_root, env=env)
        if args.runtime_config_template is not None:
            runtime_template = args.runtime_config_template.resolve()
            _require_file(runtime_template)
            checkpoint_path = output_dir / "best.pt"
            _require_file(checkpoint_path)
            calibrated_runtime = config_dir / f"{args.run_name}_runtime.yaml"
            _run(
                cli
                + [
                    "calibrate-runtime",
                    "--train-config",
                    str(config_path),
                    "--runtime-config",
                    str(runtime_template),
                    "--checkpoint",
                    str(checkpoint_path),
                    "--output",
                    str(calibrated_runtime),
                ],
                cwd=repo_root,
                env=env,
            )


if __name__ == "__main__":
    main()
