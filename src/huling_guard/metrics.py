from __future__ import annotations

from typing import Any


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def summarize_classification(
    labels: list[int],
    predictions: list[int],
    label_names: list[str],
) -> dict[str, Any]:
    num_classes = len(label_names)
    confusion = [[0 for _ in range(num_classes)] for _ in range(num_classes)]
    for label_id, prediction_id in zip(labels, predictions, strict=True):
        confusion[label_id][prediction_id] += 1

    supports = [sum(row) for row in confusion]
    predicted_counts = [sum(confusion[row][col] for row in range(num_classes)) for col in range(num_classes)]

    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    weighted_f1_sum = 0.0
    total_support = sum(supports)

    for class_id, name in enumerate(label_names):
        tp = confusion[class_id][class_id]
        fp = predicted_counts[class_id] - tp
        fn = supports[class_id] - tp
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2.0 * precision * recall, precision + recall)
        per_class[name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": supports[class_id],
            "predicted": predicted_counts[class_id],
        }
        f1_values.append(f1)
        weighted_f1_sum += f1 * supports[class_id]

    total_correct = sum(confusion[i][i] for i in range(num_classes))
    return {
        "accuracy": _safe_div(total_correct, total_support),
        "macro_f1": _safe_div(sum(f1_values), len(f1_values)),
        "weighted_f1": _safe_div(weighted_f1_sum, total_support),
        "support": total_support,
        "label_names": label_names,
        "confusion_matrix": confusion,
        "per_class": per_class,
    }
