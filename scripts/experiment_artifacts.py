from __future__ import annotations

from pathlib import Path


def build_round_artifact_paths(*, data_root: Path, run_name: str) -> dict[str, Path]:
    release_dir = data_root / "releases" / f"{run_name}_runtime"
    run_dir = data_root / "outputs" / run_name
    experiment_report_dir = data_root / "experiment_reports"
    comparison_dir = data_root / "comparisons"
    return {
        "run_dir": run_dir,
        "release_dir": release_dir,
        "train_config": data_root / "configs" / f"{run_name}.yaml",
        "runtime_config": data_root / "configs" / f"{run_name}_runtime.yaml",
        "selected_checkpoint": run_dir / "selected.pt",
        "deployment_selection_json": run_dir / "deployment_selection.json",
        "deployment_selection_markdown": run_dir / "deployment_selection.md",
        "sample_summary_json": run_dir / "sample_classification.json",
        "sample_summary_markdown": run_dir / "sample_classification.md",
        "release_verification": release_dir / "verification.json",
        "round_summary_json": experiment_report_dir / f"{run_name}.json",
        "round_summary_markdown": experiment_report_dir / f"{run_name}.md",
        "round_completion_json": experiment_report_dir / f"{run_name}_completion.json",
        "round_completion_markdown": experiment_report_dir / f"{run_name}_completion.md",
        "comparison_dir": comparison_dir,
    }


def build_comparison_artifact_paths(
    *,
    data_root: Path,
    run_name: str,
    previous_run_name: str,
) -> dict[str, Path]:
    comparison_dir = data_root / "comparisons"
    stem = f"{run_name}_vs_{previous_run_name}"
    return {
        "previous_train_summary": data_root / "outputs" / previous_run_name / "summary.json",
        "comparison_json": comparison_dir / f"{stem}.json",
        "comparison_markdown": comparison_dir / f"{stem}.md",
        "expected_state_json": comparison_dir / f"{stem}_expected_state.json",
        "expected_state_markdown": comparison_dir / f"{stem}_expected_state.md",
        "promotion_json": comparison_dir / f"{run_name}_promotion_decision.json",
        "promotion_markdown": comparison_dir / f"{run_name}_promotion_decision.md",
    }


def build_event_summary_path(batch_output_dir: Path) -> Path:
    return batch_output_dir / "reports" / "event_corpus_summary.json"


def build_batch_predictions_manifest_path(batch_output_dir: Path) -> Path:
    return batch_output_dir / "reports" / "batch_predictions_manifest.json"


def build_prepare_ur_summary_path(data_root: Path) -> Path:
    return data_root / "manifests" / "ur_fall_prepare_summary.json"


def build_finalize_ur_summary_path(data_root: Path) -> Path:
    return data_root / "manifests" / "ur_fall_finalize_summary.json"


def build_ur_fall_pose_manifest_path(data_root: Path) -> Path:
    return data_root / "processed" / "poses_ur_fall.jsonl"


def build_base_experiment_step_outputs(
    *,
    data_root: Path,
    run_name: str,
    previous_run_name: str | None,
    batch_output_dir: Path | None,
    package_release: bool,
    prepare_ur: bool,
    finalize_ur: bool,
) -> dict[str, list[Path]]:
    artifacts = build_round_artifact_paths(data_root=data_root, run_name=run_name)
    outputs: dict[str, list[Path]] = {
        "train_public_plus_ur": [artifacts["run_dir"] / "summary.json"],
        "select_deployment_checkpoint": [
            artifacts["deployment_selection_json"],
            artifacts["selected_checkpoint"],
            artifacts["runtime_config"],
        ],
        "evaluate_sample_classification": [artifacts["sample_summary_json"]],
        "summarize_experiment_round": [artifacts["round_summary_json"]],
        "check_experiment_round_complete": [artifacts["round_completion_json"]],
    }
    if prepare_ur:
        outputs["prepare_ur_fall"] = [
            build_prepare_ur_summary_path(data_root),
            build_ur_fall_pose_manifest_path(data_root),
        ]
    if finalize_ur:
        outputs["finalize_ur_fall"] = [
            build_finalize_ur_summary_path(data_root),
            build_ur_fall_pose_manifest_path(data_root),
        ]
    if package_release:
        outputs["package_release"] = [artifacts["release_dir"] / "release_manifest.json"]
        outputs["verify_release_bundle"] = [artifacts["release_verification"]]
    if batch_output_dir is not None:
        outputs["batch_inference"] = [build_batch_predictions_manifest_path(batch_output_dir)]
    if previous_run_name is not None:
        comparison_artifacts = build_comparison_artifact_paths(
            data_root=data_root,
            run_name=run_name,
            previous_run_name=previous_run_name,
        )
        outputs["compare_public_vs_baseline"] = [comparison_artifacts["comparison_json"]]
        if batch_output_dir is not None:
            outputs["compare_public_expected_state_vs_baseline"] = [comparison_artifacts["expected_state_json"]]
        outputs["assess_public_round_promotion"] = [comparison_artifacts["promotion_json"]]
    return outputs


def build_refined_experiment_step_outputs(
    *,
    data_root: Path,
    run_name: str,
    previous_run_name: str | None,
    batch_output_dir: Path | None,
    package_release: bool,
) -> dict[str, list[Path]]:
    artifacts = build_round_artifact_paths(data_root=data_root, run_name=run_name)
    outputs: dict[str, list[Path]] = {
        "train_public_plus_ur_refined": [artifacts["run_dir"] / "summary.json"],
        "select_refined_deployment_checkpoint": [
            artifacts["deployment_selection_json"],
            artifacts["selected_checkpoint"],
            artifacts["runtime_config"],
        ],
        "evaluate_refined_sample_classification": [artifacts["sample_summary_json"]],
        "summarize_experiment_round": [artifacts["round_summary_json"]],
        "check_experiment_round_complete": [artifacts["round_completion_json"]],
    }
    if package_release:
        outputs["package_refined_release"] = [artifacts["release_dir"] / "release_manifest.json"]
        outputs["verify_refined_release_bundle"] = [artifacts["release_verification"]]
    if batch_output_dir is not None:
        outputs["refined_batch_inference"] = [build_batch_predictions_manifest_path(batch_output_dir)]
    if previous_run_name is not None:
        comparison_artifacts = build_comparison_artifact_paths(
            data_root=data_root,
            run_name=run_name,
            previous_run_name=previous_run_name,
        )
        outputs["compare_refined_vs_baseline"] = [comparison_artifacts["comparison_json"]]
        if batch_output_dir is not None:
            outputs["compare_refined_expected_state_vs_baseline"] = [comparison_artifacts["expected_state_json"]]
        outputs["assess_current_round_promotion"] = [comparison_artifacts["promotion_json"]]
    return outputs


def filter_plan_for_resume(
    plan: list[dict[str, object]],
    *,
    step_outputs: dict[str, list[Path]],
) -> tuple[list[dict[str, object]], list[str]]:
    filtered: list[dict[str, object]] = []
    skipped: list[str] = []
    for step in plan:
        step_name = str(step["step"])
        outputs = step_outputs.get(step_name, [])
        if outputs and all(path.is_file() for path in outputs):
            skipped.append(step_name)
            continue
        filtered.append(step)
    return filtered, skipped
