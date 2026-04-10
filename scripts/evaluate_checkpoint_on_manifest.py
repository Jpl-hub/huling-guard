from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from evaluate_sample_classification import aggregate_sample_predictions
from huling_guard.features import get_kinematic_feature_dim
from huling_guard.metrics import summarize_classification
from huling_guard.settings import load_settings
from huling_guard.taxonomy import INTERNAL_STATES
from huling_guard.train import PoseWindowDataset


def _build_model(train_config_path: Path, checkpoint_path: Path, device: torch.device) -> torch.nn.Module:
    from huling_guard.model import ScenePoseTemporalNet

    settings = load_settings(train_config_path)
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


def evaluate_checkpoint_on_manifest(
    *,
    train_config_path: Path,
    checkpoint_path: Path,
    eval_manifest_path: Path,
    device: str,
) -> dict[str, Any]:
    settings = load_settings(train_config_path)
    if settings.data is None or settings.training is None or settings.model is None:
        raise ValueError("train config must contain data, model, and training settings")

    torch_device = torch.device(device)
    dataset = PoseWindowDataset(
        manifest_path=eval_manifest_path,
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

    model = _build_model(train_config_path=train_config_path, checkpoint_path=checkpoint_path, device=torch_device)
    amp_enabled = settings.training.amp and torch_device.type == "cuda"

    labels: list[int] = []
    predictions: list[int] = []
    sample_rows: list[dict[str, Any]] = []
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
                probs = torch.softmax(outputs["clip_logits"], dim=-1).detach().cpu()
        batch_predictions = probs.argmax(dim=-1).tolist()
        batch_labels = batch["label_id"].tolist()
        labels.extend(int(value) for value in batch_labels)
        predictions.extend(int(value) for value in batch_predictions)
        for index in range(len(batch_predictions)):
            entry = dataset.entries[offset + index]
            sample_rows.append(
                {
                    "sample_id": entry.sample_id,
                    "label_id": int(batch_labels[index]),
                    "probs": [float(value) for value in probs[index].tolist()],
                }
            )
        offset += len(batch_predictions)

    window_summary = summarize_classification(
        labels=labels,
        predictions=predictions,
        label_names=list(INTERNAL_STATES),
    )
    sample_summary = aggregate_sample_predictions(sample_rows, label_names=list(INTERNAL_STATES))
    return {
        "train_config_path": str(train_config_path),
        "checkpoint_path": str(checkpoint_path),
        "eval_manifest_path": str(eval_manifest_path),
        "window": window_summary,
        "sample": sample_summary,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    window = summary["window"]
    sample = summary["sample"]
    lines = [
        "# Checkpoint 重评估",
        "",
        f"- checkpoint: {summary['checkpoint_path']}",
        f"- eval_manifest: {summary['eval_manifest_path']}",
        "",
        "## 窗口级指标",
        f"- accuracy: {window['accuracy']:.4f}",
        f"- macro_f1: {window['macro_f1']:.4f}",
        f"- weighted_f1: {window['weighted_f1']:.4f}",
        "",
        "## 样本级指标",
        f"- accuracy: {sample['accuracy']:.4f}",
        f"- macro_f1: {sample['macro_f1']:.4f}",
        f"- weighted_f1: {sample['weighted_f1']:.4f}",
        f"- num_samples: {sample['num_samples']}",
        f"- num_windows: {sample['num_windows']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--eval-manifest", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    summary = evaluate_checkpoint_on_manifest(
        train_config_path=args.train_config.resolve(),
        checkpoint_path=args.checkpoint.resolve(),
        eval_manifest_path=args.eval_manifest.resolve(),
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
