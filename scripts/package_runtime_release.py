from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import yaml


def _copy_if_exists(source: Path, target: Path) -> Path | None:
    if not source.is_file():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_entry(path: Path | None, release_dir: Path) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return {
        "path": path.relative_to(release_dir).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _resolve_optional_path(value: str | None, *, base_dir: Path) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    lookup = [base_dir / candidate, Path.cwd() / candidate]
    for item in lookup:
        if item.exists():
            return item.resolve()
    return None


def _prepare_runtime_config(runtime_config: Path, output: Path) -> tuple[Path, Path | None]:
    runtime_config_target = output / "config" / "runtime_config.yaml"
    payload = yaml.safe_load(runtime_config.read_text(encoding="utf-8"))
    room = payload.get("room") if isinstance(payload, dict) else None
    prior_target: Path | None = None
    if isinstance(room, dict):
        prior_source = _resolve_optional_path(room.get("prior_path"), base_dir=runtime_config.parent)
        if prior_source is not None and prior_source.is_file():
            prior_target = output / "config" / prior_source.name
            _copy_if_exists(prior_source, prior_target)
            room["prior_path"] = prior_target.relative_to(runtime_config_target.parent).as_posix()
    runtime_config_target.parent.mkdir(parents=True, exist_ok=True)
    runtime_config_target.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return runtime_config_target, prior_target


def package_runtime_release(
    *,
    run_dir: str | Path,
    train_config_path: str | Path,
    runtime_config_path: str | Path,
    output_dir: str | Path,
    checkpoint_path: str | Path | None = None,
    selection_summary_path: str | Path | None = None,
) -> Path:
    run_path = Path(run_dir).resolve()
    train_config = Path(train_config_path).resolve()
    runtime_config = Path(runtime_config_path).resolve()
    if checkpoint_path is not None:
        checkpoint = Path(checkpoint_path).resolve()
    else:
        checkpoint = run_path / "selected.pt"
        if not checkpoint.is_file():
            checkpoint = run_path / "best.pt"
    selection_summary = (
        Path(selection_summary_path).resolve()
        if selection_summary_path is not None
        else run_path / "deployment_selection.json"
    )
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if not train_config.is_file():
        raise FileNotFoundError(train_config)
    if not runtime_config.is_file():
        raise FileNotFoundError(runtime_config)

    output = Path(output_dir).resolve()
    checkpoint_target = output / "checkpoints" / checkpoint.name
    train_config_target = output / "config" / "train_config.yaml"
    summary_json_target = output / "reports" / "summary.json"
    summary_md_target = output / "reports" / "summary.md"
    selection_json_target = output / "reports" / "deployment_selection.json"
    selection_md_target = output / "reports" / "deployment_selection.md"

    _copy_if_exists(checkpoint, checkpoint_target)
    _copy_if_exists(train_config, train_config_target)
    runtime_config_target, prior_target = _prepare_runtime_config(runtime_config, output)
    _copy_if_exists(run_path / "summary.json", summary_json_target)
    _copy_if_exists(run_path / "summary.md", summary_md_target)
    _copy_if_exists(selection_summary, selection_json_target)
    _copy_if_exists(selection_summary.with_suffix(".md"), selection_md_target)

    def _rel(path: Path | None) -> str | None:
        if path is None or not path.exists():
            return None
        return path.relative_to(output).as_posix()

    manifest: dict[str, Any] = {
        "layout_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_path),
        "release_dir": str(output),
        "checkpoint": _rel(checkpoint_target),
        "checkpoint_role": "selected" if checkpoint.name == "selected.pt" else "best",
        "train_config": _rel(train_config_target),
        "runtime_config": _rel(runtime_config_target),
        "scene_prior": _rel(prior_target),
        "reports": {
            "summary_json": _rel(summary_json_target),
            "summary_md": _rel(summary_md_target),
            "deployment_selection_json": _rel(selection_json_target),
            "deployment_selection_md": _rel(selection_md_target),
        },
    }
    if summary_json_target.is_file():
        summary = json.loads(summary_json_target.read_text(encoding="utf-8"))
        manifest["best_epoch"] = summary.get("best_epoch")
        manifest["best_metrics"] = summary.get("best_metrics")
    if selection_json_target.is_file():
        selection_summary_payload = json.loads(selection_json_target.read_text(encoding="utf-8"))
        manifest["selected_epoch"] = selection_summary_payload.get("selected", {}).get("epoch")
        manifest["selection_rule"] = selection_summary_payload.get("selection_rule")

    launch_instructions = "\n".join(
        [
            "从仓库根目录启动运行时服务：",
            "PYTHONPATH=src python -m huling_guard.cli serve-release \\",
            f"  --release-dir {output}",
            "",
        ]
    )
    launch_path = output / "LAUNCH_RUNTIME.txt"
    launch_path.parent.mkdir(parents=True, exist_ok=True)
    launch_path.write_text(launch_instructions, encoding="utf-8")
    manifest["artifacts"] = {
        "checkpoint": _artifact_entry(checkpoint_target, output),
        "train_config": _artifact_entry(train_config_target, output),
        "runtime_config": _artifact_entry(runtime_config_target, output),
        "scene_prior": _artifact_entry(prior_target, output),
        "summary_json": _artifact_entry(summary_json_target, output),
        "summary_md": _artifact_entry(summary_md_target, output),
        "deployment_selection_json": _artifact_entry(selection_json_target, output),
        "deployment_selection_md": _artifact_entry(selection_md_target, output),
        "launch_instructions": _artifact_entry(launch_path, output),
    }

    manifest_path = output / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--train-config", type=Path, required=True)
    parser.add_argument("--runtime-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--selection-summary", type=Path)
    args = parser.parse_args()

    manifest_path = package_runtime_release(
        run_dir=args.run_dir,
        train_config_path=args.train_config,
        runtime_config_path=args.runtime_config,
        output_dir=args.output_dir,
        checkpoint_path=args.checkpoint,
        selection_summary_path=args.selection_summary,
    )
    print(f"[write] {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
