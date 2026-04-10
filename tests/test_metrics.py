from huling_guard.metrics import summarize_classification


def test_summarize_classification_computes_macro_metrics() -> None:
    summary = summarize_classification(
        labels=[0, 0, 1, 1, 2, 2],
        predictions=[0, 1, 1, 1, 2, 0],
        label_names=["normal", "fall", "lying"],
    )

    assert summary["support"] == 6
    assert summary["accuracy"] == 4 / 6
    assert summary["confusion_matrix"] == [
        [1, 1, 0],
        [0, 2, 0],
        [1, 0, 1],
    ]
    assert round(summary["macro_f1"], 6) == round((0.5 + 0.8 + 0.6666666666666666) / 3, 6)
    assert summary["per_class"]["fall"]["recall"] == 1.0
