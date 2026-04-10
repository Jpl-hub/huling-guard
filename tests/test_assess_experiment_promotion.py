from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from assess_experiment_promotion import assess_promotion, build_markdown


def test_assess_promotion_returns_promote_when_checks_pass() -> None:
    comparison = {
        "training": {
            "macro_f1": {"delta": 0.03},
            "per_class": {
                "fall": {"delta_f1": 0.01},
                "near_fall": {"delta_f1": 0.08},
                "recovery": {"delta_f1": 0.05},
                "prolonged_lying": {"delta_f1": 0.02},
            },
        },
        "sample_classification": {
            "macro_f1": {"delta": 0.02},
        },
        "event": {
            "false_positives_per_hour": {"delta": -0.3},
            "mean_abs_delay_seconds": {"delta": -0.1},
        },
    }

    summary = assess_promotion(comparison)
    markdown = build_markdown(summary)

    assert summary["verdict"] == "promote"
    assert summary["passed_checks"] == summary["total_checks"]
    assert "建议保留当前轮" in markdown


def test_assess_promotion_returns_review_when_only_one_check_fails() -> None:
    comparison = {
        "training": {
            "macro_f1": {"delta": 0.01},
            "per_class": {
                "fall": {"delta_f1": 0.00},
                "near_fall": {"delta_f1": 0.06},
                "recovery": {"delta_f1": 0.01},
                "prolonged_lying": {"delta_f1": 0.01},
            },
        },
        "event": {
            "false_positives_per_hour": {"delta": -0.1},
            "mean_abs_delay_seconds": {"delta": 0.05},
        },
    }

    summary = assess_promotion(comparison)

    assert summary["verdict"] == "review"
    failed_checks = [check for check in summary["checks"] if not check["passed"]]
    assert len(failed_checks) == 1
    assert failed_checks[0]["name"] == "recovery_f1_delta"


def test_assess_promotion_returns_hold_when_key_metrics_regress() -> None:
    comparison = {
        "training": {
            "macro_f1": {"delta": -0.02},
            "per_class": {
                "fall": {"delta_f1": -0.04},
                "near_fall": {"delta_f1": -0.03},
                "recovery": {"delta_f1": -0.01},
                "prolonged_lying": {"delta_f1": -0.02},
            },
        },
        "event": {
            "false_positives_per_hour": {"delta": 0.8},
            "mean_abs_delay_seconds": {"delta": 0.4},
        },
    }

    summary = assess_promotion(comparison)
    markdown = build_markdown(summary)

    assert summary["verdict"] == "hold"
    assert "不建议替换上一轮" in markdown


def test_assess_promotion_holds_when_fall_regresses_even_if_macro_improves() -> None:
    comparison = {
        "training": {
            "macro_f1": {"delta": 0.05},
            "per_class": {
                "fall": {"delta_f1": -0.10},
                "near_fall": {"delta_f1": 0.03},
                "recovery": {"delta_f1": 0.04},
                "prolonged_lying": {"delta_f1": 0.01},
            },
        },
    }

    summary = assess_promotion(comparison)

    assert summary["verdict"] == "hold"
    failed_checks = [check["name"] for check in summary["checks"] if not check["passed"]]
    assert "fall_f1_delta" in failed_checks


def test_assess_promotion_holds_when_sample_macro_regresses() -> None:
    comparison = {
        "training": {
            "macro_f1": {"delta": 0.01},
            "per_class": {
                "fall": {"delta_f1": 0.01},
                "near_fall": {"delta_f1": 0.03},
                "recovery": {"delta_f1": 0.03},
                "prolonged_lying": {"delta_f1": 0.01},
            },
        },
        "sample_classification": {
            "macro_f1": {"delta": -0.08},
        },
    }

    summary = assess_promotion(comparison)

    assert summary["verdict"] == "hold"
    failed_checks = [check["name"] for check in summary["checks"] if not check["passed"]]
    assert "sample_macro_f1_non_decrease" in failed_checks


def test_assess_promotion_holds_when_expected_state_metrics_worsen() -> None:
    comparison = {
        "training": {
            "macro_f1": {"delta": 0.02},
            "per_class": {
                "fall": {"delta_f1": 0.01},
                "near_fall": {"delta_f1": 0.03},
                "recovery": {"delta_f1": 0.03},
                "prolonged_lying": {"delta_f1": 0.02},
            },
        },
        "sample_classification": {
            "macro_f1": {"delta": 0.01},
        },
        "expected_state": {
            "expected_state": "normal",
            "delta": {
                "with_incidents_rate": 0.0,
                "dominant_drift_rate": 0.30,
                "incident_sum": 29,
            },
        },
    }

    summary = assess_promotion(comparison)

    assert summary["verdict"] == "hold"
    failed_checks = [check["name"] for check in summary["checks"] if not check["passed"]]
    assert "expected_state_dominant_drift_rate_controlled" in failed_checks
    assert "expected_state_incident_sum_controlled" in failed_checks
