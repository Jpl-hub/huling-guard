from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from huling_guard.events import EventEngine
from huling_guard.runtime.pipeline import RealtimePipeline
from huling_guard.taxonomy import INTERNAL_STATES


class _DummyModel(torch.nn.Module):
    def forward(self, poses, kinematics, scene_features, padding_mask):  # type: ignore[override]
        batch = poses.shape[0]
        return {
            "clip_logits": torch.zeros((batch, len(INTERNAL_STATES)), dtype=torch.float32, device=poses.device),
            "risk_logits": torch.zeros((batch,), dtype=torch.float32, device=poses.device),
        }


def _build_pose(confidence: float) -> np.ndarray:
    keypoints = np.zeros((17, 3), dtype=np.float32)
    keypoints[:, 0] = np.linspace(0.2, 0.8, 17, dtype=np.float32)
    keypoints[:, 1] = np.linspace(0.1, 0.9, 17, dtype=np.float32)
    keypoints[:, 2] = confidence
    return keypoints


def test_realtime_pipeline_exposes_pose_quality_before_window_is_ready() -> None:
    pipeline = RealtimePipeline(
        model=_DummyModel(),
        scene_prior=None,
        event_engine=EventEngine(),
        device="cpu",
        window_size=8,
        inference_stride=2,
    )

    snapshot = pipeline.push_pose(_build_pose(0.85), timestamp=0.0)

    assert snapshot.ready is False
    assert snapshot.pose_quality_score > 0.0
    assert snapshot.mean_keypoint_confidence == 0.85
    assert snapshot.visible_joint_ratio == 1.0


def test_realtime_pipeline_lowers_pose_quality_for_low_confidence_window() -> None:
    pipeline = RealtimePipeline(
        model=_DummyModel(),
        scene_prior=None,
        event_engine=EventEngine(),
        device="cpu",
        window_size=4,
        inference_stride=1,
    )

    for index in range(4):
        snapshot = pipeline.push_pose(_build_pose(0.1), timestamp=float(index))

    assert snapshot.ready is True
    assert snapshot.mean_keypoint_confidence == 0.1
    assert snapshot.visible_joint_ratio == 0.0
    assert snapshot.pose_quality_score < 0.2
