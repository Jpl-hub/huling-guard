import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_runtime_release import package_runtime_release
from huling_guard.runtime.release import (
    format_runtime_release_verification,
    load_runtime_release_bundle,
    verify_runtime_release_bundle,
)


def test_package_runtime_release_copies_required_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "best.pt").write_bytes(b"checkpoint")
    (run_dir / "selected.pt").write_bytes(b"selected-checkpoint")
    (run_dir / "summary.json").write_text(
        json.dumps({"best_epoch": 7, "best_metrics": {"macro_f1": 0.42}}, ensure_ascii=True),
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text("# summary\n", encoding="utf-8")
    (run_dir / "deployment_selection.json").write_text(
        json.dumps({"selected": {"epoch": 11, "checkpoint_path": str(run_dir / "selected.pt")}}, ensure_ascii=True),
        encoding="utf-8",
    )
    (run_dir / "deployment_selection.md").write_text("# selection\n", encoding="utf-8")

    train_config = tmp_path / "train.yaml"
    runtime_config = tmp_path / "runtime.yaml"
    train_config.write_text("data: {}\n", encoding="utf-8")
    runtime_config.write_text("runtime: {}\n", encoding="utf-8")

    output_dir = tmp_path / "release"
    manifest_path = package_runtime_release(
        run_dir=run_dir,
        train_config_path=train_config,
        runtime_config_path=runtime_config,
        output_dir=output_dir,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["layout_version"] == 2
    assert "generated_at_utc" in manifest
    assert manifest["best_epoch"] == 7
    assert manifest["checkpoint"] == "checkpoints/selected.pt"
    assert manifest["checkpoint_role"] == "selected"
    assert manifest["selected_epoch"] == 11
    assert manifest["train_config"] == "config/train_config.yaml"
    assert manifest["runtime_config"] == "config/runtime_config.yaml"
    assert manifest["artifacts"]["checkpoint"]["path"] == "checkpoints/selected.pt"
    assert manifest["artifacts"]["checkpoint"]["size_bytes"] > 0
    assert len(manifest["artifacts"]["checkpoint"]["sha256"]) == 64
    assert (output_dir / "reports" / "summary.json").is_file()
    assert (output_dir / "reports" / "summary.md").is_file()
    assert (output_dir / "reports" / "deployment_selection.json").is_file()
    assert (output_dir / "reports" / "deployment_selection.md").is_file()
    assert (output_dir / "LAUNCH_RUNTIME.txt").is_file()

    bundle = load_runtime_release_bundle(output_dir)
    assert bundle.checkpoint_path == output_dir / "checkpoints" / "selected.pt"
    assert bundle.train_config_path == output_dir / "config" / "train_config.yaml"
    assert bundle.runtime_config_path == output_dir / "config" / "runtime_config.yaml"

    verification = verify_runtime_release_bundle(output_dir)
    assert verification["ok"] is True
    assert verification["checked_artifacts"] >= 4
    assert "运行时发布包校验" in format_runtime_release_verification(verification)


def test_verify_runtime_release_bundle_detects_modified_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "best.pt").write_bytes(b"checkpoint")
    (run_dir / "summary.json").write_text(
        json.dumps({"best_epoch": 3, "best_metrics": {"macro_f1": 0.38}}, ensure_ascii=True),
        encoding="utf-8",
    )

    train_config = tmp_path / "train.yaml"
    runtime_config = tmp_path / "runtime.yaml"
    train_config.write_text("data: {}\n", encoding="utf-8")
    runtime_config.write_text("runtime: {}\n", encoding="utf-8")

    output_dir = tmp_path / "release"
    package_runtime_release(
        run_dir=run_dir,
        train_config_path=train_config,
        runtime_config_path=runtime_config,
        output_dir=output_dir,
    )

    checkpoint_path = output_dir / "checkpoints" / "best.pt"
    checkpoint_path.write_bytes(b"tampered")

    verification = verify_runtime_release_bundle(output_dir)
    checkpoint_check = next(check for check in verification["checks"] if check["name"] == "checkpoint")
    assert verification["ok"] is False
    assert checkpoint_check["status"] == "mismatch"
