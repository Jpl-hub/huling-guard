from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_refined_experiment_ready import build_markdown, build_shell_script, check_refined_experiment_ready


def test_check_refined_experiment_ready_reports_missing_and_command(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    runtime_template = repo_root / "configs" / "runtime_room.yaml"
    train_interval_labels = data_root / "review" / "interval_labels.json"
    repo_root.joinpath("configs").mkdir(parents=True)
    data_root.joinpath("review").mkdir(parents=True)
    runtime_template.write_text("runtime: {}\n", encoding="utf-8")
    train_interval_labels.write_text('{"intervals": []}\n', encoding="utf-8")

    summary = check_refined_experiment_ready(
        repo_root=repo_root,
        data_root=data_root,
        runtime_config_template=runtime_template,
        train_interval_labels=train_interval_labels,
        batch_manifest=None,
        baseline_run_name=None,
        baseline_batch_output_dir=None,
        python_bin="python",
        run_name="public_plus_ur_refined_v1",
        clip_focal_gamma=1.5,
    )

    assert summary["ready"] is False
    assert "caucafall_raw_manifest" in summary["missing"]
    assert "scripts/run_public_plus_ur_refined_experiment.py" in summary["recommended_command"]
    assert "--kinematic-feature-set" in summary["recommended_command"]
    assert "--clip-focal-gamma" in summary["recommended_command"]
    assert "1.5" in summary["recommended_command"]
    assert "--resume" in summary["recommended_command"]
    assert "train_public_plus_ur_refined" in summary["expected_step_outputs"]
    assert "public_plus_ur_refined_v1_completion.json" in build_markdown(summary)
    assert "set -euo pipefail" in build_shell_script(summary)
