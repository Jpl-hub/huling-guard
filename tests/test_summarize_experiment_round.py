from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from summarize_experiment_round import build_markdown, build_round_summary


def test_build_round_summary_collects_key_outputs() -> None:
    summary = build_round_summary(
        run_name="public_plus_ur_refined_v1",
        training_summary={
            "best_epoch": 12,
            "best_metrics": {
                "macro_f1": 0.52,
                "accuracy": 0.86,
                "weighted_f1": 0.83,
                "risk_accuracy": 0.90,
            },
        },
        sample_summary={
            "num_samples": 120,
            "num_windows": 960,
            "accuracy": 0.78,
            "macro_f1": 0.44,
            "weighted_f1": 0.77,
        },
        event_summary={
            "precision": 0.81,
            "recall": 0.79,
            "f1": 0.80,
            "false_positives_per_hour": 0.9,
            "mean_abs_delay_seconds": 0.58,
        },
        release_verification={"ok": True, "checked_artifacts": 6},
        deployment_selection={
            "selected": {
                "epoch": 15,
                "checkpoint_path": "/tmp/selected.pt",
                "sample_metrics": {"macro_f1": 0.46, "weighted_f1": 0.79},
                "train_metrics": {"macro_f1": 0.52},
            }
        },
        comparison_summary={
            "training": {
                "macro_f1": {"delta": 0.04},
                "accuracy": {"delta": 0.02},
                "per_class": {
                    "near_fall": {"delta_f1": 0.09},
                    "recovery": {"delta_f1": 0.05},
                },
            },
            "event": {
                "false_positives_per_hour": {"delta": -0.4},
                "mean_abs_delay_seconds": {"delta": -0.1},
            },
            "expected_state": {
                "expected_state": "normal",
                "delta": {
                    "with_incidents_rate": 0.0,
                    "dominant_drift_rate": 0.3,
                    "incident_sum": 29,
                },
            },
        },
        promotion_summary={"verdict": "promote", "passed_checks": 5, "total_checks": 5},
    )

    markdown = build_markdown(summary)

    assert summary["training"]["macro_f1"] == 0.52
    assert summary["sample_classification"]["macro_f1"] == 0.44
    assert summary["event"]["f1"] == 0.80
    assert summary["release_verification"]["ok"] is True
    assert summary["deployment_selection"]["epoch"] == 15
    assert summary["comparison"]["near_fall_f1_delta"] == 0.09
    assert summary["comparison"]["expected_state_dominant_drift_rate_delta"] == 0.3
    assert summary["promotion"]["verdict"] == "promote"
    assert "## 部署选择" in markdown
    assert "## 样本级分类结果" in markdown
    assert "## 当前轮保留判读" in markdown
    assert "expected_state(normal) dominant_drift_rate_delta" in markdown
