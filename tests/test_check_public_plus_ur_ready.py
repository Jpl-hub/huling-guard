from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_public_plus_ur_ready import build_markdown, build_shell_script, check_public_plus_ur_ready


def test_check_public_plus_ur_ready_reports_missing_and_command(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    runtime_template = repo_root / "configs" / "runtime_room.yaml"
    repo_root.joinpath("configs").mkdir(parents=True)
    runtime_template.write_text("runtime: {}\n", encoding="utf-8")
    (data_root / "raw").mkdir(parents=True)
    (data_root / "manifests").mkdir(parents=True)
    (data_root / "processed").mkdir(parents=True)

    summary = check_public_plus_ur_ready(
        repo_root=repo_root,
        data_root=data_root,
        runtime_config_template=runtime_template,
        batch_manifest=None,
        python_bin="python",
        run_name="public_plus_ur_v1",
        clip_focal_gamma=1.5,
        quality_loss_weight=0.05,
    )

    assert summary["ready"] is False
    assert "ur_fall_pose_manifest" in summary["missing"]
    assert "scripts/run_public_plus_ur_experiment.py" in summary["recommended_command"]
    assert "--kinematic-feature-set" in summary["recommended_command"]
    assert "--clip-focal-gamma" in summary["recommended_command"]
    assert "1.5" in summary["recommended_command"]
    assert "--quality-loss-weight" in summary["recommended_command"]
    assert "0.05" in summary["recommended_command"]
    assert "--resume" in summary["recommended_command"]
    assert "train_public_plus_ur" in summary["expected_step_outputs"]
    assert "public_plus_ur_v1_completion.json" in build_markdown(summary)
    assert "set -euo pipefail" in build_shell_script(summary)


def test_check_public_plus_ur_ready_detects_incomplete_pose_coverage(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    runtime_template = repo_root / "configs" / "runtime_room.yaml"
    repo_root.joinpath("configs").mkdir(parents=True)
    runtime_template.write_text("runtime: {}\n", encoding="utf-8")

    raw_dir = data_root / "raw"
    manifest_dir = data_root / "manifests"
    processed_dir = data_root / "processed"
    raw_dir.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)

    (raw_dir / "caucafall_manifest.jsonl").write_text(
        '{"sample_id":"c1"}\n',
        encoding="utf-8",
    )
    (manifest_dir / "up_fall_valid.jsonl").write_text(
        '{"sample_id":"u1"}\n{"sample_id":"u2"}\n',
        encoding="utf-8",
    )
    (manifest_dir / "ur_fall_valid.jsonl").write_text(
        '{"sample_id":"r1"}\n',
        encoding="utf-8",
    )
    (processed_dir / "poses_caucafall.jsonl").write_text(
        '{"sample_id":"c1"}\n',
        encoding="utf-8",
    )
    (processed_dir / "poses_up_fall.jsonl").write_text(
        '{"sample_id":"u1"}\n',
        encoding="utf-8",
    )
    (processed_dir / "poses_ur_fall.jsonl").write_text(
        '{"sample_id":"r1"}\n',
        encoding="utf-8",
    )

    summary = check_public_plus_ur_ready(
        repo_root=repo_root,
        data_root=data_root,
        runtime_config_template=runtime_template,
        batch_manifest=None,
        python_bin="python",
        run_name="public_plus_ur_v1",
        clip_focal_gamma=1.5,
    )

    assert summary["ready"] is False
    assert summary["coverage_failures"] == ["up_fall"]
    assert summary["pose_coverage"]["up_fall"]["missing_pose_count"] == 1
    markdown = build_markdown(summary)
    assert "## Pose 覆盖率" in markdown
    assert "up_fall: fail" in markdown


def test_check_public_plus_ur_ready_includes_baseline_compare_outputs(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    runtime_template = repo_root / "configs" / "runtime_room.yaml"
    repo_root.joinpath("configs").mkdir(parents=True)
    runtime_template.write_text("runtime: {}\n", encoding="utf-8")
    (data_root / "raw").mkdir(parents=True)
    (data_root / "manifests").mkdir(parents=True)
    (data_root / "processed").mkdir(parents=True)

    for path, rows in (
        (data_root / "raw" / "caucafall_manifest.jsonl", ['{"sample_id":"c1"}\n']),
        (data_root / "manifests" / "up_fall_valid.jsonl", ['{"sample_id":"u1"}\n']),
        (data_root / "manifests" / "ur_fall_valid.jsonl", ['{"sample_id":"r1"}\n']),
        (data_root / "processed" / "poses_caucafall.jsonl", ['{"sample_id":"c1"}\n']),
        (data_root / "processed" / "poses_up_fall.jsonl", ['{"sample_id":"u1"}\n']),
        (data_root / "processed" / "poses_ur_fall.jsonl", ['{"sample_id":"r1"}\n']),
    ):
        path.write_text("".join(rows), encoding="utf-8")

    summary = check_public_plus_ur_ready(
        repo_root=repo_root,
        data_root=data_root,
        runtime_config_template=runtime_template,
        batch_manifest=None,
        python_bin="python",
        run_name="public_plus_ur_v4",
        clip_focal_gamma=1.5,
        baseline_run_name="public_plus_ur_v1",
    )

    assert summary["ready"] is True
    assert "--baseline-run-name" in summary["recommended_command"]
    assert "--kinematic-feature-set" in summary["recommended_command"]
    assert "--clip-focal-gamma" in summary["recommended_command"]
    assert "compare_public_vs_baseline" in summary["expected_step_outputs"]
    assert "assess_public_round_promotion" in summary["expected_step_outputs"]
