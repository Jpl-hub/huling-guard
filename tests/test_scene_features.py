import numpy as np

from huling_guard.contracts import ScenePrior, SceneRegion
from huling_guard.features.scene import build_scene_relation_features


def _frame(x: float, y: float) -> np.ndarray:
    keypoints = np.zeros((17, 3), dtype=np.float32)
    keypoints[:, 2] = 1.0
    keypoints[5, :2] = [x, y - 0.1]
    keypoints[6, :2] = [x, y - 0.1]
    keypoints[11, :2] = [x, y]
    keypoints[12, :2] = [x, y]
    keypoints[15, :2] = [x, y + 0.05]
    keypoints[16, :2] = [x, y + 0.05]
    return keypoints


def test_scene_relation_support_flags() -> None:
    prior = ScenePrior(
        frame_width=1920,
        frame_height=1080,
        regions=(
            SceneRegion(label="floor", bbox=(0.0, 0.7, 1.0, 1.0), score=1.0),
            SceneRegion(label="bed", bbox=(0.05, 0.55, 0.4, 0.95), score=0.9),
            SceneRegion(label="table", bbox=(0.7, 0.4, 0.9, 0.8), score=0.8),
        ),
    )
    clip = np.stack([_frame(0.2, 0.7), _frame(0.8, 0.55)], axis=0)
    features = build_scene_relation_features(clip, prior)

    assert features.shape == (2, 8)
    assert features[0, 0] > 0.0
    assert features[0, 1] > 0.0
    assert features[1, 7] < 0.2


def test_scene_relation_support_flags_with_pixel_prior_and_normalized_keypoints() -> None:
    prior = ScenePrior(
        frame_width=1920,
        frame_height=1080,
        regions=(
            SceneRegion(label="floor", bbox=(0.0, 756.0, 1920.0, 1080.0), score=1.0),
            SceneRegion(label="bed", bbox=(96.0, 594.0, 768.0, 1026.0), score=0.9),
            SceneRegion(label="table", bbox=(1344.0, 432.0, 1728.0, 864.0), score=0.8),
        ),
    )
    clip = np.stack([_frame(0.2, 0.7), _frame(0.8, 0.55)], axis=0)

    features = build_scene_relation_features(clip, prior)

    assert features.shape == (2, 8)
    assert features[0, 0] > 0.0
    assert features[0, 1] > 0.0
    assert features[1, 7] < 0.2
