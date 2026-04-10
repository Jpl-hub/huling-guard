from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _status(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False, "is_file": False}
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
    }


def _load_json(path: Path | None) -> Any | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def check_experiment_round_complete(
    *,
    run_name: str,
    training_summary_path: Path,
    sample_summary_path: Path | None = None,
    event_summary_path: Path | None = None,
    release_verification_path: Path | None = None,
    deployment_selection_path: Path | None = None,
    comparison_summary_path: Path | None = None,
    promotion_summary_path: Path | None = None,
    round_summary_path: Path | None = None,
) -> dict[str, Any]:
    artifacts = {
        "training_summary": _status(training_summary_path),
        "sample_summary": _status(sample_summary_path),
        "event_summary": _status(event_summary_path),
        "release_verification": _status(release_verification_path),
        "deployment_selection": _status(deployment_selection_path),
        "comparison_summary": _status(comparison_summary_path),
        "promotion_summary": _status(promotion_summary_path),
        "round_summary": _status(round_summary_path),
    }

    required_names = ["training_summary"]
    required_names.extend(
        name
        for name, path in (
            ("sample_summary", sample_summary_path),
            ("event_summary", event_summary_path),
            ("release_verification", release_verification_path),
            ("deployment_selection", deployment_selection_path),
            ("comparison_summary", comparison_summary_path),
            ("promotion_summary", promotion_summary_path),
            ("round_summary", round_summary_path),
        )
        if path is not None
    )

    missing = [name for name in required_names if not artifacts[name]["is_file"]]
    release_verification = _load_json(release_verification_path)
    round_summary = _load_json(round_summary_path)
    blocking_checks: list[dict[str, Any]] = []

    if release_verification_path is not None and release_verification is not None:
        blocking_checks.append(
            {
                "name": "release_verification_ok",
                "passed": bool(release_verification.get("ok", False)),
                "note": "发布包完整性校验必须通过",
            }
        )
    if round_summary_path is not None and round_summary is not None:
        artifacts_state = round_summary.get("artifacts", {})
        blocking_checks.append(
            {
                "name": "round_summary_has_training",
                "passed": True,
                "note": "当前轮总览报告已生成",
            }
        )
        if sample_summary_path is not None:
            blocking_checks.append(
                {
                    "name": "round_summary_has_sample_summary",
                    "passed": bool(artifacts_state.get("has_sample_summary", False)),
                    "note": "当前轮总览报告应包含样本级分类结果",
                }
            )
        if event_summary_path is not None:
            blocking_checks.append(
                {
                    "name": "round_summary_has_event_summary",
                    "passed": bool(artifacts_state.get("has_event_summary", False)),
                    "note": "当前轮总览报告应包含事件级结果",
                }
            )
        if release_verification_path is not None:
            blocking_checks.append(
                {
                    "name": "round_summary_has_release_verification",
                    "passed": bool(artifacts_state.get("has_release_verification", False)),
                    "note": "当前轮总览报告应包含发布包校验结果",
                }
            )
        if deployment_selection_path is not None:
            blocking_checks.append(
                {
                    "name": "round_summary_has_deployment_selection",
                    "passed": bool(artifacts_state.get("has_deployment_selection", False)),
                    "note": "当前轮总览报告应包含部署 checkpoint 选择结果",
                }
            )
        if comparison_summary_path is not None:
            blocking_checks.append(
                {
                    "name": "round_summary_has_comparison_summary",
                    "passed": bool(artifacts_state.get("has_comparison_summary", False)),
                    "note": "当前轮总览报告应包含与上一轮的结构化对比",
                }
            )
        if promotion_summary_path is not None:
            blocking_checks.append(
                {
                    "name": "round_summary_has_promotion_summary",
                    "passed": bool(artifacts_state.get("has_promotion_summary", False)),
                    "note": "当前轮总览报告应包含保留判读结果",
                }
            )

    failed_checks = [check for check in blocking_checks if not check["passed"]]
    return {
        "run_name": run_name,
        "complete": not missing and not failed_checks,
        "required_artifacts": required_names,
        "artifacts": artifacts,
        "missing": missing,
        "checks": blocking_checks,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# 轮次完成检查：{summary['run_name']}",
        "",
        f"- complete: {summary['complete']}",
        "",
        "## 产物文件",
    ]
    for name in summary["required_artifacts"]:
        info = summary["artifacts"][name]
        state = "ok" if info["is_file"] else "missing"
        lines.append(f"- {name}: {state} ({info['path']})")
    if summary["checks"]:
        lines.extend(["", "## 检查项"])
        for check in summary["checks"]:
            lines.append(f"- {check['name']}: {'pass' if check['passed'] else 'fail'} ({check['note']})")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--training-summary", type=Path, required=True)
    parser.add_argument("--sample-summary", type=Path)
    parser.add_argument("--event-summary", type=Path)
    parser.add_argument("--release-verification", type=Path)
    parser.add_argument("--deployment-selection", type=Path)
    parser.add_argument("--comparison-summary", type=Path)
    parser.add_argument("--promotion-summary", type=Path)
    parser.add_argument("--round-summary", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    summary = check_experiment_round_complete(
        run_name=args.run_name,
        training_summary_path=args.training_summary.resolve(),
        sample_summary_path=args.sample_summary.resolve() if args.sample_summary else None,
        event_summary_path=args.event_summary.resolve() if args.event_summary else None,
        release_verification_path=args.release_verification.resolve() if args.release_verification else None,
        deployment_selection_path=args.deployment_selection.resolve() if args.deployment_selection else None,
        comparison_summary_path=args.comparison_summary.resolve() if args.comparison_summary else None,
        promotion_summary_path=args.promotion_summary.resolve() if args.promotion_summary else None,
        round_summary_path=args.round_summary.resolve() if args.round_summary else None,
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
    print(markdown, end="")


if __name__ == "__main__":
    main()
