from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from experiment_artifacts import (
    build_base_experiment_step_outputs,
    build_event_summary_path,
)


def _status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
    }


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _load_sample_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8") as handle:
        return {
            str(payload.get("sample_id", "")).strip()
            for payload in (json.loads(line) for line in handle if line.strip())
            if str(payload.get("sample_id", "")).strip()
        }


def build_shell_script(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"cd {shlex.quote(summary['repo_root'])}",
            summary["recommended_command_shell"],
            "",
        ]
    )


def check_public_plus_ur_ready(
    *,
    repo_root: Path,
    data_root: Path,
    runtime_config_template: Path,
    batch_manifest: Path | None,
    python_bin: str,
    run_name: str,
    kinematic_feature_set: str = "v2",
    clip_focal_gamma: float = 0.0,
    baseline_run_name: str | None = None,
    baseline_batch_output_dir: Path | None = None,
) -> dict[str, Any]:
    required_files = {
        "runtime_config_template": _status(runtime_config_template),
        "caucafall_raw_manifest": _status(data_root / "raw" / "caucafall_manifest.jsonl"),
        "up_fall_raw_manifest": _status(data_root / "manifests" / "up_fall_valid.jsonl"),
        "ur_fall_raw_manifest": _status(data_root / "manifests" / "ur_fall_valid.jsonl"),
        "caucafall_pose_manifest": _status(data_root / "processed" / "poses_caucafall.jsonl"),
        "up_fall_pose_manifest": _status(data_root / "processed" / "poses_up_fall.jsonl"),
        "ur_fall_pose_manifest": _status(data_root / "processed" / "poses_ur_fall.jsonl"),
    }
    if batch_manifest is not None:
        required_files["batch_manifest"] = _status(batch_manifest)

    missing = [name for name, info in required_files.items() if not info["is_file"]]
    pose_coverage: dict[str, Any] = {}
    coverage_failures: list[str] = []
    coverage_pairs = [
        ("caucafall", data_root / "raw" / "caucafall_manifest.jsonl", data_root / "processed" / "poses_caucafall.jsonl"),
        ("up_fall", data_root / "manifests" / "up_fall_valid.jsonl", data_root / "processed" / "poses_up_fall.jsonl"),
        ("ur_fall", data_root / "manifests" / "ur_fall_valid.jsonl", data_root / "processed" / "poses_ur_fall.jsonl"),
    ]
    for dataset_name, raw_manifest, pose_manifest in coverage_pairs:
        if not raw_manifest.is_file() or not pose_manifest.is_file():
            pose_coverage[dataset_name] = {
                "ready": False,
                "reason": "missing_manifest",
                "raw_manifest": str(raw_manifest),
                "pose_manifest": str(pose_manifest),
            }
            continue
        raw_ids = _load_sample_ids(raw_manifest)
        pose_ids = _load_sample_ids(pose_manifest)
        missing_pose_ids = sorted(raw_ids.difference(pose_ids))
        extra_pose_ids = sorted(pose_ids.difference(raw_ids))
        dataset_summary = {
            "ready": len(missing_pose_ids) == 0,
            "raw_manifest": str(raw_manifest),
            "pose_manifest": str(pose_manifest),
            "raw_count": len(raw_ids),
            "pose_count": len(pose_ids),
            "matched_count": len(raw_ids.intersection(pose_ids)),
            "missing_pose_count": len(missing_pose_ids),
            "extra_pose_count": len(extra_pose_ids),
            "missing_pose_sample_ids_preview": missing_pose_ids[:10],
            "extra_pose_sample_ids_preview": extra_pose_ids[:10],
        }
        pose_coverage[dataset_name] = dataset_summary
        if missing_pose_ids:
            coverage_failures.append(dataset_name)

    command = [
        python_bin,
        "scripts/run_public_plus_ur_experiment.py",
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
        "--train",
        "--package-release",
        "--resume",
    ]
    if batch_manifest is not None:
        command.extend(["--batch-manifest", str(batch_manifest)])
        command.extend(["--batch-output-dir", str(data_root / "eval_outputs" / run_name)])
    if baseline_run_name is not None:
        command.extend(["--baseline-run-name", baseline_run_name])
    if baseline_batch_output_dir is not None:
        command.extend(["--baseline-batch-output-dir", str(baseline_batch_output_dir)])

    expected_step_outputs = {
        step: [str(path) for path in paths]
        for step, paths in build_base_experiment_step_outputs(
            data_root=data_root,
            run_name=run_name,
            previous_run_name=baseline_run_name,
            batch_output_dir=(data_root / "eval_outputs" / run_name) if batch_manifest is not None else None,
            package_release=True,
            prepare_ur=False,
            finalize_ur=False,
        ).items()
    }

    return {
        "ready": not missing and not coverage_failures,
        "repo_root": str(repo_root),
        "data_root": str(data_root),
        "run_name": run_name,
        "required_files": required_files,
        "missing": missing,
        "pose_coverage": pose_coverage,
        "coverage_failures": coverage_failures,
        "recommended_command": command,
        "recommended_command_shell": _shell_join(command),
        "expected_step_outputs": expected_step_outputs,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Public+UR 实验开卡前检查",
        "",
        f"- ready: {summary['ready']}",
        f"- run_name: {summary['run_name']}",
        "",
        "## 文件检查",
    ]
    for name, info in summary["required_files"].items():
        state = "ok" if info["is_file"] else "missing"
        lines.append(f"- {name}: {state} ({info['path']})")
    lines.extend(["", "## Pose 覆盖率"])
    for dataset_name, info in summary["pose_coverage"].items():
        if not info.get("ready", False):
            if info.get("reason") == "missing_manifest":
                lines.append(f"- {dataset_name}: missing_manifest")
                continue
            preview = ", ".join(info.get("missing_pose_sample_ids_preview", []))
            lines.append(
                f"- {dataset_name}: fail, missing_pose_count={info['missing_pose_count']}, preview={preview}"
            )
            continue
        lines.append(
            f"- {dataset_name}: ok, coverage={info['matched_count']}/{info['raw_count']}, extra_pose_count={info['extra_pose_count']}"
        )
    lines.extend(["", "## 建议命令", f"```bash\n{summary['recommended_command_shell']}\n```", "", "## 预期产物"])
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
    parser.add_argument("--batch-manifest", type=Path)
    parser.add_argument("--run-name", default="public_plus_ur_v1")
    parser.add_argument("--kinematic-feature-set", default="v2")
    parser.add_argument("--clip-focal-gamma", type=float, default=0.0)
    parser.add_argument("--baseline-run-name")
    parser.add_argument("--baseline-batch-output-dir", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--output-shell", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    runtime_template = args.runtime_config_template
    if not runtime_template.is_absolute():
        runtime_template = (repo_root / runtime_template).resolve()
    batch_manifest = args.batch_manifest.resolve() if args.batch_manifest is not None else None
    baseline_batch_output_dir = (
        args.baseline_batch_output_dir.resolve() if args.baseline_batch_output_dir is not None else None
    )

    summary = check_public_plus_ur_ready(
        repo_root=repo_root,
        data_root=data_root,
        runtime_config_template=runtime_template,
        batch_manifest=batch_manifest,
        python_bin=args.python,
        run_name=args.run_name,
        kinematic_feature_set=args.kinematic_feature_set,
        clip_focal_gamma=args.clip_focal_gamma,
        baseline_run_name=args.baseline_run_name,
        baseline_batch_output_dir=baseline_batch_output_dir,
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
