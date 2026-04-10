from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _delta(candidate: float, baseline: float) -> float:
    return candidate - baseline


def _metric_block(baseline: float, candidate: float) -> dict[str, float]:
    return {
        "baseline": baseline,
        "candidate": candidate,
        "delta": _delta(candidate, baseline),
    }


def _extract_class_metrics(section: dict[str, Any], label: str) -> dict[str, float]:
    metrics = section.get("per_class", {}).get(label, {})
    return {
        "f1": float(metrics.get("f1", 0.0)),
        "recall": float(metrics.get("recall", 0.0)),
        "support": int(metrics.get("support", 0)),
    }


def build_comparison_payload(
    *,
    baseline_summary: dict[str, Any],
    candidate_summary: dict[str, Any],
) -> dict[str, Any]:
    baseline_window = baseline_summary.get("window", {})
    candidate_window = candidate_summary.get("window", {})
    baseline_sample = baseline_summary.get("sample", {})
    candidate_sample = candidate_summary.get("sample", {})

    labels = sorted(
        set(baseline_window.get("per_class", {}).keys())
        | set(candidate_window.get("per_class", {}).keys())
        | set(baseline_sample.get("per_class", {}).keys())
        | set(candidate_sample.get("per_class", {}).keys())
    )

    per_class_window: dict[str, dict[str, float | int]] = {}
    per_class_sample: dict[str, dict[str, float | int]] = {}
    for label in labels:
        base_window_metrics = _extract_class_metrics(baseline_window, label)
        cand_window_metrics = _extract_class_metrics(candidate_window, label)
        base_sample_metrics = _extract_class_metrics(baseline_sample, label)
        cand_sample_metrics = _extract_class_metrics(candidate_sample, label)
        per_class_window[label] = {
            "baseline_f1": base_window_metrics["f1"],
            "candidate_f1": cand_window_metrics["f1"],
            "delta_f1": _delta(cand_window_metrics["f1"], base_window_metrics["f1"]),
            "baseline_recall": base_window_metrics["recall"],
            "candidate_recall": cand_window_metrics["recall"],
            "delta_recall": _delta(cand_window_metrics["recall"], base_window_metrics["recall"]),
            "baseline_support": base_window_metrics["support"],
            "candidate_support": cand_window_metrics["support"],
        }
        per_class_sample[label] = {
            "baseline_f1": base_sample_metrics["f1"],
            "candidate_f1": cand_sample_metrics["f1"],
            "delta_f1": _delta(cand_sample_metrics["f1"], base_sample_metrics["f1"]),
            "baseline_recall": base_sample_metrics["recall"],
            "candidate_recall": cand_sample_metrics["recall"],
            "delta_recall": _delta(cand_sample_metrics["recall"], base_sample_metrics["recall"]),
            "baseline_support": base_sample_metrics["support"],
            "candidate_support": cand_sample_metrics["support"],
        }

    return {
        "baseline": {
            "checkpoint_path": baseline_summary.get("checkpoint_path"),
            "eval_manifest_path": baseline_summary.get("eval_manifest_path"),
        },
        "candidate": {
            "checkpoint_path": candidate_summary.get("checkpoint_path"),
            "eval_manifest_path": candidate_summary.get("eval_manifest_path"),
        },
        "window": {
            "accuracy": _metric_block(
                float(baseline_window.get("accuracy", 0.0)),
                float(candidate_window.get("accuracy", 0.0)),
            ),
            "macro_f1": _metric_block(
                float(baseline_window.get("macro_f1", 0.0)),
                float(candidate_window.get("macro_f1", 0.0)),
            ),
            "weighted_f1": _metric_block(
                float(baseline_window.get("weighted_f1", 0.0)),
                float(candidate_window.get("weighted_f1", 0.0)),
            ),
            "support": {
                "baseline": int(baseline_window.get("support", 0)),
                "candidate": int(candidate_window.get("support", 0)),
                "delta": int(candidate_window.get("support", 0)) - int(baseline_window.get("support", 0)),
            },
            "per_class": per_class_window,
        },
        "sample": {
            "accuracy": _metric_block(
                float(baseline_sample.get("accuracy", 0.0)),
                float(candidate_sample.get("accuracy", 0.0)),
            ),
            "macro_f1": _metric_block(
                float(baseline_sample.get("macro_f1", 0.0)),
                float(candidate_sample.get("macro_f1", 0.0)),
            ),
            "weighted_f1": _metric_block(
                float(baseline_sample.get("weighted_f1", 0.0)),
                float(candidate_sample.get("weighted_f1", 0.0)),
            ),
            "num_samples": {
                "baseline": int(baseline_sample.get("num_samples", 0)),
                "candidate": int(candidate_sample.get("num_samples", 0)),
                "delta": int(candidate_sample.get("num_samples", 0)) - int(baseline_sample.get("num_samples", 0)),
            },
            "num_windows": {
                "baseline": int(baseline_sample.get("num_windows", 0)),
                "candidate": int(candidate_sample.get("num_windows", 0)),
                "delta": int(candidate_sample.get("num_windows", 0)) - int(baseline_sample.get("num_windows", 0)),
            },
            "per_class": per_class_sample,
        },
    }


def _format_metric(value: float) -> str:
    return f"{value:.4f}"


def _format_delta(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.4f}"


def build_markdown(payload: dict[str, Any]) -> str:
    window = payload["window"]
    sample = payload["sample"]
    lines = [
        "# Checkpoint 同口径重评对比",
        "",
        f"- baseline_checkpoint: {payload['baseline']['checkpoint_path']}",
        f"- candidate_checkpoint: {payload['candidate']['checkpoint_path']}",
        f"- baseline_eval_manifest: {payload['baseline']['eval_manifest_path']}",
        f"- candidate_eval_manifest: {payload['candidate']['eval_manifest_path']}",
        "",
        "## 窗口级指标",
        (
            f"- accuracy: baseline={_format_metric(window['accuracy']['baseline'])} "
            f"candidate={_format_metric(window['accuracy']['candidate'])} "
            f"delta={_format_delta(window['accuracy']['delta'])}"
        ),
        (
            f"- macro_f1: baseline={_format_metric(window['macro_f1']['baseline'])} "
            f"candidate={_format_metric(window['macro_f1']['candidate'])} "
            f"delta={_format_delta(window['macro_f1']['delta'])}"
        ),
        (
            f"- weighted_f1: baseline={_format_metric(window['weighted_f1']['baseline'])} "
            f"candidate={_format_metric(window['weighted_f1']['candidate'])} "
            f"delta={_format_delta(window['weighted_f1']['delta'])}"
        ),
        (
            f"- support: baseline={window['support']['baseline']} "
            f"candidate={window['support']['candidate']} "
            f"delta={window['support']['delta']:+d}"
        ),
        "",
        "## 样本级指标",
        (
            f"- accuracy: baseline={_format_metric(sample['accuracy']['baseline'])} "
            f"candidate={_format_metric(sample['accuracy']['candidate'])} "
            f"delta={_format_delta(sample['accuracy']['delta'])}"
        ),
        (
            f"- macro_f1: baseline={_format_metric(sample['macro_f1']['baseline'])} "
            f"candidate={_format_metric(sample['macro_f1']['candidate'])} "
            f"delta={_format_delta(sample['macro_f1']['delta'])}"
        ),
        (
            f"- weighted_f1: baseline={_format_metric(sample['weighted_f1']['baseline'])} "
            f"candidate={_format_metric(sample['weighted_f1']['candidate'])} "
            f"delta={_format_delta(sample['weighted_f1']['delta'])}"
        ),
        (
            f"- num_samples: baseline={sample['num_samples']['baseline']} "
            f"candidate={sample['num_samples']['candidate']} "
            f"delta={sample['num_samples']['delta']:+d}"
        ),
        (
            f"- num_windows: baseline={sample['num_windows']['baseline']} "
            f"candidate={sample['num_windows']['candidate']} "
            f"delta={sample['num_windows']['delta']:+d}"
        ),
        "",
        "## 样本级各类别对比",
    ]
    for label, metrics in sample["per_class"].items():
        lines.append(
            (
                f"- {label}: "
                f"f1 { _format_metric(metrics['baseline_f1']) } -> { _format_metric(metrics['candidate_f1']) } "
                f"({ _format_delta(metrics['delta_f1']) }), "
                f"recall { _format_metric(metrics['baseline_recall']) } -> { _format_metric(metrics['candidate_recall']) } "
                f"({ _format_delta(metrics['delta_recall']) }), "
                f"support {metrics['baseline_support']} -> {metrics['candidate_support']}"
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    payload = build_comparison_payload(
        baseline_summary=_load_json(args.baseline.resolve()),
        candidate_summary=_load_json(args.candidate.resolve()),
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
