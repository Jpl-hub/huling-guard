from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assess_promotion(
    comparison: dict[str, Any],
    *,
    min_macro_f1_delta: float = 0.0,
    min_sample_macro_f1_delta: float = 0.0,
    min_fall_f1_delta: float = 0.0,
    min_near_fall_f1_delta: float = 0.02,
    min_recovery_f1_delta: float = 0.02,
    min_prolonged_lying_f1_delta: float = 0.0,
    max_fp_per_hour_delta: float = 0.2,
    max_delay_delta: float = 0.2,
    max_expected_state_with_incidents_rate_delta: float = 0.0,
    max_expected_state_dominant_drift_rate_delta: float = 0.0,
    max_expected_state_incident_sum_delta: float = 0.0,
) -> dict[str, Any]:
    training = comparison["training"]
    event = comparison.get("event")
    sample_classification = comparison.get("sample_classification")
    expected_state = comparison.get("expected_state")
    per_class = training["per_class"]

    checks: list[dict[str, Any]] = []

    def _add_check(name: str, passed: bool, value: float | None, threshold: float | None, note: str) -> None:
        checks.append(
            {
                "name": name,
                "passed": passed,
                "value": value,
                "threshold": threshold,
                "note": note,
            }
        )

    macro_delta = float(training["macro_f1"]["delta"])
    _add_check(
        "macro_f1_non_decrease",
        macro_delta >= min_macro_f1_delta,
        macro_delta,
        min_macro_f1_delta,
        "整体 macro_f1 不应下降",
    )
    if sample_classification is not None:
        sample_macro_delta = float(sample_classification["macro_f1"]["delta"])
        _add_check(
            "sample_macro_f1_non_decrease",
            sample_macro_delta >= min_sample_macro_f1_delta,
            sample_macro_delta,
            min_sample_macro_f1_delta,
            "样本级 macro_f1 不应下降",
        )

    for label, threshold in (
        ("fall", min_fall_f1_delta),
        ("near_fall", min_near_fall_f1_delta),
        ("recovery", min_recovery_f1_delta),
        ("prolonged_lying", min_prolonged_lying_f1_delta),
    ):
        label_metrics = per_class.get(label)
        if label_metrics is None:
            _add_check(
                f"{label}_f1_delta",
                False,
                None,
                threshold,
                f"缺少 {label} 指标，无法确认补强收益",
            )
            continue
        delta_value = float(label_metrics["delta_f1"])
        _add_check(
            f"{label}_f1_delta",
            delta_value >= threshold,
            delta_value,
            threshold,
            f"{label} 的 F1 提升应达到阈值",
        )

    if event is not None:
        fp_delta = float(event["false_positives_per_hour"]["delta"])
        _add_check(
            "false_positives_per_hour_controlled",
            fp_delta <= max_fp_per_hour_delta,
            fp_delta,
            max_fp_per_hour_delta,
            "每小时误报数不应明显恶化",
        )
        delay_delta = float(event["mean_abs_delay_seconds"]["delta"])
        _add_check(
            "delay_controlled",
            delay_delta <= max_delay_delta,
            delay_delta,
            max_delay_delta,
            "平均绝对延迟不应明显恶化",
        )
    if expected_state is not None:
        expected_delta = expected_state.get("delta", {})
        with_incidents_rate_delta = float(expected_delta.get("with_incidents_rate", 0.0))
        _add_check(
            "expected_state_with_incidents_rate_controlled",
            with_incidents_rate_delta <= max_expected_state_with_incidents_rate_delta,
            with_incidents_rate_delta,
            max_expected_state_with_incidents_rate_delta,
            "真实应用正常视频的事件触发率不应恶化",
        )
        dominant_drift_rate_delta = float(expected_delta.get("dominant_drift_rate", 0.0))
        _add_check(
            "expected_state_dominant_drift_rate_controlled",
            dominant_drift_rate_delta <= max_expected_state_dominant_drift_rate_delta,
            dominant_drift_rate_delta,
            max_expected_state_dominant_drift_rate_delta,
            "真实应用正常视频的主导状态漂移率不应恶化",
        )
        incident_sum_delta = float(expected_delta.get("incident_sum", 0.0))
        _add_check(
            "expected_state_incident_sum_controlled",
            incident_sum_delta <= max_expected_state_incident_sum_delta,
            incident_sum_delta,
            max_expected_state_incident_sum_delta,
            "真实应用正常视频的累计误报事件数不应增加",
        )

    passed = sum(1 for check in checks if check["passed"])
    failed = [check for check in checks if not check["passed"]]
    hard_fail_checks = {
        "macro_f1_non_decrease",
        "sample_macro_f1_non_decrease",
        "fall_f1_delta",
        "prolonged_lying_f1_delta",
        "false_positives_per_hour_controlled",
        "delay_controlled",
        "expected_state_with_incidents_rate_controlled",
        "expected_state_dominant_drift_rate_controlled",
        "expected_state_incident_sum_controlled",
    }
    failed_names = {str(check["name"]) for check in failed}
    if not failed:
        verdict = "promote"
    elif failed_names & hard_fail_checks:
        verdict = "hold"
    elif passed >= max(1, len(checks) - 1):
        verdict = "review"
    else:
        verdict = "hold"

    return {
        "verdict": verdict,
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "summary": {
            "macro_f1_delta": macro_delta,
            "sample_macro_f1_delta": float(sample_classification["macro_f1"]["delta"])
            if sample_classification is not None
            else None,
            "fall_f1_delta": float(per_class.get("fall", {}).get("delta_f1", 0.0)),
            "near_fall_f1_delta": float(per_class.get("near_fall", {}).get("delta_f1", 0.0)),
            "recovery_f1_delta": float(per_class.get("recovery", {}).get("delta_f1", 0.0)),
            "prolonged_lying_f1_delta": float(per_class.get("prolonged_lying", {}).get("delta_f1", 0.0)),
            "false_positives_per_hour_delta": float(event["false_positives_per_hour"]["delta"]) if event else None,
            "mean_abs_delay_delta": float(event["mean_abs_delay_seconds"]["delta"]) if event else None,
            "expected_state_with_incidents_rate_delta": float(expected_state.get("delta", {}).get("with_incidents_rate", 0.0))
            if expected_state is not None
            else None,
            "expected_state_dominant_drift_rate_delta": float(expected_state.get("delta", {}).get("dominant_drift_rate", 0.0))
            if expected_state is not None
            else None,
            "expected_state_incident_sum_delta": float(expected_state.get("delta", {}).get("incident_sum", 0.0))
            if expected_state is not None
            else None,
        },
    }


def build_markdown(summary: dict[str, Any]) -> str:
    verdict_map = {
        "promote": "建议保留当前轮",
        "review": "建议人工复查后决定",
        "hold": "不建议替换上一轮",
    }
    lines = [
        "# 结果保留判读",
        "",
        f"- verdict: {summary['verdict']} ({verdict_map.get(summary['verdict'], 'unknown')})",
        f"- passed_checks: {summary['passed_checks']}/{summary['total_checks']}",
        "",
        "## 检查项",
    ]
    for check in summary["checks"]:
        status = "pass" if check["passed"] else "fail"
        value = "n/a" if check["value"] is None else f"{check['value']:.4f}"
        threshold = "n/a" if check["threshold"] is None else f"{check['threshold']:.4f}"
        lines.append(
            f"- {check['name']}: {status}, value={value}, threshold={threshold}, note={check['note']}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--min-macro-f1-delta", type=float, default=0.0)
    parser.add_argument("--min-sample-macro-f1-delta", type=float, default=0.0)
    parser.add_argument("--min-fall-f1-delta", type=float, default=0.0)
    parser.add_argument("--min-near-fall-f1-delta", type=float, default=0.02)
    parser.add_argument("--min-recovery-f1-delta", type=float, default=0.02)
    parser.add_argument("--min-prolonged-lying-f1-delta", type=float, default=0.0)
    parser.add_argument("--max-fp-per-hour-delta", type=float, default=0.2)
    parser.add_argument("--max-delay-delta", type=float, default=0.2)
    parser.add_argument("--max-expected-state-with-incidents-rate-delta", type=float, default=0.0)
    parser.add_argument("--max-expected-state-dominant-drift-rate-delta", type=float, default=0.0)
    parser.add_argument("--max-expected-state-incident-sum-delta", type=float, default=0.0)
    args = parser.parse_args()

    summary = assess_promotion(
        _load_json(args.comparison.resolve()),
        min_macro_f1_delta=args.min_macro_f1_delta,
        min_sample_macro_f1_delta=args.min_sample_macro_f1_delta,
        min_fall_f1_delta=args.min_fall_f1_delta,
        min_near_fall_f1_delta=args.min_near_fall_f1_delta,
        min_recovery_f1_delta=args.min_recovery_f1_delta,
        min_prolonged_lying_f1_delta=args.min_prolonged_lying_f1_delta,
        max_fp_per_hour_delta=args.max_fp_per_hour_delta,
        max_delay_delta=args.max_delay_delta,
        max_expected_state_with_incidents_rate_delta=args.max_expected_state_with_incidents_rate_delta,
        max_expected_state_dominant_drift_rate_delta=args.max_expected_state_dominant_drift_rate_delta,
        max_expected_state_incident_sum_delta=args.max_expected_state_incident_sum_delta,
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
