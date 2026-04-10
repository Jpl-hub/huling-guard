import numpy as np

from huling_guard.features import build_kinematic_features, get_kinematic_feature_dim


def _build_motion_clip(num_frames: int) -> np.ndarray:
    clip = np.zeros((num_frames, 17, 3), dtype=np.float32)
    clip[:, :, 2] = 1.0
    for frame_idx in range(num_frames):
        x = 0.3 + frame_idx * 0.02
        y = 0.7 - frame_idx * 0.03
        clip[frame_idx, 5, :2] = [x - 0.04, y - 0.2]
        clip[frame_idx, 6, :2] = [x + 0.04, y - 0.18]
        clip[frame_idx, 11, :2] = [x - 0.03, y]
        clip[frame_idx, 12, :2] = [x + 0.03, y + 0.01]
        clip[frame_idx, 15, :2] = [x - 0.02, y + 0.22]
        clip[frame_idx, 16, :2] = [x + 0.02, y + 0.24]
    return clip


def test_get_kinematic_feature_dim_resolves_known_sets() -> None:
    assert get_kinematic_feature_dim("v1") == 8
    assert get_kinematic_feature_dim("v2") == 12


def test_build_kinematic_features_v2_adds_directional_motion_terms() -> None:
    clip = _build_motion_clip(6)

    features_v1 = build_kinematic_features(clip, feature_set="v1")
    features_v2 = build_kinematic_features(clip, feature_set="v2")

    assert features_v1.shape == (6, 8)
    assert features_v2.shape == (6, 12)
    np.testing.assert_allclose(features_v2[:, :8], features_v1, atol=1e-6)
    assert np.any(np.abs(features_v2[1:, 8:]) > 0.0)


def test_build_kinematic_features_v2_clamps_degenerate_motion_scale() -> None:
    clip = np.zeros((4, 17, 3), dtype=np.float32)
    clip[:, :, 2] = 1.0
    clip[:, 11, :2] = [0.5, 0.5]
    clip[:, 12, :2] = [0.5, 0.5]
    clip[:, 5, :2] = [0.5, 0.5]
    clip[:, 6, :2] = [0.5, 0.5]
    clip[:, 15, :2] = [[0.4, 0.9], [0.7, 0.3], [0.2, 0.8], [0.8, 0.2]]
    clip[:, 16, :2] = [[0.6, 0.9], [0.9, 0.3], [0.4, 0.8], [1.0, 0.2]]

    features_v2 = build_kinematic_features(clip, feature_set="v2")

    assert np.max(np.abs(features_v2[:, 8:11])) <= 12.0
    assert np.max(np.abs(features_v2[:, 11])) <= 2.0
