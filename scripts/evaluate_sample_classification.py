from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TYPE_CHECKING

from huling_guard.metrics import summarize_classification
from huling_guard.settings import AppSettings, load_settings
from huling_guard.taxonomy import INTERNAL_STATES
from huling_guard.features import get_kinematic_feature_dim

if TYPE_CHECKING:
    import torch
    from huling_guard.model import ScenePoseTemporalNet


def aggregate_sample_predictions(
    rows: list[dict[str, Any]],
    *,
    label_names: list[str],
) -> dict[str, Any]:
    sample_scores: dict[str, list[list[float]]] = defaultdict(list)
    sample_label_votes: dict[str, list[int]] = defaultdict(list)

    for row in rows:
        sample_id = str(row["sample_id"])
        sample_scores[sample_id].append([float(value) for value in row["probs"]])
        sample_label_votes[sample_id].append(int(row["label_id"]))

    labels: list[int] = []
    predictions: list[int] = []
    sample_rows: list[dict[str, Any]] = []
    for sample_id in sorted(sample_scores):
        window_scores = sample_scores[sample_id]
        mean_scores = [
            sum(values[class_index] for values in window_scores) / len(window_scores)
            for class_index in range(len(label_names))
        ]
        label_vote_counter = Counter(sample_label_votes[sample_id])
        label_id = label_vote_counter.most_common(1)[0][0]
        prediction_id = max(range(len(label_names)), key=lambda index: mean_scores[index])
        labels.append(label_id)
        predictions.append(prediction_id)
        sample_rows.append(
            {
                "sample_id": sample_id,
                "label_id": label_id,
                "predicted_id": prediction_id,
                "label_name": label_names[label_id],
                "predicted_name": label_names[prediction_id],
                "mean_probs": mean_scores,
                "window_count": len(window_scores),
            }
        )

    summary = summarize_classification(labels=labels, predictions=predictions, label_names=label_names)
    summary["num_samples"] = len(sample_rows)
    summary["num_windows"] = len(rows)
    summary["samples"] = sample_rows
    return summary


def _build_model(settings: AppSettings, checkpoint_path: Path, device: "torch.device") -> "ScenePoseTemporalNet":
    import torch

    from huling_guard.model import ScenePoseTemporalNet

    if settings.data is None or settings.model is None:
        raise ValueError("train config must contain data and model settings")
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


def evaluate_sample_classification(
    *,
    train_config_path: Path,
    checkpoint_path: Path,
    device: str,
) -> dict[str, Any]:
    settings = load_settings(train_config_path)
    if settings.data is None or settings.training is None or settings.data.eval_manifest_path is None:
        raise ValueError("sample evaluation requires training data settings with eval_manifest_path")

    import torch
    from torch.utils.data import DataLoader

    from huling_guard.train import PoseWindowDataset

    torch_device = torch.device(device)
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
        "pin_memory": settings.training.pin_memory and torch_device.type == "cuda",
    }
    if loader_kwargs["num_workers"] > 0:
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 2
    loader = DataLoader(dataset, **loader_kwargs)

    model = _build_model(settings, checkpoint_path=checkpoint_path, device=torch_device)
    amp_enabled = settings.training.amp and torch_device.type == "cuda"

    rows: list[dict[str, Any]] = []
    offset = 0
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
                probs = torch.softmax(outputs["clip_logits"], dim=-1).detach().cpu().tolist()
        batch_size = len(probs)
        for index in range(batch_size):
            entry = dataset.entries[offset + index]
            rows.append(
                {
                    "sample_id": entry.sample_id,
                    "label_id": int(batch["label_id"][index].item()),
                    "probs": probs[index],
                }
            )
        offset += batch_size

    summary = aggregate_sample_predictions(rows, label_names=list(INTERNAL_STATES))
    summary["train_config_path"] = str(train_config_path)
    summary["checkpoint_path"] = str(checkpoint_path)
    return summary


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 样本级分类评估",
        "",
        f"- num_samples: {summary['num_samples']}",
        f"- num_windows: {summary['num_windows']}",
        f"- accuracy: {summary['accuracy']:.4f}",
        f"- macro_f1: {summary['macro_f1']:.4f}",
        f"- weighted_f1: {summary['weighted_f1']:.4f}",
        "",
        "## 各类别",
    ]
    for name in summary["label_names"]:
        metrics = summary["per_class"][name]
        lines.append(
            f"- {name}: precision={metrics['precision']:.4f}, recall={metrics['recall']:.4f}, "
            f"f1={metrics['f1']:.4f}, support={metrics['support']}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    summary = evaluate_sample_classification(
        train_config_path=args.train_config.resolve(),
        checkpoint_path=args.checkpoint.resolve(),
        device=args.device,
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
