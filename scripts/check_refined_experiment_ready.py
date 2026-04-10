from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from experiment_artifacts import (
    build_comparison_artifact_paths,
    build_event_summary_path,
    build_refined_experiment_step_outputs,
)


def _status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
    }


def _metric_line(title: str, value: Any) -> str:
    return f"- {title}: {value}"


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def build_shell_script(summary: dict[str, Any]) -> str:
    command = summary["recommended_command"]
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"cd {shlex.quote(summary['repo_root'])}",
            _shell_join(command),
            "",
        ]
    )


def check_refined_experiment_ready(
    *,
    repo_root: Path,
    data_root: Path,
    runtime_config_template: Path,
    train_interval_labels: Path,
    batch_manifest: Path | None,
    baseline_run_name: str | None,
    baseline_batch_output_dir: Path | None,
    python_bin: str,
    run_name: str,
    kinematic_feature_set: str = "v2",
    clip_focal_gamma: float = 0.0,
) -> dict[str, Any]:
    required_files = {
        "runtime_config_template": _status(runtime_config_template),
        "train_interval_labels": _status(train_interval_labels),
        "caucafall_raw_manifest": _status(data_root / "raw" / "caucafall_manifest.jsonl"),
        "up_fall_raw_manifest": _status(data_root / "manifests" / "up_fall_valid.jsonl"),
        "ur_fall_raw_manifest": _status(data_root / "manifests" / "ur_fall_valid.jsonl"),
        "caucafall_pose_manifest": _status(data_root / "processed" / "poses_caucafall.jsonl"),
        "up_fall_pose_manifest": _status(data_root / "processed" / "poses_up_fall.jsonl"),
        "ur_fall_pose_manifest": _status(data_root / "processed" / "poses_ur_fall.jsonl"),
    }
    if batch_manifest is not None:
        required_files["batch_manifest"] = _status(batch_manifest)
    if baseline_run_name is not None:
        comparison_artifacts = build_comparison_artifact_paths(
            data_root=data_root,
            run_name=run_name,
            previous_run_name=baseline_run_name,
        )
        required_files["baseline_train_summary"] = _status(comparison_artifacts["previous_train_summary"])
    if baseline_batch_output_dir is not None:
        required_files["baseline_event_summary"] = _status(build_event_summary_path(baseline_batch_output_dir))

    missing = [name for name, info in required_files.items() if not info["is_file"]]
    refined_command = [
        python_bin,
        "scripts/run_public_plus_ur_refined_experiment.py",
        "--python",
        python_bin,
        "--data-root",
        str(data_root),
        "--run-name",
        run_name,
        "--kinematic-feature-set",
        kinematic_feature_set,
        "--clip-focal-gamma",
        str(clip_focal_gamma),
        "--train-interval-labels",
        str(train_interval_labels),
        "--runtime-config-template",
        str(runtime_config_template),
        "--train",
        "--package-release",
        "--resume",
    ]
    if batch_manifest is not None:
        refined_command.extend(["--batch-manifest", str(batch_manifest)])
        refined_command.extend(
            ["--batch-output-dir", str(data_root / "eval_outputs" / run_name)]
        )
    if baseline_run_name is not None:
        refined_command.extend(["--baseline-run-name", baseline_run_name])
    if baseline_batch_output_dir is not None:
        refined_command.extend(["--baseline-batch-output-dir", str(baseline_batch_output_dir)])

    expected_step_outputs = {
        step: [str(path) for path in paths]
        for step, paths in build_refined_experiment_step_outputs(
            data_root=data_root,
            run_name=run_name,
            previous_run_name=baseline_run_name,
            batch_output_dir=(data_root / "eval_outputs" / run_name) if batch_manifest is not None else None,
            package_release=True,
        ).items()
    }

    return {
        "ready": not missing,
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "run_name": run_name,
        "required_files": required_files,
        "missing": missing,
        "recommended_command": refined_command,
        "recommended_command_shell": _shell_join(refined_command),
        "expected_step_outputs": expected_step_outputs,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Refined 实验开卡前检查",
        "",
        _metric_line("ready", summary["ready"]),
        _metric_line("run_name", summary["run_name"]),
        "",
        "## 文件检查",
    ]
    for name, info in summary["required_files"].items():
        state = "ok" if info["is_file"] else "missing"
        lines.append(f"- {name}: {state} ({info['path']})")
    lines.extend(["", "## 建议命令", f"```bash\n{summary['recommended_command_shell']}\n```"])
    lines.extend(["", "## 预期产物"])
    for step_name, outputs in summary["expected_step_outputs"].items():
        lines.append(f"- {step_name}:")
        for output in outputs:
            lines.append(f"  - {output}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    parser.add_argument("--runtime-config-template", type=Path, default=Path("configs/runtime_room.yaml"))
    parser.add_argument("--train-interval-labels", type=Path, required=True)
    parser.add_argument("--batch-manifest", type=Path)
    parser.add_argument("--kinematic-feature-set", default="v2")
    parser.add_argument("--clip-focal-gamma", type=float, default=0.0)
    parser.add_argument("--baseline-run-name")
    parser.add_argument("--baseline-batch-output-dir", type=Path)
    parser.add_argument("--run-name", default="public_plus_ur_refined_v1")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--output-shell", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    runtime_template = args.runtime_config_template
    if not runtime_template.is_absolute():
        runtime_template = (repo_root / runtime_template).resolve()
    train_interval_labels = args.train_interval_labels
    if not train_interval_labels.is_absolute():
        train_interval_labels = (repo_root / train_interval_labels).resolve()
    batch_manifest = args.batch_manifest.resolve() if args.batch_manifest is not None else None
    baseline_batch_output_dir = (
        args.baseline_batch_output_dir.resolve() if args.baseline_batch_output_dir is not None else None
    )

    summary = check_refined_experiment_ready(
        repo_root=repo_root,
        data_root=data_root,
        runtime_config_template=runtime_template,
        train_interval_labels=train_interval_labels,
        batch_manifest=batch_manifest,
        baseline_run_name=args.baseline_run_name,
        baseline_batch_output_dir=baseline_batch_output_dir,
        python_bin=args.python,
        run_name=args.run_name,
        kinematic_feature_set=args.kinematic_feature_set,
        clip_focal_gamma=args.clip_focal_gamma,
    )
    markdown = build_markdown(summary)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {args.output_json}", flush=True)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    if args.output_shell is not None:
        args.output_shell.parent.mkdir(parents=True, exist_ok=True)
        args.output_shell.write_text(build_shell_script(summary), encoding="utf-8")
        print(f"[write] {args.output_shell}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
