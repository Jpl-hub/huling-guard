from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class PoseAugmentationConfig:
    temporal_jitter_frames: int = 0
    time_mask_prob: float = 0.0
    time_mask_max_frames: int = 0
    pose_noise_std: float = 0.0
    kinematic_noise_std: float = 0.0
    confidence_dropout_prob: float = 0.0

    def enabled(self) -> bool:
        return any(
            [
                self.temporal_jitter_frames > 0,
                self.time_mask_prob > 0 and self.time_mask_max_frames > 0,
                self.pose_noise_std > 0,
                self.kinematic_noise_std > 0,
                self.confidence_dropout_prob > 0,
            ]
        )


def sample_window_bounds(
    *,
    start: int,
    end: int,
    total_frames: int,
    jitter_frames: int,
    rng: np.random.Generator,
) -> tuple[int, int]:
    if jitter_frames <= 0 or total_frames <= 0:
        return start, end
    max_left = min(jitter_frames, start)
    max_right = min(jitter_frames, max(0, total_frames - end))
    if max_left <= 0 and max_right <= 0:
        return start, end
    shift = int(rng.integers(-max_left, max_right + 1))
    return start + shift, end + shift


def apply_pose_window_augmentation(
    *,
    poses: np.ndarray,
    kinematics: np.ndarray,
    scene_features: np.ndarray,
    config: PoseAugmentationConfig,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not config.enabled():
        return poses, kinematics, scene_features

    aug_poses = poses.astype(np.float32, copy=True)
    aug_kinematics = kinematics.astype(np.float32, copy=True)
    aug_scene = scene_features.astype(np.float32, copy=True)

    if config.pose_noise_std > 0:
        pose_noise = rng.normal(
            loc=0.0,
            scale=config.pose_noise_std,
            size=aug_poses[:, :, :2].shape,
        ).astype(np.float32)
        aug_poses[:, :, :2] += pose_noise

    if config.confidence_dropout_prob > 0 and aug_poses.shape[-1] >= 3:
        keep_mask = (
            rng.random(size=aug_poses[:, :, 2].shape) >= config.confidence_dropout_prob
        ).astype(np.float32)
        aug_poses[:, :, 2] *= keep_mask

    if config.kinematic_noise_std > 0:
        aug_kinematics += rng.normal(
            loc=0.0,
            scale=config.kinematic_noise_std,
            size=aug_kinematics.shape,
        ).astype(np.float32)

    if config.time_mask_prob > 0 and config.time_mask_max_frames > 0 and len(aug_poses) > 1:
        if float(rng.random()) < config.time_mask_prob:
            mask_len = int(
                rng.integers(
                    1,
                    min(config.time_mask_max_frames, len(aug_poses)) + 1,
                )
            )
            mask_start = int(rng.integers(0, len(aug_poses) - mask_len + 1))
            mask_end = mask_start + mask_len
            aug_poses[mask_start:mask_end] = 0.0
            aug_kinematics[mask_start:mask_end] = 0.0
            aug_scene[mask_start:mask_end] = 0.0

    return aug_poses, aug_kinematics, aug_scene
