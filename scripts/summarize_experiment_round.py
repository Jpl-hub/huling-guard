from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path | None) -> Any | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_round_summary(
    *,
    run_name: str,
    training_summary: dict[str, Any],
    sample_summary: dict[str, Any] | None = None,
    event_summary: dict[str, Any] | None = None,
    release_verification: dict[str, Any] | None = None,
    deployment_selection: dict[str, Any] | None = None,
    comparison_summary: dict[str, Any] | None = None,
    promotion_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    best_metrics = training_summary.get("best_metrics", {})
    payload: dict[str, Any] = {
        "run_name": run_name,
        "training": {
            "best_epoch": training_summary.get("best_epoch"),
            "macro_f1": float(best_metrics.get("macro_f1", 0.0)),
            "accuracy": float(best_metrics.get("accuracy", 0.0)),
            "weighted_f1": float(best_metrics.get("weighted_f1", 0.0)),
            "risk_accuracy": float(best_metrics.get("risk_accuracy", 0.0)),
        },
        "artifacts": {
            "has_sample_summary": sample_summary is not None,
            "has_event_summary": event_summary is not None,
            "has_release_verification": release_verification is not None,
            "has_deployment_selection": deployment_selection is not None,
            "has_comparison_summary": comparison_summary is not None,
            "has_promotion_summary": promotion_summary is not None,
        },
    }
    if sample_summary is not None:
        payload["sample_classification"] = {
            "num_samples": int(sample_summary.get("num_samples", 0)),
            "num_windows": int(sample_summary.get("num_windows", 0)),
            "accuracy": float(sample_summary.get("accuracy", 0.0)),
            "macro_f1": float(sample_summary.get("macro_f1", 0.0)),
            "weighted_f1": float(sample_summary.get("weighted_f1", 0.0)),
        }
    if event_summary is not None:
        payload["event"] = {
            "precision": float(event_summary.get("precision", 0.0)),
            "recall": float(event_summary.get("recall", 0.0)),
            "f1": float(event_summary.get("f1", 0.0)),
            "false_positives_per_hour": float(event_summary.get("false_positives_per_hour", 0.0)),
            "mean_abs_delay_seconds": float(event_summary.get("mean_abs_delay_seconds", 0.0)),
        }
    if release_verification is not None:
        payload["release_verification"] = {
            "ok": bool(release_verification.get("ok", False)),
            "checked_artifacts": int(release_verification.get("checked_artifacts", 0)),
        }
    if deployment_selection is not None:
        selected = deployment_selection.get("selected", {})
        sample_metrics = selected.get("sample_metrics", {})
        train_metrics = selected.get("train_metrics", {})
        payload["deployment_selection"] = {
            "epoch": int(selected.get("epoch", 0)),
            "checkpoint_path": selected.get("checkpoint_path"),
            "sample_macro_f1": float(sample_metrics.get("macro_f1", 0.0)),
            "sample_weighted_f1": float(sample_metrics.get("weighted_f1", 0.0)),
            "train_macro_f1": float(train_metrics.get("macro_f1", 0.0)),
        }
    if comparison_summary is not None:
        training = comparison_summary.get("training", {})
        payload["comparison"] = {
            "macro_f1_delta": float(training.get("macro_f1", {}).get("delta", 0.0)),
            "accuracy_delta": float(training.get("accuracy", {}).get("delta", 0.0)),
            "near_fall_f1_delta": float(training.get("per_class", {}).get("near_fall", {}).get("delta_f1", 0.0)),
            "recovery_f1_delta": float(training.get("per_class", {}).get("recovery", {}).get("delta_f1", 0.0)),
        }
        if "event" in comparison_summary:
            payload["comparison"]["false_positives_per_hour_delta"] = float(
                comparison_summary["event"].get("false_positives_per_hour", {}).get("delta", 0.0)
            )
            payload["comparison"]["mean_abs_delay_delta"] = float(
                comparison_summary["event"].get("mean_abs_delay_seconds", {}).get("delta", 0.0)
            )
        if "expected_state" in comparison_summary:
            expected_state = comparison_summary["expected_state"]
            payload["comparison"]["expected_state"] = expected_state.get("expected_state")
            payload["comparison"]["expected_state_with_incidents_rate_delta"] = float(
                expected_state.get("delta", {}).get("with_incidents_rate", 0.0)
            )
            payload["comparison"]["expected_state_dominant_drift_rate_delta"] = float(
                expected_state.get("delta", {}).get("dominant_drift_rate", 0.0)
            )
            payload["comparison"]["expected_state_incident_sum_delta"] = float(
                expected_state.get("delta", {}).get("incident_sum", 0.0)
            )
    if promotion_summary is not None:
        payload["promotion"] = {
            "verdict": promotion_summary.get("verdict"),
            "passed_checks": int(promotion_summary.get("passed_checks", 0)),
            "total_checks": int(promotion_summary.get("total_checks", 0)),
        }
    return payload


def build_markdown(summary: dict[str, Any]) -> str:
    training = summary["training"]
    lines = [
        f"# 实验轮次总览：{summary['run_name']}",
        "",
        "## 训练结果",
        f"- best_epoch: {training['best_epoch']}",
        f"- macro_f1: {training['macro_f1']:.4f}",
        f"- accuracy: {training['accuracy']:.4f}",
        f"- weighted_f1: {training['weighted_f1']:.4f}",
        f"- risk_accuracy: {training['risk_accuracy']:.4f}",
        "",
        "## 产物状态",
    ]
    for name, value in summary["artifacts"].items():
        lines.append(f"- {name}: {value}")

    sample = summary.get("sample_classification")
    if sample is not None:
        lines.extend(
            [
                "",
                "## 样本级分类结果",
                f"- num_samples: {sample['num_samples']}",
                f"- num_windows: {sample['num_windows']}",
                f"- accuracy: {sample['accuracy']:.4f}",
                f"- macro_f1: {sample['macro_f1']:.4f}",
                f"- weighted_f1: {sample['weighted_f1']:.4f}",
            ]
        )

    event = summary.get("event")
    if event is not None:
        lines.extend(
            [
                "",
                "## 事件级结果",
                f"- precision: {event['precision']:.4f}",
                f"- recall: {event['recall']:.4f}",
                f"- f1: {event['f1']:.4f}",
                f"- 每小时误报数: {event['false_positives_per_hour']:.4f}",
                f"- 平均绝对延迟(秒): {event['mean_abs_delay_seconds']:.4f}",
            ]
        )

    release_verification = summary.get("release_verification")
    if release_verification is not None:
        lines.extend(
            [
                "",
                "## 发布包校验",
                f"- ok: {release_verification['ok']}",
                f"- checked_artifacts: {release_verification['checked_artifacts']}",
            ]
        )

    deployment_selection = summary.get("deployment_selection")
    if deployment_selection is not None:
        lines.extend(
            [
                "",
                "## 部署选择",
                f"- epoch: {deployment_selection['epoch']}",
                f"- checkpoint: {deployment_selection['checkpoint_path']}",
                f"- sample_macro_f1: {deployment_selection['sample_macro_f1']:.4f}",
                f"- sample_weighted_f1: {deployment_selection['sample_weighted_f1']:.4f}",
                f"- train_macro_f1: {deployment_selection['train_macro_f1']:.4f}",
            ]
        )

    comparison = summary.get("comparison")
    if comparison is not None:
        lines.extend(
            [
                "",
                "## 与上一轮对比",
                f"- macro_f1_delta: {comparison['macro_f1_delta']:+.4f}",
                f"- accuracy_delta: {comparison['accuracy_delta']:+.4f}",
                f"- near_fall_f1_delta: {comparison['near_fall_f1_delta']:+.4f}",
                f"- recovery_f1_delta: {comparison['recovery_f1_delta']:+.4f}",
            ]
        )
        if "false_positives_per_hour_delta" in comparison:
            lines.append(f"- false_positives_per_hour_delta: {comparison['false_positives_per_hour_delta']:+.4f}")
        if "mean_abs_delay_delta" in comparison:
            lines.append(f"- mean_abs_delay_delta: {comparison['mean_abs_delay_delta']:+.4f}")
        if "expected_state_with_incidents_rate_delta" in comparison:
            lines.append(
                f"- expected_state({comparison.get('expected_state', 'n/a')}) with_incidents_rate_delta: "
                f"{comparison['expected_state_with_incidents_rate_delta']:+.4f}"
            )
        if "expected_state_dominant_drift_rate_delta" in comparison:
            lines.append(
                f"- expected_state({comparison.get('expected_state', 'n/a')}) dominant_drift_rate_delta: "
                f"{comparison['expected_state_dominant_drift_rate_delta']:+.4f}"
            )
        if "expected_state_incident_sum_delta" in comparison:
            lines.append(
                f"- expected_state({comparison.get('expected_state', 'n/a')}) incident_sum_delta: "
                f"{comparison['expected_state_incident_sum_delta']:+.0f}"
            )

    promotion = summary.get("promotion")
    if promotion is not None:
        lines.extend(
            [
                "",
                "## 当前轮保留判读",
                f"- verdict: {promotion['verdict']}",
                f"- passed_checks: {promotion['passed_checks']}/{promotion['total_checks']}",
            ]
        )

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
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    summary = build_round_summary(
        run_name=args.run_name,
        training_summary=_load_json(args.training_summary.resolve()),
        sample_summary=_load_json(args.sample_summary.resolve()) if args.sample_summary else None,
        event_summary=_load_json(args.event_summary.resolve()) if args.event_summary else None,
        release_verification=_load_json(args.release_verification.resolve()) if args.release_verification else None,
        deployment_selection=_load_json(args.deployment_selection.resolve()) if args.deployment_selection else None,
        comparison_summary=_load_json(args.comparison_summary.resolve()) if args.comparison_summary else None,
        promotion_summary=_load_json(args.promotion_summary.resolve()) if args.promotion_summary else None,
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
