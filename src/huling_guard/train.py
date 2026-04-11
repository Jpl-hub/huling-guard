from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
import time
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from huling_guard.contracts import ScenePrior
from huling_guard.data.augmentation import (
    PoseAugmentationConfig,
    apply_pose_window_augmentation,
    sample_window_bounds,
)
from huling_guard.data.pose_io import load_pose_archive, normalize_pose_archive_coords
from huling_guard.features import (
    build_kinematic_features,
    build_scene_relation_features,
    get_kinematic_feature_dim,
    normalize_pose_sequence,
)
from huling_guard.metrics import summarize_classification
from huling_guard.model.losses import build_class_balance_weights, compute_losses
from huling_guard.model.scene_pose_temporal_net import ScenePoseTemporalNet
from huling_guard.settings import AppSettings, load_settings
from huling_guard.taxonomy import INTERNAL_STATES, STATE_TO_INDEX, risk_target_for_state

def _load_feature_archive(path: str | Path) -> dict[str, np.ndarray]:
    loaded = np.load(Path(path), allow_pickle=False)
    payload = {key: loaded[key].astype(np.float32) for key in loaded.files}
    required = {"poses", "kinematics", "scene_features"}
    missing = required.difference(payload)
    if missing:
        raise KeyError(f"{path} is missing cached feature arrays: {sorted(missing)}")
    return payload


def _pad_to_length(array: np.ndarray, length: int) -> tuple[np.ndarray, np.ndarray]:
    current = array.shape[0]
    if current >= length:
        return array[:length], np.zeros(length, dtype=bool)
    pad_shape = (length - current, *array.shape[1:])
    padded = np.concatenate([array, np.zeros(pad_shape, dtype=array.dtype)], axis=0)
    mask = np.zeros(length, dtype=bool)
    mask[current:] = True
    return padded, mask


def _build_frame_quality_target(poses: np.ndarray, padding_mask: np.ndarray) -> np.ndarray:
    confidences = poses[..., 2].astype(np.float32)
    mean_confidence = confidences.mean(axis=-1)
    visible_joint_ratio = (confidences >= 0.35).astype(np.float32).mean(axis=-1)
    target = np.clip((0.60 * mean_confidence) + (0.40 * visible_joint_ratio), 0.05, 1.0)
    target = target.astype(np.float32)
    target[padding_mask] = 0.0
    return target


@dataclass(slots=True)
class WindowEntry:
    sample_id: str
    pose_path: Path
    feature_path: Path | None
    kinematic_feature_set: str | None
    kinematic_dim: int | None
    scene_prior_path: Path | None
    internal_label: str
    start: int
    end: int
    sample_weight: float = 1.0


class PoseWindowDataset(Dataset):
    def __init__(
        self,
        manifest_path: str | Path,
        window_size: int,
        *,
        kinematic_feature_set: str = "v1",
        expected_kinematic_dim: int | None = None,
        augmentation: PoseAugmentationConfig | None = None,
    ) -> None:
        self.window_size = window_size
        self.kinematic_feature_set = kinematic_feature_set
        self.expected_kinematic_dim = expected_kinematic_dim
        self.augmentation = augmentation
        self.entries: list[WindowEntry] = []
        with Path(manifest_path).open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                self.entries.append(
                    WindowEntry(
                        sample_id=payload["sample_id"],
                        pose_path=Path(payload["pose_path"]),
                        feature_path=Path(payload["feature_path"])
                        if payload.get("feature_path")
                        else None,
                        kinematic_feature_set=str(payload["kinematic_feature_set"])
                        if payload.get("kinematic_feature_set")
                        else None,
                        kinematic_dim=int(payload["kinematic_dim"])
                        if payload.get("kinematic_dim") is not None
                        else None,
                        scene_prior_path=Path(payload["scene_prior_path"])
                        if payload.get("scene_prior_path")
                        else None,
                        internal_label=payload["internal_label"],
                        start=int(payload["start"]),
                        end=int(payload["end"]),
                        sample_weight=max(1.0, float(payload.get("sample_weight") or 1.0)),
                    )
                )

    def __len__(self) -> int:
        return len(self.entries)

    def class_counts(self) -> torch.Tensor:
        counts = torch.zeros(len(INTERNAL_STATES), dtype=torch.long)
        for entry in self.entries:
            counts[STATE_TO_INDEX[entry.internal_label]] += 1
        return counts

    def sample_weights(self) -> torch.Tensor:
        class_counts = self.class_counts().clamp_min(1).to(dtype=torch.float32)
        weights = torch.zeros(len(self.entries), dtype=torch.float32)
        for index, entry in enumerate(self.entries):
            weights[index] = entry.sample_weight / class_counts[STATE_TO_INDEX[entry.internal_label]]
        return weights

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        entry = self.entries[index]
        rng = None
        if self.augmentation is not None and self.augmentation.enabled():
            seed = int(torch.initial_seed()) + index
            rng = np.random.default_rng(seed % (2**32))
        if entry.feature_path is not None:
            feature_payload = _load_feature_archive(entry.feature_path)
            start, end = entry.start, entry.end
            if rng is not None:
                start, end = sample_window_bounds(
                    start=entry.start,
                    end=entry.end,
                    total_frames=int(feature_payload["poses"].shape[0]),
                    jitter_frames=self.augmentation.temporal_jitter_frames,
                    rng=rng,
                )
            poses = feature_payload["poses"][start:end]
            kinematics = feature_payload["kinematics"][start:end]
            scene_features = feature_payload["scene_features"][start:end]
            if self.expected_kinematic_dim is not None and kinematics.shape[-1] != self.expected_kinematic_dim:
                raise ValueError(
                    f"{entry.feature_path} has kinematic_dim={kinematics.shape[-1]} "
                    f"but expected {self.expected_kinematic_dim}"
                )
            if (
                entry.kinematic_feature_set is not None
                and entry.kinematic_feature_set != self.kinematic_feature_set
            ):
                raise ValueError(
                    f"{entry.feature_path} was cached with kinematic_feature_set="
                    f"{entry.kinematic_feature_set!r} but training expects "
                    f"{self.kinematic_feature_set!r}"
                )
        else:
            keypoints, payload = load_pose_archive(entry.pose_path)
            keypoints = normalize_pose_archive_coords(keypoints, payload)
            start, end = entry.start, entry.end
            if rng is not None:
                start, end = sample_window_bounds(
                    start=entry.start,
                    end=entry.end,
                    total_frames=int(keypoints.shape[0]),
                    jitter_frames=self.augmentation.temporal_jitter_frames,
                    rng=rng,
                )
            keypoints = keypoints[start:end]

            scene_prior = ScenePrior.load(entry.scene_prior_path) if entry.scene_prior_path else None
            poses = normalize_pose_sequence(keypoints)
            kinematics = build_kinematic_features(
                keypoints,
                feature_set=self.kinematic_feature_set,
            )
            scene_features = build_scene_relation_features(keypoints, scene_prior)

        if rng is not None:
            poses, kinematics, scene_features = apply_pose_window_augmentation(
                poses=poses,
                kinematics=kinematics,
                scene_features=scene_features,
                config=self.augmentation,
                rng=rng,
            )

        padded_pose, padding_mask = _pad_to_length(poses, self.window_size)
        padded_kinematics, _ = _pad_to_length(kinematics, self.window_size)
        padded_scene, _ = _pad_to_length(scene_features, self.window_size)

        frame_quality_target = _build_frame_quality_target(padded_pose, padding_mask)
        state = entry.internal_label
        return {
            "poses": torch.from_numpy(padded_pose),
            "kinematics": torch.from_numpy(padded_kinematics),
            "scene_features": torch.from_numpy(padded_scene),
            "padding_mask": torch.from_numpy(padding_mask),
            "label_id": torch.tensor(STATE_TO_INDEX[state], dtype=torch.long),
            "risk_target": torch.tensor(risk_target_for_state(state), dtype=torch.float32),
            "frame_quality_target": torch.from_numpy(frame_quality_target),
            "sample_weight": torch.tensor(entry.sample_weight, dtype=torch.float32),
        }


def _build_loader(
    dataset: PoseWindowDataset,
    batch_size: int,
    shuffle: bool,
    *,
    num_workers: int,
    pin_memory: bool,
    sampler: WeightedRandomSampler | None = None,
    generator: torch.Generator | None = None,
) -> DataLoader:
    loader_kwargs: dict[str, Any] = {
        "batch_size": batch_size,
        "num_workers": max(0, num_workers),
        "pin_memory": pin_memory,
    }
    if sampler is not None:
        loader_kwargs["sampler"] = sampler
    else:
        loader_kwargs["shuffle"] = shuffle
        if generator is not None:
            loader_kwargs["generator"] = generator
    if loader_kwargs["num_workers"] > 0:
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 2
    return DataLoader(dataset, **loader_kwargs)


def _move_to_device(batch: dict[str, torch.Tensor], device: torch.device) -> dict[str, torch.Tensor]:
    non_blocking = device.type == "cuda"
    return {key: value.to(device, non_blocking=non_blocking) for key, value in batch.items()}


def _build_scheduler(
    optimizer: torch.optim.Optimizer,
    *,
    epochs: int,
    scheduler_name: str,
    min_learning_rate: float,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    normalized = scheduler_name.strip().lower()
    if normalized in {"", "none"}:
        return None
    if normalized == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=max(1, epochs),
            eta_min=min_learning_rate,
        )
    raise ValueError(f"unsupported scheduler: {scheduler_name}")


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def _run_epoch(
    model: ScenePoseTemporalNet,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    class_weights: torch.Tensor | None,
    clip_focal_gamma: float,
    risk_loss_weight: float,
    quality_loss_weight: float,
    amp_enabled: bool,
    grad_clip_norm: float,
    scaler: torch.amp.GradScaler | None,
) -> dict[str, Any]:
    training = optimizer is not None
    model.train(mode=training)
    total_loss = 0.0
    total_samples = 0
    total_risk_correct = 0
    total_quality_abs_error = 0.0
    total_quality_frames = 0
    all_predictions: list[int] = []
    all_labels: list[int] = []

    for batch in loader:
        batch = _move_to_device(batch, device)
        with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
            outputs = model(
                poses=batch["poses"],
                kinematics=batch["kinematics"],
                scene_features=batch["scene_features"],
                padding_mask=batch["padding_mask"],
            )
            losses = compute_losses(
                outputs=outputs,
                label_ids=batch["label_id"],
                risk_targets=batch["risk_target"],
                frame_quality_targets=batch["frame_quality_target"],
                padding_mask=batch["padding_mask"],
                class_weights=class_weights,
                clip_focal_gamma=clip_focal_gamma,
                risk_loss_weight=risk_loss_weight,
                quality_loss_weight=quality_loss_weight,
            )
        if training:
            optimizer.zero_grad(set_to_none=True)
            if scaler is not None:
                scaler.scale(losses["total"]).backward()
                scaler.unscale_(optimizer)
                if grad_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip_norm)
                scaler.step(optimizer)
                scaler.update()
            else:
                losses["total"].backward()
                if grad_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip_norm)
                optimizer.step()

        total_loss += float(losses["total"].item()) * batch["label_id"].size(0)
        predictions = outputs["clip_logits"].argmax(dim=-1)
        risk_predictions = (torch.sigmoid(outputs["risk_logits"]) >= 0.5).float()
        total_risk_correct += int((risk_predictions == batch["risk_target"]).sum().item())
        valid_quality_mask = (~batch["padding_mask"]).to(dtype=outputs["frame_quality"].dtype)
        total_quality_abs_error += float((torch.abs(outputs["frame_quality"] - batch["frame_quality_target"]) * valid_quality_mask).sum().item())
        total_quality_frames += int(valid_quality_mask.sum().item())
        all_predictions.extend(int(value) for value in predictions.detach().cpu().tolist())
        all_labels.extend(int(value) for value in batch["label_id"].detach().cpu().tolist())
        total_samples += int(batch["label_id"].size(0))

    summary = summarize_classification(
        labels=all_labels,
        predictions=all_predictions,
        label_names=list(INTERNAL_STATES),
    )
    return {
        "loss": total_loss / max(total_samples, 1),
        "accuracy": summary["accuracy"],
        "macro_f1": summary["macro_f1"],
        "weighted_f1": summary["weighted_f1"],
        "risk_accuracy": total_risk_correct / max(total_samples, 1),
        "quality_mae": total_quality_abs_error / max(total_quality_frames, 1),
        "support": summary["support"],
        "label_names": summary["label_names"],
        "confusion_matrix": summary["confusion_matrix"],
        "per_class": summary["per_class"],
    }


def run_training(config_path: str | Path) -> Path:
    settings: AppSettings = load_settings(config_path)
    if settings.data is None or settings.model is None or settings.training is None:
        raise ValueError("training config must contain data/model/training sections")
    expected_kinematic_dim = get_kinematic_feature_dim(settings.model.kinematic_feature_set)
    if settings.model.kinematic_dim != expected_kinematic_dim:
        raise ValueError(
            "model.kinematic_dim does not match model.kinematic_feature_set "
            f"({settings.model.kinematic_dim} != {expected_kinematic_dim})"
        )

    device = torch.device(settings.training.device)
    _set_seed(settings.training.seed)
    pin_memory = settings.training.pin_memory and device.type == "cuda"
    loader_generator = torch.Generator()
    loader_generator.manual_seed(settings.training.seed)
    train_augmentation = (
        PoseAugmentationConfig(
            temporal_jitter_frames=settings.augmentation.temporal_jitter_frames,
            time_mask_prob=settings.augmentation.time_mask_prob,
            time_mask_max_frames=settings.augmentation.time_mask_max_frames,
            pose_noise_std=settings.augmentation.pose_noise_std,
            kinematic_noise_std=settings.augmentation.kinematic_noise_std,
            confidence_dropout_prob=settings.augmentation.confidence_dropout_prob,
        )
        if settings.augmentation is not None
        else None
    )
    train_dataset = PoseWindowDataset(
        manifest_path=settings.data.manifest_path,
        window_size=settings.data.window_size,
        kinematic_feature_set=settings.model.kinematic_feature_set,
        expected_kinematic_dim=expected_kinematic_dim,
        augmentation=train_augmentation,
    )
    train_sampler = None
    if settings.training.balanced_sampling:
        train_sampler = WeightedRandomSampler(
            weights=train_dataset.sample_weights(),
            num_samples=len(train_dataset),
            replacement=True,
            generator=loader_generator,
        )
    train_loader = _build_loader(
        dataset=train_dataset,
        batch_size=settings.training.batch_size,
        shuffle=train_sampler is None,
        num_workers=settings.training.num_workers,
        pin_memory=pin_memory,
        sampler=train_sampler,
        generator=loader_generator,
    )
    eval_loader = None
    if settings.data.eval_manifest_path:
        eval_dataset = PoseWindowDataset(
            manifest_path=settings.data.eval_manifest_path,
            window_size=settings.data.window_size,
            kinematic_feature_set=settings.model.kinematic_feature_set,
            expected_kinematic_dim=expected_kinematic_dim,
            augmentation=None,
        )
        eval_loader = _build_loader(
            dataset=eval_dataset,
            batch_size=settings.training.batch_size,
            shuffle=False,
            num_workers=settings.training.num_workers,
            pin_memory=pin_memory,
            generator=loader_generator,
        )
    train_class_counts = train_dataset.class_counts()
    hard_weighted_windows = sum(1 for entry in train_dataset.entries if entry.sample_weight > 1.0)
    class_weights = build_class_balance_weights(
        class_counts=train_class_counts,
        beta=settings.training.class_balance_beta,
    ).to(device)

    model = ScenePoseTemporalNet(
        num_joints=settings.data.num_joints,
        pose_dim=settings.model.pose_dim,
        kinematic_dim=settings.model.kinematic_dim,
        scene_dim=settings.model.scene_dim,
        quality_dim=settings.model.quality_dim,
        hidden_dim=settings.model.hidden_dim,
        num_heads=settings.model.num_heads,
        depth=settings.model.depth,
        dropout=settings.model.dropout,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=settings.training.learning_rate,
        weight_decay=settings.training.weight_decay,
    )
    scheduler = _build_scheduler(
        optimizer,
        epochs=settings.training.epochs,
        scheduler_name=settings.training.scheduler,
        min_learning_rate=settings.training.min_learning_rate,
    )
    amp_enabled = settings.training.amp and device.type == "cuda"
    scaler = torch.amp.GradScaler(device=device.type, enabled=amp_enabled)

    output_dir = settings.training.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "config.yaml").write_text(
        Path(config_path).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    best_eval_macro_f1 = float("-inf")
    history: list[dict[str, Any]] = []
    candidate_checkpoints: list[dict[str, Any]] = []

    for epoch in range(1, settings.training.epochs + 1):
        epoch_start = time.perf_counter()
        current_lr = float(optimizer.param_groups[0]["lr"])
        train_metrics = _run_epoch(
            model,
            train_loader,
            device,
            optimizer,
            class_weights=class_weights,
            clip_focal_gamma=settings.training.clip_focal_gamma,
            risk_loss_weight=settings.training.risk_loss_weight,
            quality_loss_weight=settings.training.quality_loss_weight,
            amp_enabled=amp_enabled,
            grad_clip_norm=settings.training.grad_clip_norm,
            scaler=scaler,
        )
        epoch_seconds = float(time.perf_counter() - epoch_start)
        metrics: dict[str, Any] = {
            "epoch": epoch,
            "lr": current_lr,
            "epoch_seconds": epoch_seconds,
            "train": train_metrics,
        }
        if eval_loader is not None:
            with torch.no_grad():
                eval_metrics = _run_epoch(
                    model,
                    eval_loader,
                    device,
                    optimizer=None,
                    class_weights=class_weights,
                    clip_focal_gamma=settings.training.clip_focal_gamma,
                    risk_loss_weight=settings.training.risk_loss_weight,
                    quality_loss_weight=settings.training.quality_loss_weight,
                    amp_enabled=amp_enabled,
                    grad_clip_norm=settings.training.grad_clip_norm,
                    scaler=None,
                )
            metrics["eval"] = eval_metrics
            if float(eval_metrics["macro_f1"]) >= best_eval_macro_f1:
                best_eval_macro_f1 = float(eval_metrics["macro_f1"])
                candidate_checkpoint_path = checkpoint_dir / f"epoch_{epoch:03d}_macro_f1_{best_eval_macro_f1:.4f}.pt"
                torch.save(model.state_dict(), candidate_checkpoint_path)
                torch.save(model.state_dict(), output_dir / "best.pt")
                candidate_checkpoints.append(
                    {
                        "epoch": epoch,
                        "selection_metric": "macro_f1",
                        "selection_scope": "eval",
                        "metric_value": best_eval_macro_f1,
                        "checkpoint_path": str(candidate_checkpoint_path),
                    }
                )
                metrics["saved_best_checkpoint"] = str(candidate_checkpoint_path)
        elif float(train_metrics["macro_f1"]) >= best_eval_macro_f1:
            best_eval_macro_f1 = float(train_metrics["macro_f1"])
            candidate_checkpoint_path = checkpoint_dir / f"epoch_{epoch:03d}_macro_f1_{best_eval_macro_f1:.4f}.pt"
            torch.save(model.state_dict(), candidate_checkpoint_path)
            torch.save(model.state_dict(), output_dir / "best.pt")
            candidate_checkpoints.append(
                {
                    "epoch": epoch,
                    "selection_metric": "macro_f1",
                    "selection_scope": "train",
                    "metric_value": best_eval_macro_f1,
                    "checkpoint_path": str(candidate_checkpoint_path),
                }
            )
            metrics["saved_best_checkpoint"] = str(candidate_checkpoint_path)
        history.append(metrics)
        print(
            f"[train] epoch={epoch} lr={current_lr:.6f} seconds={epoch_seconds:.2f} train_loss={train_metrics['loss']:.4f} train_macro_f1={train_metrics['macro_f1']:.4f}",
            flush=True,
        )
        if "eval" in metrics:
            eval_metrics = metrics["eval"]
            print(
                f"[eval] epoch={epoch} eval_loss={eval_metrics['loss']:.4f} eval_macro_f1={eval_metrics['macro_f1']:.4f}",
                flush=True,
            )
        if scheduler is not None:
            scheduler.step()

    history_path = output_dir / "history.json"
    history_path.write_text(json.dumps(history, ensure_ascii=True, indent=2), encoding="utf-8")
    torch.save(model.state_dict(), output_dir / "latest.pt")
    if history:
        scored_runs = [
            (entry.get("eval", entry["train"])["macro_f1"], entry["epoch"], entry)
            for entry in history
        ]
        _, best_epoch, best_entry = max(scored_runs, key=lambda item: (item[0], -item[1]))
        summary = {
            "best_epoch": best_epoch,
            "selection_metric": "macro_f1",
            "best_checkpoint_path": str(output_dir / "best.pt"),
            "candidate_checkpoints": candidate_checkpoints,
            "amp": amp_enabled,
            "scheduler": settings.training.scheduler,
            "balanced_sampling": settings.training.balanced_sampling,
            "augmentation": (
                {
                    "temporal_jitter_frames": train_augmentation.temporal_jitter_frames,
                    "time_mask_prob": train_augmentation.time_mask_prob,
                    "time_mask_max_frames": train_augmentation.time_mask_max_frames,
                    "pose_noise_std": train_augmentation.pose_noise_std,
                    "kinematic_noise_std": train_augmentation.kinematic_noise_std,
                    "confidence_dropout_prob": train_augmentation.confidence_dropout_prob,
                }
                if train_augmentation is not None
                else None
            ),
            "batch_size": settings.training.batch_size,
            "num_workers": settings.training.num_workers,
            "class_balance_beta": settings.training.class_balance_beta,
            "clip_focal_gamma": settings.training.clip_focal_gamma,
            "risk_loss_weight": settings.training.risk_loss_weight,
            "train_class_counts": {
                state: int(train_class_counts[idx].item()) for idx, state in enumerate(INTERNAL_STATES)
            },
            "hard_weighted_windows": int(hard_weighted_windows),
            "class_weights": {
                state: float(class_weights[idx].detach().cpu().item())
                for idx, state in enumerate(INTERNAL_STATES)
            },
            "best_metrics": best_entry.get("eval", best_entry["train"]),
            "final_metrics": history[-1].get("eval", history[-1]["train"]),
        }
        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    return output_dir
