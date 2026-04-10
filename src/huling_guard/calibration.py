from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import yaml
from huling_guard.taxonomy import STATE_TO_INDEX
from huling_guard.features import get_kinematic_feature_dim

if TYPE_CHECKING:
    import torch
    from torch.utils.data import DataLoader

    from huling_guard.model import ScenePoseTemporalNet
    from huling_guard.settings import AppSettings


CALIBRATION_STATES = (
    "near_fall",
    "fall",
    "recovery",
    "prolonged_lying",
)


def _sync_runtime_payload_with_train_settings(
    runtime_payload: dict[str, Any],
    train_settings: AppSettings,
) -> dict[str, Any]:
    if train_settings.data is None:
        raise ValueError("train config must contain data settings")
    runtime_payload.setdefault("runtime", {})
    runtime_payload["runtime"]["window_size"] = int(train_settings.data.window_size)
    return runtime_payload


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _binary_metrics(labels: list[int], scores: list[float], threshold: float) -> dict[str, float | int]:
    tp = fp = fn = tn = 0
    for label, score in zip(labels, scores, strict=True):
        predicted = score >= threshold
        if label == 1 and predicted:
            tp += 1
        elif label == 0 and predicted:
            fp += 1
        elif label == 1 and not predicted:
            fn += 1
        else:
            tn += 1
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    return {
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": tp + fn,
        "predicted_positive": tp + fp,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def select_best_threshold(
    labels: list[int],
    scores: list[float],
    *,
    default_threshold: float,
    threshold_grid: list[float],
) -> dict[str, float | int]:
    support = sum(labels)
    if support == 0:
        metrics = _binary_metrics(labels, scores, default_threshold)
        metrics["selected"] = False
        return metrics

    ranked: list[tuple[float, float, float, float, dict[str, float | int]]] = []
    for threshold in threshold_grid:
        metrics = _binary_metrics(labels, scores, threshold)
        ranked.append(
            (
                float(metrics["f1"]),
                float(metrics["precision"]),
                float(threshold),
                -abs(float(threshold) - default_threshold),
                metrics,
            )
        )
    _, _, _, _, best = max(ranked, key=lambda item: item[:4])
    best["selected"] = True
    return best


def _build_model(settings: "AppSettings", checkpoint_path: Path, device: "torch.device") -> "ScenePoseTemporalNet":
    import torch

    from huling_guard.model import ScenePoseTemporalNet

    if settings.data is None or settings.model is None:
        raise ValueError("train config must contain data and model sections")
    expected_kinematic_dim = get_kinematic_feature_dim(settings.model.kinematic_feature_set)
    if settings.model.kinematic_dim != expected_kinematic_dim:
        raise ValueError(
            "model.kinematic_dim does not match model.kinematic_feature_set "
            f"({settings.model.kinematic_dim} != {expected_kinematic_dim})"
        )
    model = ScenePoseTemporalNet(
        num_joints=settings.data.num_joints,
        pose_dim=settings.model.pose_dim,
        kinematic_dim=settings.model.kinematic_dim,
        scene_dim=settings.model.scene_dim,
        hidden_dim=settings.model.hidden_dim,
        num_heads=settings.model.num_heads,
        depth=settings.model.depth,
        dropout=settings.model.dropout,
    )
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def _build_eval_loader(settings: "AppSettings", device: "torch.device") -> "DataLoader":
    from torch.utils.data import DataLoader

    from huling_guard.train import PoseWindowDataset

    if settings.data is None or settings.data.eval_manifest_path is None or settings.training is None:
        raise ValueError("calibration requires data.eval_manifest_path and training settings")
    pin_memory = settings.training.pin_memory and device.type == "cuda"
    dataset = PoseWindowDataset(
        manifest_path=settings.data.eval_manifest_path,
        window_size=settings.data.window_size,
        kinematic_feature_set=settings.model.kinematic_feature_set,
        expected_kinematic_dim=get_kinematic_feature_dim(settings.model.kinematic_feature_set),
    )
    loader_kwargs: dict[str, Any] = {
        "batch_size": settings.training.batch_size,
        "shuffle": False,
        "num_workers": max(0, settings.training.num_workers),
        "pin_memory": pin_memory,
    }
    if loader_kwargs["num_workers"] > 0:
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 2
    return DataLoader(dataset, **loader_kwargs)


def _collect_eval_outputs(
    settings: AppSettings,
    checkpoint_path: Path,
    device: str,
) -> tuple[list[int], dict[str, list[float]]]:
    import torch

    torch_device = torch.device(device)
    loader = _build_eval_loader(settings, torch_device)
    model = _build_model(settings, checkpoint_path=checkpoint_path, device=torch_device)
    amp_enabled = settings.training is not None and settings.training.amp and torch_device.type == "cuda"

    labels: list[int] = []
    state_scores = {state: [] for state in CALIBRATION_STATES}
    for batch in loader:
        moved = {
            key: value.to(torch_device, non_blocking=torch_device.type == "cuda")
            for key, value in batch.items()
        }
        with torch.no_grad():
            with torch.amp.autocast(device_type=torch_device.type, enabled=amp_enabled):
                outputs = model(
                    poses=moved["poses"],
                    kinematics=moved["kinematics"],
                    scene_features=moved["scene_features"],
                    padding_mask=moved["padding_mask"],
                )
                probabilities = torch.softmax(outputs["clip_logits"], dim=-1).detach().cpu()
        labels.extend(int(value) for value in batch["label_id"].tolist())
        for state in CALIBRATION_STATES:
            state_index = STATE_TO_INDEX[state]
            state_scores[state].extend(float(value) for value in probabilities[:, state_index].tolist())
    return labels, state_scores


def calibrate_runtime_thresholds(
    *,
    train_config_path: str | Path,
    runtime_config_path: str | Path,
    checkpoint_path: str | Path,
    output_path: str | Path,
    device: str = "cuda",
    threshold_step: float = 0.02,
) -> Path:
    from huling_guard.settings import load_settings

    train_settings = load_settings(train_config_path)
    runtime_payload = yaml.safe_load(Path(runtime_config_path).read_text(encoding="utf-8"))
    runtime_payload = _sync_runtime_payload_with_train_settings(runtime_payload, train_settings)
    runtime_settings = load_settings(runtime_config_path)
    if runtime_settings.runtime is None:
        raise ValueError("runtime config must contain runtime settings")

    threshold_grid = [
        round(value * threshold_step, 4)
        for value in range(max(1, int(0.1 / threshold_step)), int(0.95 / threshold_step) + 1)
    ]

    labels, state_scores = _collect_eval_outputs(
        settings=train_settings,
        checkpoint_path=Path(checkpoint_path),
        device=device,
    )

    defaults = {
        "near_fall": runtime_settings.runtime.near_fall_threshold,
        "fall": runtime_settings.runtime.fall_threshold,
        "recovery": runtime_settings.runtime.recovery_threshold,
        "prolonged_lying": runtime_settings.runtime.prolonged_lying_threshold,
    }
    results: dict[str, dict[str, float | int | bool]] = {}
    for state in CALIBRATION_STATES:
        binary_labels = [1 if label == STATE_TO_INDEX[state] else 0 for label in labels]
        results[state] = select_best_threshold(
            binary_labels,
            state_scores[state],
            default_threshold=defaults[state],
            threshold_grid=threshold_grid,
        )

    runtime_payload.setdefault("runtime", {})
    runtime_payload["runtime"]["near_fall_threshold"] = float(results["near_fall"]["threshold"])
    runtime_payload["runtime"]["fall_threshold"] = float(results["fall"]["threshold"])
    runtime_payload["runtime"]["recovery_threshold"] = float(results["recovery"]["threshold"])
    runtime_payload["runtime"]["prolonged_lying_threshold"] = float(
        results["prolonged_lying"]["threshold"]
    )
    runtime_payload["calibration"] = {
        "checkpoint_path": str(Path(checkpoint_path)),
        "train_config_path": str(Path(train_config_path)),
        "states": results,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(runtime_payload, sort_keys=False), encoding="utf-8")
    return output


def summarize_calibration_output(path: str | Path) -> str:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    lines = [
        f"# 阈值校准结果：{Path(path).name}",
        "",
        "## 状态阈值",
    ]
    for state in CALIBRATION_STATES:
        metrics = payload["calibration"]["states"][state]
        lines.append(
            (
                f"- {state}: threshold={float(metrics['threshold']):.2f}, "
                f"f1={float(metrics['f1']):.4f}, "
                f"precision={float(metrics['precision']):.4f}, "
                f"recall={float(metrics['recall']):.4f}, "
                f"support={int(metrics['support'])}"
            )
        )
    return "\n".join(lines) + "\n"
