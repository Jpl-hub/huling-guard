import numpy as np

from huling_guard.data.augmentation import (
    PoseAugmentationConfig,
    apply_pose_window_augmentation,
    sample_window_bounds,
)


def test_sample_window_bounds_stays_within_sample() -> None:
    rng = np.random.default_rng(2026)
    start, end = sample_window_bounds(
        start=10,
        end=20,
        total_frames=24,
        jitter_frames=8,
        rng=rng,
    )

    assert 0 <= start < end <= 24
    assert end - start == 10


def test_apply_pose_window_augmentation_masks_and_perturbs() -> None:
    config = PoseAugmentationConfig(
        time_mask_prob=1.0,
        time_mask_max_frames=3,
        pose_noise_std=0.05,
        kinematic_noise_std=0.03,
        confidence_dropout_prob=0.5,
    )
    rng = np.random.default_rng(42)
    poses = np.ones((8, 17, 3), dtype=np.float32)
    kinematics = np.ones((8, 12), dtype=np.float32)
    scene_features = np.ones((8, 8), dtype=np.float32)

    aug_poses, aug_kinematics, aug_scene = apply_pose_window_augmentation(
        poses=poses,
        kinematics=kinematics,
        scene_features=scene_features,
        config=config,
        rng=rng,
    )

    assert aug_poses.shape == poses.shape
    assert aug_kinematics.shape == kinematics.shape
    assert aug_scene.shape == scene_features.shape
    assert not np.array_equal(aug_poses, poses)
    assert not np.array_equal(aug_kinematics, kinematics)
    assert np.any(aug_poses[:, :, 2] == 0.0)
    assert np.any(np.all(aug_scene == 0.0, axis=1))
