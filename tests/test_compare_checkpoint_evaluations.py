from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import compare_checkpoint_evaluations as checkpoint_compare


def test_build_comparison_payload_computes_sample_and_window_deltas() -> None:
    baseline = {
        "checkpoint_path": "baseline.pt",
        "eval_manifest_path": "baseline_eval.jsonl",
        "window": {
            "accuracy": 0.80,
            "macro_f1": 0.70,
            "weighted_f1": 0.78,
            "support": 100,
            "per_class": {
                "fall": {"f1": 0.60, "recall": 0.55, "support": 20},
            },
        },
        "sample": {
            "accuracy": 0.82,
            "macro_f1": 0.71,
            "weighted_f1": 0.80,
            "num_samples": 12,
            "num_windows": 100,
            "per_class": {
                "fall": {"f1": 0.65, "recall": 0.60, "support": 6},
            },
        },
    }
    candidate = {
        "checkpoint_path": "candidate.pt",
        "eval_manifest_path": "candidate_eval.jsonl",
        "window": {
            "accuracy": 0.86,
            "macro_f1": 0.75,
            "weighted_f1": 0.83,
            "support": 100,
            "per_class": {
                "fall": {"f1": 0.72, "recall": 0.68, "support": 20},
            },
        },
        "sample": {
            "accuracy": 0.88,
            "macro_f1": 0.79,
            "weighted_f1": 0.86,
            "num_samples": 12,
            "num_windows": 100,
            "per_class": {
                "fall": {"f1": 0.78, "recall": 0.75, "support": 6},
            },
        },
    }

    payload = checkpoint_compare.build_comparison_payload(
        baseline_summary=baseline,
        candidate_summary=candidate,
    )

    assert payload["window"]["macro_f1"]["delta"] == pytest.approx(0.05)
    assert payload["sample"]["accuracy"]["delta"] == pytest.approx(0.06)
    assert payload["sample"]["per_class"]["fall"]["delta_f1"] == pytest.approx(0.13)
    assert payload["baseline"]["checkpoint_path"] == "baseline.pt"


def test_build_markdown_renders_checkpoint_comparison_sections() -> None:
    markdown = checkpoint_compare.build_markdown(
        {
            "baseline": {
                "checkpoint_path": "baseline.pt",
                "eval_manifest_path": "baseline_eval.jsonl",
            },
            "candidate": {
                "checkpoint_path": "candidate.pt",
                "eval_manifest_path": "candidate_eval.jsonl",
            },
            "window": {
                "accuracy": {"baseline": 0.8, "candidate": 0.9, "delta": 0.1},
                "macro_f1": {"baseline": 0.7, "candidate": 0.8, "delta": 0.1},
                "weighted_f1": {"baseline": 0.75, "candidate": 0.85, "delta": 0.1},
                "support": {"baseline": 100, "candidate": 100, "delta": 0},
                "per_class": {},
            },
            "sample": {
                "accuracy": {"baseline": 0.82, "candidate": 0.88, "delta": 0.06},
                "macro_f1": {"baseline": 0.71, "candidate": 0.79, "delta": 0.08},
                "weighted_f1": {"baseline": 0.80, "candidate": 0.86, "delta": 0.06},
                "num_samples": {"baseline": 12, "candidate": 12, "delta": 0},
                "num_windows": {"baseline": 100, "candidate": 100, "delta": 0},
                "per_class": {
                    "fall": {
                        "baseline_f1": 0.65,
                        "candidate_f1": 0.78,
                        "delta_f1": 0.13,
                        "baseline_recall": 0.60,
                        "candidate_recall": 0.75,
                        "delta_recall": 0.15,
                        "baseline_support": 6,
                        "candidate_support": 6,
                    }
                },
            },
        }
    )

    assert "# Checkpoint 同口径重评对比" in markdown
    assert "## 窗口级指标" in markdown
    assert "## 样本级指标" in markdown
    assert "baseline_checkpoint: baseline.pt" in markdown
    assert "fall: f1 0.6500 -> 0.7800 (+0.1300)" in markdown
