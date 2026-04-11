from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from experiment_artifacts import (
    build_base_experiment_step_outputs,
    build_batch_predictions_manifest_path,
    build_comparison_artifact_paths,
    build_event_summary_path,
    build_round_artifact_paths,
    filter_plan_for_resume,
)


def _run(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    print("[run]", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def build_experiment_plan(
    *,
    python_bin: str,
    repo_root: Path,
    data_root: Path,
    run_name: str,
    runtime_config_template: Path,
    window_size: int,
    stride: int,
    seed: int,
    kinematic_feature_set: str,
    clip_focal_gamma: float,
    quality_loss_weight: float,
    batch_manifest: Path | None,
    batch_output_dir: Path | None,
    prepare_ur: bool,
    finalize_ur: bool,
    train: bool,
    package_release: bool,
    write_video: bool,
    camera: str,
    workers: int,
    device: str,
    rtmo_device: str,
    tolerance_seconds: float,
    baseline_run_name: str | None,
    baseline_batch_output_dir: Path | None,
    min_macro_f1_delta: float,
    min_sample_macro_f1_delta: float,
    min_near_fall_f1_delta: float,
    min_recovery_f1_delta: float,
    max_fp_per_hour_delta: float,
    max_delay_delta: float,
    resume: bool,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []

    if prepare_ur:
        commands.append(
            {
                "step": "prepare_ur_fall",
                "command": [
                    python_bin,
                    "scripts/prepare_ur_fall_corpus.py",
                    "--python",
                    python_bin,
                    "--repo-root",
                    str(repo_root),
                    "--data-root",
                    str(data_root),
                    "--camera",
                    camera,
                    "--workers",
                    str(workers),
                    "--device",
                    device,
                ],
            }
        )
        if resume:
            commands[-1]["command"].append("--resume")

    if finalize_ur:
        commands.append(
            {
                "step": "finalize_ur_fall",
                "command": [
                    python_bin,
                    "scripts/finalize_ur_fall_corpus.py",
                    "--python",
                    python_bin,
                    "--repo-root",
                    str(repo_root),
                    "--data-root",
                    str(data_root),
                ],
            }
        )

    if train:
        commands.append(
            {
                "step": "train_public_plus_ur",
                "command": [
                    python_bin,
                    "scripts/run_public_plus_ur_training.py",
                    "--python",
                    python_bin,
                    "--repo-root",
                    str(repo_root),
                    "--data-root",
                    str(data_root),
                    "--run-name",
                    run_name,
                    "--window-size",
                    str(window_size),
                    "--stride",
                    str(stride),
                    "--seed",
                    str(seed),
                    "--kinematic-feature-set",
                    kinematic_feature_set,
                    "--clip-focal-gamma",
                    str(clip_focal_gamma),
                    "--quality-loss-weight",
                    str(quality_loss_weight),
                    "--runtime-config-template",
                    str(runtime_config_template),
                    "--train",
                ],
            }
        )

    artifacts = build_round_artifact_paths(data_root=data_root, run_name=run_name)
    release_dir = artifacts["release_dir"]
    run_dir = artifacts["run_dir"]
    train_config = artifacts["train_config"]
    runtime_config = artifacts["runtime_config"]
    sample_summary_json = artifacts["sample_summary_json"]
    sample_summary_markdown = artifacts["sample_summary_markdown"]

    if train:
        commands.append(
            {
                "step": "select_deployment_checkpoint",
                "command": [
                    python_bin,
                    "scripts/select_deployment_checkpoint.py",
                    "--run-dir",
                    str(run_dir),
                    "--train-config",
                    str(train_config),
                    "--runtime-template",
                    str(runtime_config_template),
                    "--runtime-output",
                    str(runtime_config),
                    "--device",
                    device,
                    "--selected-checkpoint-output",
                    str(artifacts["selected_checkpoint"]),
                    "--output-json",
                    str(artifacts["deployment_selection_json"]),
                    "--output-markdown",
                    str(artifacts["deployment_selection_markdown"]),
                ],
            }
        )
        commands.append(
            {
                "step": "evaluate_sample_classification",
                "command": [
                    python_bin,
                    "scripts/evaluate_sample_classification.py",
                    "--train-config",
                    str(train_config),
                    "--checkpoint",
                    str(artifacts["selected_checkpoint"]),
                    "--device",
                    device,
                    "--output-json",
                    str(sample_summary_json),
                    "--output-markdown",
                    str(sample_summary_markdown),
                ],
            }
        )

    if package_release:
        commands.append(
            {
                "step": "package_release",
                "command": [
                    python_bin,
                    "scripts/package_runtime_release.py",
                    "--run-dir",
                    str(run_dir),
                    "--train-config",
                    str(train_config),
                    "--runtime-config",
                    str(runtime_config),
                    "--output-dir",
                    str(release_dir),
                    "--checkpoint",
                    str(artifacts["selected_checkpoint"]),
                    "--selection-summary",
                    str(artifacts["deployment_selection_json"]),
                ],
            }
        )
        commands.append(
            {
                "step": "verify_release_bundle",
                "command": [
                    python_bin,
                    "-m",
                    "huling_guard.cli",
                    "verify-release",
                    "--release-dir",
                    str(release_dir),
                    "--output",
                    str(artifacts["release_verification"]),
                ],
            }
        )

    if batch_manifest is not None and batch_output_dir is not None:
        commands.append(
            {
                "step": "batch_inference",
                "command": [
                    python_bin,
                    "-m",
                    "huling_guard.cli",
                    "run-release-video-batch",
                    "--release-dir",
                    str(release_dir),
                    "--manifest",
                    str(batch_manifest),
                    "--output-dir",
                    str(batch_output_dir),
                    "--device",
                    device,
                    "--rtmo-device",
                    rtmo_device,
                    "--tolerance-seconds",
                    str(tolerance_seconds),
                ]
                + (["--write-video"] if write_video else []),
            }
        )

    comparison_artifacts: dict[str, Path] | None = None
    if baseline_run_name is not None:
        comparison_artifacts = build_comparison_artifact_paths(
            data_root=data_root,
            run_name=run_name,
            previous_run_name=baseline_run_name,
        )
        if baseline_batch_output_dir is not None and batch_output_dir is not None:
            commands.append(
                {
                    "step": "compare_public_expected_state_vs_baseline",
                    "command": [
                        python_bin,
                        "scripts/compare_expected_state_manifests.py",
                        "--baseline-manifest",
                        str(build_batch_predictions_manifest_path(baseline_batch_output_dir)),
                        "--candidate-manifest",
                        str(build_batch_predictions_manifest_path(batch_output_dir)),
                        "--expected-state",
                        "normal",
                        "--output-json",
                        str(comparison_artifacts["expected_state_json"]),
                        "--output-markdown",
                        str(comparison_artifacts["expected_state_markdown"]),
                    ],
                }
            )
        compare_command = [
            python_bin,
            "scripts/compare_experiment_results.py",
            "--baseline-train-summary",
            str(comparison_artifacts["previous_train_summary"]),
            "--candidate-train-summary",
            str(run_dir / "summary.json"),
            "--baseline-sample-summary",
            str(build_round_artifact_paths(data_root=data_root, run_name=baseline_run_name)["sample_summary_json"]),
            "--candidate-sample-summary",
            str(sample_summary_json),
            "--output-json",
            str(comparison_artifacts["comparison_json"]),
            "--output-markdown",
            str(comparison_artifacts["comparison_markdown"]),
        ]
        if baseline_batch_output_dir is not None and batch_output_dir is not None:
            compare_command.extend(
                [
                    "--baseline-event-summary",
                    str(build_event_summary_path(baseline_batch_output_dir)),
                    "--candidate-event-summary",
                    str(build_event_summary_path(batch_output_dir)),
                    "--expected-state-summary",
                    str(comparison_artifacts["expected_state_json"]),
                ]
            )
        commands.append({"step": "compare_public_vs_baseline", "command": compare_command})
        commands.append(
            {
                "step": "assess_public_round_promotion",
                "command": [
                    python_bin,
                    "scripts/assess_experiment_promotion.py",
                    "--comparison",
                    str(comparison_artifacts["comparison_json"]),
                    "--output-json",
                    str(comparison_artifacts["promotion_json"]),
                    "--output-markdown",
                    str(comparison_artifacts["promotion_markdown"]),
                    "--min-macro-f1-delta",
                    str(min_macro_f1_delta),
                    "--min-sample-macro-f1-delta",
                    str(min_sample_macro_f1_delta),
                    "--min-near-fall-f1-delta",
                    str(min_near_fall_f1_delta),
                    "--min-recovery-f1-delta",
                    str(min_recovery_f1_delta),
                    "--max-fp-per-hour-delta",
                    str(max_fp_per_hour_delta),
                    "--max-delay-delta",
                    str(max_delay_delta),
                ],
            }
        )

    commands.append(
        {
            "step": "summarize_experiment_round",
            "command": [
                python_bin,
                "scripts/summarize_experiment_round.py",
                "--run-name",
                run_name,
                "--training-summary",
                str(run_dir / "summary.json"),
                "--sample-summary",
                str(sample_summary_json),
                "--output-json",
                str(artifacts["round_summary_json"]),
                "--output-markdown",
                str(artifacts["round_summary_markdown"]),
            ]
            + (
                ["--event-summary", str(build_event_summary_path(batch_output_dir))]
                if batch_output_dir is not None
                else []
            )
            + (
                ["--release-verification", str(artifacts["release_verification"])]
                if package_release
                else []
            )
            + (
                ["--deployment-selection", str(artifacts["deployment_selection_json"])]
                if train
                else []
            )
            + (
                ["--comparison-summary", str(comparison_artifacts["comparison_json"])]
                if comparison_artifacts is not None
                else []
            )
            + (
                ["--promotion-summary", str(comparison_artifacts["promotion_json"])]
                if comparison_artifacts is not None
                else []
            ),
        }
    )
    commands.append(
        {
            "step": "check_experiment_round_complete",
            "command": [
                python_bin,
                "scripts/check_experiment_round_complete.py",
                "--run-name",
                run_name,
                "--training-summary",
                str(run_dir / "summary.json"),
                "--sample-summary",
                str(sample_summary_json),
                "--round-summary",
                str(artifacts["round_summary_json"]),
                "--output-json",
                str(artifacts["round_completion_json"]),
                "--output-markdown",
                str(artifacts["round_completion_markdown"]),
            ]
            + (
                ["--event-summary", str(build_event_summary_path(batch_output_dir))]
                if batch_output_dir is not None
                else []
            )
            + (
                ["--release-verification", str(artifacts["release_verification"])]
                if package_release
                else []
            )
            + (
                ["--deployment-selection", str(artifacts["deployment_selection_json"])]
                if train
                else []
            )
            + (
                ["--comparison-summary", str(comparison_artifacts["comparison_json"])]
                if comparison_artifacts is not None
                else []
            )
            + (
                ["--promotion-summary", str(comparison_artifacts["promotion_json"])]
                if comparison_artifacts is not None
                else []
            ),
        }
    )

    return commands


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    parser.add_argument("--run-name", default="public_plus_ur_v1")
    parser.add_argument("--window-size", type=int, default=64)
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--kinematic-feature-set", default="v2")
    parser.add_argument("--clip-focal-gamma", type=float, default=0.0)
    parser.add_argument("--quality-loss-weight", type=float, default=0.15)
    parser.add_argument("--runtime-config-template", type=Path, default=Path("configs/runtime_room.yaml"))
    parser.add_argument("--camera", choices=("cam0", "cam1", "both"), default="cam0")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--rtmo-device", default="cuda:0")
    parser.add_argument("--tolerance-seconds", type=float, default=2.0)
    parser.add_argument("--batch-manifest", type=Path)
    parser.add_argument("--batch-output-dir", type=Path)
    parser.add_argument("--baseline-run-name")
    parser.add_argument("--baseline-batch-output-dir", type=Path)
    parser.add_argument("--min-macro-f1-delta", type=float, default=0.0)
    parser.add_argument("--min-sample-macro-f1-delta", type=float, default=0.0)
    parser.add_argument("--min-near-fall-f1-delta", type=float, default=0.02)
    parser.add_argument("--min-recovery-f1-delta", type=float, default=0.02)
    parser.add_argument("--max-fp-per-hour-delta", type=float, default=0.2)
    parser.add_argument("--max-delay-delta", type=float, default=0.2)
    parser.add_argument("--prepare-ur", action="store_true")
    parser.add_argument("--finalize-ur", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--package-release", action="store_true")
    parser.add_argument("--write-video", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    runtime_template = args.runtime_config_template
    if not runtime_template.is_absolute():
        runtime_template = (repo_root / runtime_template).resolve()

    if (args.batch_manifest is None) != (args.batch_output_dir is None):
        raise ValueError("batch_manifest and batch_output_dir must be provided together")

    batch_manifest = args.batch_manifest.resolve() if args.batch_manifest is not None else None
    batch_output_dir = args.batch_output_dir.resolve() if args.batch_output_dir is not None else None
    baseline_batch_output_dir = (
        args.baseline_batch_output_dir.resolve() if args.baseline_batch_output_dir is not None else None
    )

    plan = build_experiment_plan(
        python_bin=args.python,
        repo_root=repo_root,
        data_root=data_root,
        run_name=args.run_name,
        runtime_config_template=runtime_template,
        window_size=args.window_size,
        stride=args.stride,
        seed=args.seed,
        kinematic_feature_set=args.kinematic_feature_set,
        clip_focal_gamma=args.clip_focal_gamma,
        quality_loss_weight=args.quality_loss_weight,
        batch_manifest=batch_manifest,
        batch_output_dir=batch_output_dir,
        prepare_ur=args.prepare_ur,
        finalize_ur=args.finalize_ur,
        train=args.train,
        package_release=args.package_release,
        write_video=args.write_video,
        camera=args.camera,
        workers=args.workers,
        device=args.device,
        rtmo_device=args.rtmo_device,
        tolerance_seconds=args.tolerance_seconds,
        baseline_run_name=args.baseline_run_name,
        baseline_batch_output_dir=baseline_batch_output_dir,
        min_macro_f1_delta=args.min_macro_f1_delta,
        min_sample_macro_f1_delta=args.min_sample_macro_f1_delta,
        min_near_fall_f1_delta=args.min_near_fall_f1_delta,
        min_recovery_f1_delta=args.min_recovery_f1_delta,
        max_fp_per_hour_delta=args.max_fp_per_hour_delta,
        max_delay_delta=args.max_delay_delta,
        resume=args.resume,
    )
    skipped_steps: list[str] = []
    if args.resume:
        plan, skipped_steps = filter_plan_for_resume(
            plan,
            step_outputs=build_base_experiment_step_outputs(
                data_root=data_root,
                run_name=args.run_name,
                previous_run_name=args.baseline_run_name,
                batch_output_dir=batch_output_dir,
                package_release=args.package_release,
                prepare_ur=args.prepare_ur,
                finalize_ur=args.finalize_ur,
            ),
        )
        for step_name in skipped_steps:
            print(f"[resume-skip] {step_name}", flush=True)

    if args.plan_output is not None:
        args.plan_output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"steps": plan, "skipped_steps": skipped_steps}
        args.plan_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {args.plan_output}", flush=True)
    if args.plan_only:
        print(json.dumps({"steps": plan, "skipped_steps": skipped_steps}, ensure_ascii=False, indent=2), end="")
        return

    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS") or "8"
    env["MKL_NUM_THREADS"] = env.get("MKL_NUM_THREADS") or "8"
    env["OPENBLAS_NUM_THREADS"] = env.get("OPENBLAS_NUM_THREADS") or "1"
    env["NUMEXPR_NUM_THREADS"] = env.get("NUMEXPR_NUM_THREADS") or "1"

    for step in plan:
        _run(step["command"], cwd=repo_root, env=env)


if __name__ == "__main__":
    main()
