from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_public_plus_ur_experiment import build_experiment_plan


def test_build_experiment_plan_includes_requested_steps() -> None:
    repo_root = Path("/repo")
    data_root = Path("/data")
    runtime_template = repo_root / "configs" / "runtime_room.yaml"
    batch_manifest = repo_root / "batch.json"
    batch_output_dir = data_root / "batch_outputs"

    plan = build_experiment_plan(
        python_bin="python",
        repo_root=repo_root,
        data_root=data_root,
        run_name="public_plus_ur_v1",
        runtime_config_template=runtime_template,
        window_size=32,
        stride=8,
        seed=3407,
        kinematic_feature_set="v2",
        clip_focal_gamma=1.5,
        quality_loss_weight=0.05,
        batch_manifest=batch_manifest,
        batch_output_dir=batch_output_dir,
        prepare_ur=True,
        finalize_ur=True,
        train=True,
        package_release=True,
        write_video=True,
        camera="cam0",
        workers=12,
        device="cuda",
        rtmo_device="cuda:0",
        tolerance_seconds=2.0,
        baseline_run_name="public_plus_ur_v1",
        baseline_batch_output_dir=data_root / "eval_outputs" / "public_plus_ur_v1",
        min_macro_f1_delta=0.0,
        min_sample_macro_f1_delta=0.0,
        min_near_fall_f1_delta=0.02,
        min_recovery_f1_delta=0.02,
        max_fp_per_hour_delta=0.2,
        max_delay_delta=0.2,
        resume=True,
    )

    assert [step["step"] for step in plan] == [
        "prepare_ur_fall",
        "finalize_ur_fall",
        "train_public_plus_ur",
        "select_deployment_checkpoint",
        "evaluate_sample_classification",
        "package_release",
        "verify_release_bundle",
        "batch_inference",
        "compare_public_expected_state_vs_baseline",
        "compare_public_vs_baseline",
        "assess_public_round_promotion",
        "summarize_experiment_round",
        "check_experiment_round_complete",
    ]
    assert "scripts/select_deployment_checkpoint.py" in plan[3]["command"]
    assert "scripts/evaluate_sample_classification.py" in plan[4]["command"]
    assert "--write-video" in plan[7]["command"]
    assert "scripts/compare_expected_state_manifests.py" in plan[8]["command"]
    assert "--expected-state" in plan[8]["command"]
    assert "--baseline-sample-summary" in plan[9]["command"]
    assert "--expected-state-summary" in plan[9]["command"]
    assert "scripts/assess_experiment_promotion.py" in plan[10]["command"]
    assert str(data_root / "releases" / "public_plus_ur_v1_runtime") in plan[7]["command"]
    assert "verify-release" in plan[6]["command"]
    assert "scripts/summarize_experiment_round.py" in plan[-2]["command"]
    assert "scripts/check_experiment_round_complete.py" in plan[-1]["command"]
    assert "--resume" in plan[0]["command"]
    assert "--window-size" in plan[2]["command"]
    assert "32" in plan[2]["command"]
    assert "--stride" in plan[2]["command"]
    assert "8" in plan[2]["command"]
    assert "--seed" in plan[2]["command"]
    assert "3407" in plan[2]["command"]
    assert "--kinematic-feature-set" in plan[2]["command"]
    assert "v2" in plan[2]["command"]
    assert "--clip-focal-gamma" in plan[2]["command"]
    assert "1.5" in plan[2]["command"]
    assert "--quality-loss-weight" in plan[2]["command"]
    assert "0.05" in plan[2]["command"]
