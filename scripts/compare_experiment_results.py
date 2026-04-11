from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path | None) -> Any | None:
    if path is None:
        return None
    resolved = path.resolve()
    if not resolved.is_file():
        print(f"[skip-missing] optional summary not found: {resolved}", flush=True)
        return None
    return _load_json(resolved)


def _delta(candidate: float, baseline: float) -> float:
    return candidate - baseline


def _format_metric(value: float) -> str:
    return f"{value:.4f}"


def _format_delta(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.4f}"


def _extract_train_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    best_metrics = summary.get("best_metrics", {})
    return {
        "best_epoch": summary.get("best_epoch"),
        "macro_f1": float(best_metrics.get("macro_f1", 0.0)),
        "accuracy": float(best_metrics.get("accuracy", 0.0)),
        "weighted_f1": float(best_metrics.get("weighted_f1", 0.0)),
        "risk_accuracy": float(best_metrics.get("risk_accuracy", 0.0)),
        "per_class": best_metrics.get("per_class", {}),
        "train_class_counts": summary.get("train_class_counts", {}),
    }


def _extract_sample_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "num_samples": int(summary.get("num_samples", 0)),
        "num_windows": int(summary.get("num_windows", 0)),
        "accuracy": float(summary.get("accuracy", 0.0)),
        "macro_f1": float(summary.get("macro_f1", 0.0)),
        "weighted_f1": float(summary.get("weighted_f1", 0.0)),
        "per_class": summary.get("per_class", {}),
    }


def build_comparison_payload(
    *,
    baseline_train_summary: dict[str, Any],
    candidate_train_summary: dict[str, Any],
    baseline_event_summary: dict[str, Any] | None = None,
    candidate_event_summary: dict[str, Any] | None = None,
    baseline_sample_summary: dict[str, Any] | None = None,
    candidate_sample_summary: dict[str, Any] | None = None,
    expected_state_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline_train = _extract_train_metrics(baseline_train_summary)
    candidate_train = _extract_train_metrics(candidate_train_summary)

    per_class_labels = sorted(
        set(baseline_train["per_class"].keys()) | set(candidate_train["per_class"].keys())
    )
    per_class: dict[str, dict[str, float]] = {}
    for label in per_class_labels:
        baseline_metrics = baseline_train["per_class"].get(label, {})
        candidate_metrics = candidate_train["per_class"].get(label, {})
        per_class[label] = {
            "baseline_f1": float(baseline_metrics.get("f1", 0.0)),
            "candidate_f1": float(candidate_metrics.get("f1", 0.0)),
            "delta_f1": _delta(
                float(candidate_metrics.get("f1", 0.0)),
                float(baseline_metrics.get("f1", 0.0)),
            ),
            "baseline_recall": float(baseline_metrics.get("recall", 0.0)),
            "candidate_recall": float(candidate_metrics.get("recall", 0.0)),
            "delta_recall": _delta(
                float(candidate_metrics.get("recall", 0.0)),
                float(baseline_metrics.get("recall", 0.0)),
            ),
        }

    payload: dict[str, Any] = {
        "training": {
            "baseline_best_epoch": baseline_train["best_epoch"],
            "candidate_best_epoch": candidate_train["best_epoch"],
            "macro_f1": {
                "baseline": baseline_train["macro_f1"],
                "candidate": candidate_train["macro_f1"],
                "delta": _delta(candidate_train["macro_f1"], baseline_train["macro_f1"]),
            },
            "accuracy": {
                "baseline": baseline_train["accuracy"],
                "candidate": candidate_train["accuracy"],
                "delta": _delta(candidate_train["accuracy"], baseline_train["accuracy"]),
            },
            "weighted_f1": {
                "baseline": baseline_train["weighted_f1"],
                "candidate": candidate_train["weighted_f1"],
                "delta": _delta(candidate_train["weighted_f1"], baseline_train["weighted_f1"]),
            },
            "risk_accuracy": {
                "baseline": baseline_train["risk_accuracy"],
                "candidate": candidate_train["risk_accuracy"],
                "delta": _delta(candidate_train["risk_accuracy"], baseline_train["risk_accuracy"]),
            },
            "per_class": per_class,
            "train_class_counts": {
                "baseline": baseline_train["train_class_counts"],
                "candidate": candidate_train["train_class_counts"],
            },
        }
    }

    if baseline_event_summary is not None and candidate_event_summary is not None:
        payload["event"] = {
            "precision": {
                "baseline": float(baseline_event_summary.get("precision", 0.0)),
                "candidate": float(candidate_event_summary.get("precision", 0.0)),
                "delta": _delta(
                    float(candidate_event_summary.get("precision", 0.0)),
                    float(baseline_event_summary.get("precision", 0.0)),
                ),
            },
            "recall": {
                "baseline": float(baseline_event_summary.get("recall", 0.0)),
                "candidate": float(candidate_event_summary.get("recall", 0.0)),
                "delta": _delta(
                    float(candidate_event_summary.get("recall", 0.0)),
                    float(baseline_event_summary.get("recall", 0.0)),
                ),
            },
            "f1": {
                "baseline": float(baseline_event_summary.get("f1", 0.0)),
                "candidate": float(candidate_event_summary.get("f1", 0.0)),
                "delta": _delta(
                    float(candidate_event_summary.get("f1", 0.0)),
                    float(baseline_event_summary.get("f1", 0.0)),
                ),
            },
            "false_positives_per_hour": {
                "baseline": float(baseline_event_summary.get("false_positives_per_hour", 0.0)),
                "candidate": float(candidate_event_summary.get("false_positives_per_hour", 0.0)),
                "delta": _delta(
                    float(candidate_event_summary.get("false_positives_per_hour", 0.0)),
                    float(baseline_event_summary.get("false_positives_per_hour", 0.0)),
                ),
            },
            "mean_abs_delay_seconds": {
                "baseline": float(baseline_event_summary.get("mean_abs_delay_seconds", 0.0)),
                "candidate": float(candidate_event_summary.get("mean_abs_delay_seconds", 0.0)),
                "delta": _delta(
                    float(candidate_event_summary.get("mean_abs_delay_seconds", 0.0)),
                    float(baseline_event_summary.get("mean_abs_delay_seconds", 0.0)),
                ),
            },
        }
    if baseline_sample_summary is not None and candidate_sample_summary is not None:
        baseline_sample = _extract_sample_metrics(baseline_sample_summary)
        candidate_sample = _extract_sample_metrics(candidate_sample_summary)
        sample_labels = sorted(
            set(baseline_sample["per_class"].keys()) | set(candidate_sample["per_class"].keys())
        )
        per_class_sample: dict[str, dict[str, float]] = {}
        for label in sample_labels:
            baseline_metrics = baseline_sample["per_class"].get(label, {})
            candidate_metrics = candidate_sample["per_class"].get(label, {})
            per_class_sample[label] = {
                "baseline_f1": float(baseline_metrics.get("f1", 0.0)),
                "candidate_f1": float(candidate_metrics.get("f1", 0.0)),
                "delta_f1": _delta(
                    float(candidate_metrics.get("f1", 0.0)),
                    float(baseline_metrics.get("f1", 0.0)),
                ),
                "baseline_recall": float(baseline_metrics.get("recall", 0.0)),
                "candidate_recall": float(candidate_metrics.get("recall", 0.0)),
                "delta_recall": _delta(
                    float(candidate_metrics.get("recall", 0.0)),
                    float(baseline_metrics.get("recall", 0.0)),
                ),
            }
        payload["sample_classification"] = {
            "num_samples": {
                "baseline": baseline_sample["num_samples"],
                "candidate": candidate_sample["num_samples"],
                "delta": candidate_sample["num_samples"] - baseline_sample["num_samples"],
            },
            "num_windows": {
                "baseline": baseline_sample["num_windows"],
                "candidate": candidate_sample["num_windows"],
                "delta": candidate_sample["num_windows"] - baseline_sample["num_windows"],
            },
            "accuracy": {
                "baseline": baseline_sample["accuracy"],
                "candidate": candidate_sample["accuracy"],
                "delta": _delta(candidate_sample["accuracy"], baseline_sample["accuracy"]),
            },
            "macro_f1": {
                "baseline": baseline_sample["macro_f1"],
                "candidate": candidate_sample["macro_f1"],
                "delta": _delta(candidate_sample["macro_f1"], baseline_sample["macro_f1"]),
            },
            "weighted_f1": {
                "baseline": baseline_sample["weighted_f1"],
                "candidate": candidate_sample["weighted_f1"],
                "delta": _delta(candidate_sample["weighted_f1"], baseline_sample["weighted_f1"]),
            },
            "per_class": per_class_sample,
        }
    if expected_state_summary is not None:
        payload["expected_state"] = {
            "expected_state": expected_state_summary.get("expected_state"),
            "baseline": expected_state_summary.get("baseline", {}),
            "candidate": expected_state_summary.get("candidate", {}),
            "delta": expected_state_summary.get("delta", {}),
        }
    return payload


def build_markdown(payload: dict[str, Any]) -> str:
    training = payload["training"]
    lines = [
        "# 实验结果对比",
        "",
        "## 训练指标",
        (
            f"- macro_f1: 上一轮={_format_metric(training['macro_f1']['baseline'])} "
            f"当前轮={_format_metric(training['macro_f1']['candidate'])} "
            f"delta={_format_delta(training['macro_f1']['delta'])}"
        ),
        (
            f"- accuracy: 上一轮={_format_metric(training['accuracy']['baseline'])} "
            f"当前轮={_format_metric(training['accuracy']['candidate'])} "
            f"delta={_format_delta(training['accuracy']['delta'])}"
        ),
        (
            f"- weighted_f1: 上一轮={_format_metric(training['weighted_f1']['baseline'])} "
            f"当前轮={_format_metric(training['weighted_f1']['candidate'])} "
            f"delta={_format_delta(training['weighted_f1']['delta'])}"
        ),
        (
            f"- risk_accuracy: 上一轮={_format_metric(training['risk_accuracy']['baseline'])} "
            f"当前轮={_format_metric(training['risk_accuracy']['candidate'])} "
            f"delta={_format_delta(training['risk_accuracy']['delta'])}"
        ),
        "",
        "## 各类别对比",
    ]
    for label, metrics in training["per_class"].items():
        lines.append(
            (
                f"- {label}: "
                f"f1 { _format_metric(metrics['baseline_f1']) } -> { _format_metric(metrics['candidate_f1']) } "
                f"({ _format_delta(metrics['delta_f1']) }), "
                f"recall { _format_metric(metrics['baseline_recall']) } -> { _format_metric(metrics['candidate_recall']) } "
                f"({ _format_delta(metrics['delta_recall']) })"
            )
        )

    if "event" in payload:
        event = payload["event"]
        lines.extend(
            [
                "",
                "## 事件级指标",
                (
                    f"- precision: 上一轮={_format_metric(event['precision']['baseline'])} "
                    f"当前轮={_format_metric(event['precision']['candidate'])} "
                    f"delta={_format_delta(event['precision']['delta'])}"
                ),
                (
                    f"- recall: 上一轮={_format_metric(event['recall']['baseline'])} "
                    f"当前轮={_format_metric(event['recall']['candidate'])} "
                    f"delta={_format_delta(event['recall']['delta'])}"
                ),
                (
                    f"- f1: 上一轮={_format_metric(event['f1']['baseline'])} "
                    f"当前轮={_format_metric(event['f1']['candidate'])} "
                    f"delta={_format_delta(event['f1']['delta'])}"
                ),
                (
                    f"- 每小时误报数: 上一轮={_format_metric(event['false_positives_per_hour']['baseline'])} "
                    f"当前轮={_format_metric(event['false_positives_per_hour']['candidate'])} "
                    f"delta={_format_delta(event['false_positives_per_hour']['delta'])}"
                ),
                (
                    f"- 平均绝对延迟(秒): 上一轮={_format_metric(event['mean_abs_delay_seconds']['baseline'])} "
                    f"当前轮={_format_metric(event['mean_abs_delay_seconds']['candidate'])} "
                    f"delta={_format_delta(event['mean_abs_delay_seconds']['delta'])}"
                ),
            ]
        )
    if "sample_classification" in payload:
        sample = payload["sample_classification"]
        lines.extend(
            [
                "",
                "## 样本级分类指标",
                (
                    f"- num_samples: 上一轮={sample['num_samples']['baseline']} "
                    f"当前轮={sample['num_samples']['candidate']} "
                    f"delta={sample['num_samples']['delta']:+d}"
                ),
                (
                    f"- num_windows: 上一轮={sample['num_windows']['baseline']} "
                    f"当前轮={sample['num_windows']['candidate']} "
                    f"delta={sample['num_windows']['delta']:+d}"
                ),
                (
                    f"- accuracy: 上一轮={_format_metric(sample['accuracy']['baseline'])} "
                    f"当前轮={_format_metric(sample['accuracy']['candidate'])} "
                    f"delta={_format_delta(sample['accuracy']['delta'])}"
                ),
                (
                    f"- macro_f1: 上一轮={_format_metric(sample['macro_f1']['baseline'])} "
                    f"当前轮={_format_metric(sample['macro_f1']['candidate'])} "
                    f"delta={_format_delta(sample['macro_f1']['delta'])}"
                ),
                (
                    f"- weighted_f1: 上一轮={_format_metric(sample['weighted_f1']['baseline'])} "
                    f"当前轮={_format_metric(sample['weighted_f1']['candidate'])} "
                    f"delta={_format_delta(sample['weighted_f1']['delta'])}"
                ),
                "",
                "### 样本级各类别对比",
            ]
        )
        for label, metrics in sample["per_class"].items():
            lines.append(
                (
                    f"- {label}: "
                    f"f1 { _format_metric(metrics['baseline_f1']) } -> { _format_metric(metrics['candidate_f1']) } "
                    f"({ _format_delta(metrics['delta_f1']) }), "
                    f"recall { _format_metric(metrics['baseline_recall']) } -> { _format_metric(metrics['candidate_recall']) } "
                    f"({ _format_delta(metrics['delta_recall']) })"
                )
            )
    if "expected_state" in payload:
        expected_state = payload["expected_state"]
        baseline = expected_state.get("baseline", {})
        candidate = expected_state.get("candidate", {})
        delta = expected_state.get("delta", {})
        lines.extend(
            [
                "",
                "## 应用级期望状态对比",
                f"- expected_state: {expected_state.get('expected_state')}",
                (
                    f"- with_incidents_rate: 上一轮={_format_metric(float(baseline.get('with_incidents_rate', 0.0)))} "
                    f"当前轮={_format_metric(float(candidate.get('with_incidents_rate', 0.0)))} "
                    f"delta={_format_delta(float(delta.get('with_incidents_rate', 0.0)))}"
                ),
                (
                    f"- dominant_drift_rate: 上一轮={_format_metric(float(baseline.get('dominant_drift_rate', 0.0)))} "
                    f"当前轮={_format_metric(float(candidate.get('dominant_drift_rate', 0.0)))} "
                    f"delta={_format_delta(float(delta.get('dominant_drift_rate', 0.0)))}"
                ),
                (
                    f"- incident_sum: 上一轮={int(baseline.get('incident_sum', 0))} "
                    f"当前轮={int(candidate.get('incident_sum', 0))} "
                    f"delta={int(delta.get('incident_sum', 0)):+d}"
                ),
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-train-summary", type=Path, required=True)
    parser.add_argument("--candidate-train-summary", type=Path, required=True)
    parser.add_argument("--baseline-event-summary", type=Path)
    parser.add_argument("--candidate-event-summary", type=Path)
    parser.add_argument("--baseline-sample-summary", type=Path)
    parser.add_argument("--candidate-sample-summary", type=Path)
    parser.add_argument("--expected-state-summary", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    payload = build_comparison_payload(
        baseline_train_summary=_load_json(args.baseline_train_summary.resolve()),
        candidate_train_summary=_load_json(args.candidate_train_summary.resolve()),
        baseline_event_summary=_load_optional_json(args.baseline_event_summary),
        candidate_event_summary=_load_optional_json(args.candidate_event_summary),
        baseline_sample_summary=_load_json(args.baseline_sample_summary.resolve())
        if args.baseline_sample_summary is not None
        else None,
        candidate_sample_summary=_load_json(args.candidate_sample_summary.resolve())
        if args.candidate_sample_summary is not None
        else None,
        expected_state_summary=_load_json(args.expected_state_summary.resolve())
        if args.expected_state_summary is not None
        else None,
    )
    markdown = build_markdown(payload)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {args.output_json}", flush=True)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
