from pathlib import Path

from huling_guard.settings import load_settings


def test_load_settings_parses_training_options(tmp_path: Path) -> None:
    config_path = tmp_path / "train.yaml"
    config_path.write_text(
        """
data:
  manifest_path: data/train.jsonl
  eval_manifest_path: data/val.jsonl
  window_size: 64
  stride: 16
  num_joints: 17
model:
  pose_dim: 3
  kinematic_dim: 12
  kinematic_feature_set: v2
  scene_dim: 8
  quality_dim: 3
  hidden_dim: 256
  num_heads: 8
  depth: 6
  dropout: 0.1
training:
  seed: 3407
  batch_size: 64
  epochs: 30
  learning_rate: 0.0003
  min_learning_rate: 0.00003
  weight_decay: 0.0001
  clip_focal_gamma: 1.5
  risk_loss_weight: 0.3
  quality_loss_weight: 0.15
  sample_loss_weight: 0.5
  class_balance_beta: 0.999
  num_workers: 8
  pin_memory: true
  amp: true
  grad_clip_norm: 1.0
  scheduler: cosine
  balanced_sampling: true
  device: cuda
  output_dir: outputs/public_merged
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.model is not None
    assert settings.model.kinematic_feature_set == "v2"
    assert settings.model.kinematic_dim == 12
    assert settings.model.quality_dim == 3
    assert settings.training is not None
    assert settings.training.seed == 3407
    assert settings.training.batch_size == 64
    assert settings.training.min_learning_rate == 0.00003
    assert settings.training.clip_focal_gamma == 1.5
    assert settings.training.num_workers == 8
    assert settings.training.quality_loss_weight == 0.15
    assert settings.training.pin_memory is True
    assert settings.training.amp is True
    assert settings.training.grad_clip_norm == 1.0
    assert settings.training.scheduler == "cosine"
    assert settings.training.balanced_sampling is True


def test_load_settings_parses_runtime_and_room(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime_room.yaml"
    config_path.write_text(
        """
runtime:
  window_size: 64
  inference_stride: 4
  near_fall_threshold: 0.55
  fall_threshold: 0.7
  recovery_threshold: 0.65
  prolonged_lying_threshold: 0.75
  prolonged_lying_seconds: 18
  warning_cooldown_seconds: 9
room:
  prior_path: configs/sample_room_prior.json
  camera_name: sample_room
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.runtime is not None
    assert settings.runtime.recovery_threshold == 0.65
    assert settings.runtime.prolonged_lying_threshold == 0.75
    assert settings.room is not None
    assert settings.room.prior_path == Path("configs/sample_room_prior.json")
    assert settings.room.camera_name == "sample_room"


def test_load_settings_parses_augmentation(tmp_path: Path) -> None:
    config_path = tmp_path / "train_aug.yaml"
    config_path.write_text(
        """
data:
  manifest_path: data/train.jsonl
  eval_manifest_path: data/val.jsonl
  window_size: 64
  stride: 16
  num_joints: 17
model:
  pose_dim: 3
  kinematic_dim: 12
  kinematic_feature_set: v2
  scene_dim: 8
  quality_dim: 3
  hidden_dim: 256
  num_heads: 8
  depth: 6
  dropout: 0.1
augmentation:
  temporal_jitter_frames: 4
  time_mask_prob: 0.25
  time_mask_max_frames: 6
  pose_noise_std: 0.012
  kinematic_noise_std: 0.01
  confidence_dropout_prob: 0.04
training:
  seed: 2026
  batch_size: 64
  epochs: 30
  learning_rate: 0.0003
  min_learning_rate: 0.00003
  weight_decay: 0.0001
  clip_focal_gamma: 0.0
  risk_loss_weight: 0.3
  quality_loss_weight: 0.15
  class_balance_beta: 0.999
  num_workers: 8
  pin_memory: true
  amp: true
  grad_clip_norm: 1.0
  scheduler: cosine
  balanced_sampling: true
  device: cuda
  output_dir: outputs/public_merged
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.augmentation is not None
    assert settings.augmentation.temporal_jitter_frames == 4
    assert settings.augmentation.time_mask_prob == 0.25
    assert settings.augmentation.time_mask_max_frames == 6
    assert settings.augmentation.pose_noise_std == 0.012
    assert settings.augmentation.kinematic_noise_std == 0.01
    assert settings.augmentation.confidence_dropout_prob == 0.04
