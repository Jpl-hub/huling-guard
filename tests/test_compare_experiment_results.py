import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_experiment_results import _load_optional_json, build_comparison_payload, build_markdown


def test_load_optional_json_skips_missing_summary(tmp_path: Path) -> None:
    assert _load_optional_json(tmp_path / "missing.json") is None


def test_compare_experiment_results_builds_training_and_event_deltas() -> None:
    baseline_train = {
        "best_epoch": 8,
        "best_metrics": {
            "macro_f1": 0.41,
            "accuracy": 0.83,
            "weighted_f1": 0.79,
            "risk_accuracy": 0.87,
            "per_class": {
                "near_fall": {"f1": 0.10, "recall": 0.08},
                "recovery": {"f1": 0.12, "recall": 0.10},
            },
        },
        "train_class_counts": {"near_fall": 0, "recovery": 13},
    }
    candidate_train = {
        "best_epoch": 11,
        "best_metrics": {
            "macro_f1": 0.46,
            "accuracy": 0.85,
            "weighted_f1": 0.82,
            "risk_accuracy": 0.89,
            "per_class": {
                "near_fall": {"f1": 0.24, "recall": 0.20},
                "recovery": {"f1": 0.31, "recall": 0.28},
            },
        },
        "train_class_counts": {"near_fall": 120, "recovery": 40},
    }
    baseline_event = {
        "precision": 0.72,
        "recall": 0.70,
        "f1": 0.71,
        "false_positives_per_hour": 1.8,
        "mean_abs_delay_seconds": 0.92,
    }
    candidate_event = {
        "precision": 0.79,
        "recall": 0.78,
        "f1": 0.785,
        "false_positives_per_hour": 1.2,
        "mean_abs_delay_seconds": 0.66,
    }
    baseline_sample = {
        "num_samples": 120,
        "num_windows": 960,
        "accuracy": 0.75,
        "macro_f1": 0.38,
        "weighted_f1": 0.74,
        "per_class": {
            "near_fall": {"f1": 0.05, "recall": 0.04},
            "recovery": {"f1": 0.08, "recall": 0.06},
        },
    }
    candidate_sample = {
        "num_samples": 120,
        "num_windows": 1440,
        "accuracy": 0.80,
        "macro_f1": 0.44,
        "weighted_f1": 0.79,
        "per_class": {
            "near_fall": {"f1": 0.12, "recall": 0.10},
            "recovery": {"f1": 0.18, "recall": 0.15},
        },
    }
    expected_state = {
        "expected_state": "normal",
        "baseline": {
            "with_incidents_rate": 0.475,
            "dominant_drift_rate": 0.075,
            "incident_sum": 19,
        },
        "candidate": {
            "with_incidents_rate": 0.475,
            "dominant_drift_rate": 0.375,
            "incident_sum": 48,
        },
        "delta": {
            "with_incidents_rate": 0.0,
            "dominant_drift_rate": 0.3,
            "incident_sum": 29,
        },
    }

    payload = build_comparison_payload(
        baseline_train_summary=baseline_train,
        candidate_train_summary=candidate_train,
        baseline_event_summary=baseline_event,
        candidate_event_summary=candidate_event,
        baseline_sample_summary=baseline_sample,
        candidate_sample_summary=candidate_sample,
        expected_state_summary=expected_state,
    )
    markdown = build_markdown(payload)

    assert round(payload["training"]["macro_f1"]["delta"], 6) == 0.05
    assert round(payload["training"]["per_class"]["near_fall"]["delta_f1"], 6) == 0.14
    assert round(payload["event"]["false_positives_per_hour"]["delta"], 6) == -0.6
    assert round(payload["sample_classification"]["macro_f1"]["delta"], 6) == 0.06
    assert round(payload["expected_state"]["delta"]["dominant_drift_rate"], 6) == 0.3
    assert "## 训练指标" in markdown
    assert "## 事件级指标" in markdown
    assert "## 样本级分类指标" in markdown
    assert "## 应用级期望状态对比" in markdown
    assert "near_fall" in markdown
