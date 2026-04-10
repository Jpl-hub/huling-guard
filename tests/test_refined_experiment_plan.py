from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_public_plus_ur_refined_experiment import build_refined_experiment_plan


def test_build_refined_experiment_plan_includes_compare_step() -> None:
    repo_root = Path("/repo")
    data_root = Path("/data")
    runtime_template = repo_root / "configs" / "runtime_room.yaml"
    train_intervals = data_root / "review" / "intervals.json"
    batch_manifest = repo_root / "batch.json"
    batch_output_dir = data_root / "eval_outputs" / "refined"
    baseline_batch_output_dir = data_root / "eval_outputs" / "baseline"

    plan = build_refined_experiment_plan(
        python_bin="python",
        repo_root=repo_root,
        data_root=data_root,
        run_name="public_plus_ur_refined_v1",
        runtime_config_template=runtime_template,
        seed=3407,
        kinematic_feature_set="v2",
        clip_focal_gamma=1.5,
        train_interval_labels=train_intervals,
        eval_interval_labels=None,
        interval_min_overlap=0.5,
        train=True,
        package_release=True,
        batch_manifest=batch_manifest,
        batch_output_dir=batch_output_dir,
        write_video=False,
        device="cuda",
        rtmo_device="cuda:0",
        tolerance_seconds=2.0,
        baseline_run_name="public_plus_ur_v1",
        baseline_batch_output_dir=baseline_batch_output_dir,
        min_macro_f1_delta=0.0,
        min_near_fall_f1_delta=0.02,
        min_recovery_f1_delta=0.02,
        max_fp_per_hour_delta=0.2,
        max_delay_delta=0.2,
    )

    assert [step["step"] for step in plan] == [
        "train_public_plus_ur_refined",
        "select_refined_deployment_checkpoint",
        "evaluate_refined_sample_classification",
        "package_refined_release",
        "verify_refined_release_bundle",
        "refined_batch_inference",
        "compare_refined_expected_state_vs_baseline",
        "compare_refined_vs_baseline",
        "assess_current_round_promotion",
        "summarize_experiment_round",
        "check_experiment_round_complete",
    ]
    assert "scripts/select_deployment_checkpoint.py" in plan[1]["command"]
    assert "scripts/evaluate_sample_classification.py" in plan[2]["command"]
    assert "verify-release" in plan[4]["command"]
    assert "--seed" in plan[0]["command"]
    assert "3407" in plan[0]["command"]
    assert "--kinematic-feature-set" in plan[0]["command"]
    assert "v2" in plan[0]["command"]
    assert "--clip-focal-gamma" in plan[0]["command"]
    assert "1.5" in plan[0]["command"]
    assert "scripts/compare_expected_state_manifests.py" in plan[-5]["command"]
    assert "--baseline-event-summary" in plan[-4]["command"]
    assert "--baseline-sample-summary" in plan[-4]["command"]
    assert "--expected-state-summary" in plan[-4]["command"]
    assert "scripts/assess_experiment_promotion.py" in plan[-3]["command"]
    assert "scripts/summarize_experiment_round.py" in plan[-2]["command"]
    assert "scripts/check_experiment_round_complete.py" in plan[-1]["command"]
