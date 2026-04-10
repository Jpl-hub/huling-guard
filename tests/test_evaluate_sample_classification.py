from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate_sample_classification import aggregate_sample_predictions, build_markdown


def test_aggregate_sample_predictions_averages_windows_per_sample() -> None:
    summary = aggregate_sample_predictions(
        [
            {"sample_id": "s1", "label_id": 1, "probs": [0.1, 0.8, 0.1]},
            {"sample_id": "s1", "label_id": 1, "probs": [0.2, 0.7, 0.1]},
            {"sample_id": "s2", "label_id": 2, "probs": [0.1, 0.2, 0.7]},
            {"sample_id": "s2", "label_id": 2, "probs": [0.2, 0.2, 0.6]},
        ],
        label_names=["normal", "fall", "recovery"],
    )

    assert summary["num_samples"] == 2
    assert summary["num_windows"] == 4
    assert summary["accuracy"] == 1.0
    assert summary["per_class"]["fall"]["support"] == 1
    assert summary["samples"][0]["window_count"] == 2


def test_build_markdown_renders_sample_level_section() -> None:
    markdown = build_markdown(
        {
            "num_samples": 2,
            "num_windows": 4,
            "accuracy": 1.0,
            "macro_f1": 1.0,
            "weighted_f1": 1.0,
            "label_names": ["normal", "fall"],
            "per_class": {
                "normal": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 1},
                "fall": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 1},
            },
        }
    )

    assert "# 样本级分类评估" in markdown
    assert "- num_samples: 2" in markdown
    assert "- fall: precision=1.0000, recall=1.0000, f1=1.0000, support=1" in markdown
