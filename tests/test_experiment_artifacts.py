from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from experiment_artifacts import (
    build_comparison_artifact_paths,
    build_event_summary_path,
    build_base_experiment_step_outputs,
    build_finalize_ur_summary_path,
    build_prepare_ur_summary_path,
    build_refined_experiment_step_outputs,
    build_round_artifact_paths,
    build_ur_fall_pose_manifest_path,
    filter_plan_for_resume,
)


def test_build_round_artifact_paths_is_stable() -> None:
    data_root = Path("/data")
    paths = build_round_artifact_paths(data_root=data_root, run_name="public_plus_ur_v1")

    assert paths["run_dir"] == data_root / "outputs" / "public_plus_ur_v1"
    assert paths["release_dir"] == data_root / "releases" / "public_plus_ur_v1_runtime"
    assert paths["selected_checkpoint"] == data_root / "outputs" / "public_plus_ur_v1" / "selected.pt"
    assert paths["deployment_selection_json"] == data_root / "outputs" / "public_plus_ur_v1" / "deployment_selection.json"
    assert paths["sample_summary_json"] == data_root / "outputs" / "public_plus_ur_v1" / "sample_classification.json"
    assert paths["round_summary_json"] == data_root / "experiment_reports" / "public_plus_ur_v1.json"
    assert paths["round_completion_markdown"] == data_root / "experiment_reports" / "public_plus_ur_v1_completion.md"


def test_build_comparison_artifact_paths_is_stable() -> None:
    data_root = Path("/data")
    paths = build_comparison_artifact_paths(
        data_root=data_root,
        run_name="public_plus_ur_refined_v1",
        previous_run_name="public_plus_ur_v1",
    )

    assert paths["previous_train_summary"] == data_root / "outputs" / "public_plus_ur_v1" / "summary.json"
    assert paths["comparison_json"] == data_root / "comparisons" / "public_plus_ur_refined_v1_vs_public_plus_ur_v1.json"
    assert paths["expected_state_json"] == data_root / "comparisons" / "public_plus_ur_refined_v1_vs_public_plus_ur_v1_expected_state.json"
    assert paths["promotion_markdown"] == data_root / "comparisons" / "public_plus_ur_refined_v1_promotion_decision.md"


def test_build_event_summary_path_points_to_report_file() -> None:
    batch_output_dir = Path("/data/eval_outputs/public_plus_ur_v1")
    assert build_event_summary_path(batch_output_dir) == batch_output_dir / "reports" / "event_corpus_summary.json"


def test_filter_plan_for_resume_skips_completed_steps(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    run_name = "public_plus_ur_v1"
    outputs = build_base_experiment_step_outputs(
        data_root=data_root,
        run_name=run_name,
        previous_run_name=None,
        batch_output_dir=None,
        package_release=False,
        prepare_ur=False,
        finalize_ur=False,
    )
    summary_path = outputs["train_public_plus_ur"][0]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("{}", encoding="utf-8")

    plan = [
        {"step": "train_public_plus_ur", "command": ["python", "train.py"]},
        {"step": "evaluate_sample_classification", "command": ["python", "evaluate.py"]},
        {"step": "summarize_experiment_round", "command": ["python", "summary.py"]},
    ]
    filtered, skipped = filter_plan_for_resume(plan, step_outputs=outputs)

    assert skipped == ["train_public_plus_ur"]
    assert [step["step"] for step in filtered] == ["evaluate_sample_classification", "summarize_experiment_round"]


def test_build_refined_experiment_step_outputs_includes_comparison_files() -> None:
    outputs = build_refined_experiment_step_outputs(
        data_root=Path("/data"),
        run_name="public_plus_ur_refined_v1",
        previous_run_name="public_plus_ur_v1",
        batch_output_dir=Path("/data/eval_outputs/refined"),
        package_release=True,
    )

    assert outputs["select_refined_deployment_checkpoint"] == [
        Path("/data/outputs/public_plus_ur_refined_v1/deployment_selection.json"),
        Path("/data/outputs/public_plus_ur_refined_v1/selected.pt"),
        Path("/data/configs/public_plus_ur_refined_v1_runtime.yaml"),
    ]
    assert outputs["evaluate_refined_sample_classification"][0] == Path(
        "/data/outputs/public_plus_ur_refined_v1/sample_classification.json"
    )
    assert outputs["compare_refined_vs_baseline"][0] == Path(
        "/data/comparisons/public_plus_ur_refined_v1_vs_public_plus_ur_v1.json"
    )
    assert outputs["compare_refined_expected_state_vs_baseline"][0] == Path(
        "/data/comparisons/public_plus_ur_refined_v1_vs_public_plus_ur_v1_expected_state.json"
    )
    assert outputs["assess_current_round_promotion"][0] == Path(
        "/data/comparisons/public_plus_ur_refined_v1_promotion_decision.json"
    )


def test_build_base_experiment_step_outputs_includes_comparison_files() -> None:
    outputs = build_base_experiment_step_outputs(
        data_root=Path("/data"),
        run_name="public_plus_ur_v4",
        previous_run_name="public_plus_ur_v1",
        batch_output_dir=Path("/data/eval_outputs/public_plus_ur_v4"),
        package_release=True,
        prepare_ur=False,
        finalize_ur=False,
    )

    assert outputs["select_deployment_checkpoint"] == [
        Path("/data/outputs/public_plus_ur_v4/deployment_selection.json"),
        Path("/data/outputs/public_plus_ur_v4/selected.pt"),
        Path("/data/configs/public_plus_ur_v4_runtime.yaml"),
    ]
    assert outputs["compare_public_vs_baseline"][0] == Path(
        "/data/comparisons/public_plus_ur_v4_vs_public_plus_ur_v1.json"
    )
    assert outputs["compare_public_expected_state_vs_baseline"][0] == Path(
        "/data/comparisons/public_plus_ur_v4_vs_public_plus_ur_v1_expected_state.json"
    )
    assert outputs["assess_public_round_promotion"][0] == Path(
        "/data/comparisons/public_plus_ur_v4_promotion_decision.json"
    )


def test_ur_resume_outputs_require_pose_manifest() -> None:
    data_root = Path("/data")
    outputs = build_base_experiment_step_outputs(
        data_root=data_root,
        run_name="public_plus_ur_v1",
        previous_run_name=None,
        batch_output_dir=None,
        package_release=False,
        prepare_ur=True,
        finalize_ur=True,
    )

    assert outputs["prepare_ur_fall"] == [
        build_prepare_ur_summary_path(data_root),
        build_ur_fall_pose_manifest_path(data_root),
    ]
    assert outputs["finalize_ur_fall"] == [
        build_finalize_ur_summary_path(data_root),
        build_ur_fall_pose_manifest_path(data_root),
    ]


def test_filter_plan_for_resume_does_not_skip_prepare_ur_without_pose_manifest(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    outputs = build_base_experiment_step_outputs(
        data_root=data_root,
        run_name="public_plus_ur_v1",
        previous_run_name=None,
        batch_output_dir=None,
        package_release=False,
        prepare_ur=True,
        finalize_ur=False,
    )
    prepare_summary, pose_manifest = outputs["prepare_ur_fall"]
    prepare_summary.parent.mkdir(parents=True, exist_ok=True)
    prepare_summary.write_text("{}", encoding="utf-8")

    plan = [{"step": "prepare_ur_fall", "command": ["python", "prepare.py"]}]
    filtered, skipped = filter_plan_for_resume(plan, step_outputs=outputs)

    assert skipped == []
    assert filtered == plan

    pose_manifest.parent.mkdir(parents=True, exist_ok=True)
    pose_manifest.write_text("{}", encoding="utf-8")
    filtered, skipped = filter_plan_for_resume(plan, step_outputs=outputs)
    assert skipped == ["prepare_ur_fall"]
    assert filtered == []
