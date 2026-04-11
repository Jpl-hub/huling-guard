from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(slots=True)
class DataSettings:
    manifest_path: Path
    eval_manifest_path: Path | None
    window_size: int
    stride: int
    num_joints: int


@dataclass(slots=True)
class ModelSettings:
    pose_dim: int
    kinematic_dim: int
    kinematic_feature_set: str
    scene_dim: int
    quality_dim: int
    hidden_dim: int
    num_heads: int
    depth: int
    dropout: float


@dataclass(slots=True)
class TrainingSettings:
    seed: int
    batch_size: int
    epochs: int
    learning_rate: float
    min_learning_rate: float
    weight_decay: float
    clip_focal_gamma: float
    risk_loss_weight: float
    quality_loss_weight: float
    sample_loss_weight: float
    class_balance_beta: float
    num_workers: int
    pin_memory: bool
    amp: bool
    grad_clip_norm: float
    scheduler: str
    balanced_sampling: bool
    device: str
    output_dir: Path


@dataclass(slots=True)
class AugmentationSettings:
    temporal_jitter_frames: int = 0
    time_mask_prob: float = 0.0
    time_mask_max_frames: int = 0
    pose_noise_std: float = 0.0
    kinematic_noise_std: float = 0.0
    confidence_dropout_prob: float = 0.0


@dataclass(slots=True)
class RuntimeSettings:
    window_size: int
    inference_stride: int
    near_fall_threshold: float
    fall_threshold: float
    recovery_threshold: float
    prolonged_lying_threshold: float
    prolonged_lying_seconds: int
    warning_cooldown_seconds: int


@dataclass(slots=True)
class RoomSettings:
    prior_path: Path
    camera_name: str


@dataclass(slots=True)
class AppSettings:
    data: DataSettings | None = None
    model: ModelSettings | None = None
    training: TrainingSettings | None = None
    augmentation: AugmentationSettings | None = None
    runtime: RuntimeSettings | None = None
    room: RoomSettings | None = None


def _as_path(value: str | None) -> Path | None:
    if value is None:
        return None
    return Path(value)


def load_settings(path: str | Path) -> AppSettings:
    payload = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    data = payload.get('data')
    model = payload.get('model')
    training = payload.get('training')
    augmentation = payload.get('augmentation')
    runtime = payload.get('runtime')
    room = payload.get('room')
    return AppSettings(
        data=DataSettings(
            manifest_path=Path(data['manifest_path']),
            eval_manifest_path=_as_path(data.get('eval_manifest_path')),
            window_size=int(data['window_size']),
            stride=int(data['stride']),
            num_joints=int(data['num_joints']),
        )
        if data
        else None,
        model=ModelSettings(
            pose_dim=int(model['pose_dim']),
            kinematic_dim=int(model['kinematic_dim']),
            kinematic_feature_set=str(model.get('kinematic_feature_set', 'v1')),
            scene_dim=int(model['scene_dim']),
            quality_dim=int(model.get('quality_dim', 3)),
            hidden_dim=int(model['hidden_dim']),
            num_heads=int(model['num_heads']),
            depth=int(model['depth']),
            dropout=float(model['dropout']),
        )
        if model
        else None,
        training=TrainingSettings(
            seed=int(training.get('seed', 2026)),
            batch_size=int(training['batch_size']),
            epochs=int(training['epochs']),
            learning_rate=float(training['learning_rate']),
            min_learning_rate=float(training.get('min_learning_rate', 1e-5)),
            weight_decay=float(training['weight_decay']),
            clip_focal_gamma=float(training.get('clip_focal_gamma', 0.0)),
            risk_loss_weight=float(training.get('risk_loss_weight', 0.3)),
            quality_loss_weight=float(training.get('quality_loss_weight', 0.15)),
            sample_loss_weight=float(training.get('sample_loss_weight', 0.0)),
            class_balance_beta=float(training.get('class_balance_beta', 0.999)),
            num_workers=int(training.get('num_workers', 4)),
            pin_memory=bool(training.get('pin_memory', True)),
            amp=bool(training.get('amp', True)),
            grad_clip_norm=float(training.get('grad_clip_norm', 1.0)),
            scheduler=str(training.get('scheduler', 'cosine')),
            balanced_sampling=bool(training.get('balanced_sampling', True)),
            device=str(training['device']),
            output_dir=Path(training['output_dir']),
        )
        if training
        else None,
        augmentation=AugmentationSettings(
            temporal_jitter_frames=int(augmentation.get('temporal_jitter_frames', 0)),
            time_mask_prob=float(augmentation.get('time_mask_prob', 0.0)),
            time_mask_max_frames=int(augmentation.get('time_mask_max_frames', 0)),
            pose_noise_std=float(augmentation.get('pose_noise_std', 0.0)),
            kinematic_noise_std=float(augmentation.get('kinematic_noise_std', 0.0)),
            confidence_dropout_prob=float(
                augmentation.get('confidence_dropout_prob', 0.0)
            ),
        )
        if augmentation
        else None,
        runtime=RuntimeSettings(
            window_size=int(runtime['window_size']),
            inference_stride=int(runtime['inference_stride']),
            near_fall_threshold=float(runtime['near_fall_threshold']),
            fall_threshold=float(runtime['fall_threshold']),
            recovery_threshold=float(runtime.get('recovery_threshold', 0.55)),
            prolonged_lying_threshold=float(runtime.get('prolonged_lying_threshold', 0.6)),
            prolonged_lying_seconds=int(runtime['prolonged_lying_seconds']),
            warning_cooldown_seconds=int(runtime['warning_cooldown_seconds']),
        )
        if runtime
        else None,
        room=RoomSettings(
            prior_path=Path(room['prior_path']),
            camera_name=str(room['camera_name']),
        )
        if room
        else None,
    )
