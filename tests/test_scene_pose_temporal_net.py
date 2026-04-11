from __future__ import annotations

import pytest

torch = pytest.importorskip('torch')

from huling_guard.model.scene_pose_temporal_net import ScenePoseTemporalNet


def _build_pose_window(batch_size: int, window_size: int, confidence: float) -> torch.Tensor:
    poses = torch.zeros((batch_size, window_size, 17, 3), dtype=torch.float32)
    poses[..., 0] = torch.linspace(0.1, 0.9, 17, dtype=torch.float32)
    poses[..., 1] = torch.linspace(0.2, 0.8, 17, dtype=torch.float32)
    poses[..., 2] = confidence
    return poses


def test_scene_pose_temporal_net_emits_quality_outputs_and_expected_shapes() -> None:
    model = ScenePoseTemporalNet(
        kinematic_dim=12,
        scene_dim=8,
        hidden_dim=48,
        num_heads=4,
        depth=2,
        dropout=0.0,
        num_classes=5,
    )
    poses = _build_pose_window(batch_size=2, window_size=6, confidence=0.8)
    kinematics = torch.zeros((2, 6, 12), dtype=torch.float32)
    scene_features = torch.zeros((2, 6, 8), dtype=torch.float32)
    padding_mask = torch.zeros((2, 6), dtype=torch.bool)

    outputs = model(
        poses=poses,
        kinematics=kinematics,
        scene_features=scene_features,
        padding_mask=padding_mask,
    )

    assert outputs['frame_logits'].shape == (2, 6, 5)
    assert outputs['clip_logits'].shape == (2, 5)
    assert outputs['risk_logits'].shape == (2,)
    assert outputs['embedding'].shape == (2, 48)
    assert outputs['frame_quality'].shape == (2, 6)
    assert outputs['frame_quality_prior'].shape == (2, 6)
    assert outputs['frame_quality_logits'].shape == (2, 6)
    assert torch.all(outputs['frame_quality'] > 0.0)
    assert torch.all(outputs['frame_quality'] <= 1.0)


def test_scene_pose_temporal_net_assigns_lower_quality_to_low_confidence_frames() -> None:
    model = ScenePoseTemporalNet(
        kinematic_dim=12,
        scene_dim=8,
        hidden_dim=48,
        num_heads=4,
        depth=2,
        dropout=0.0,
        num_classes=5,
    )
    high_conf = _build_pose_window(batch_size=1, window_size=6, confidence=0.9)
    low_conf = _build_pose_window(batch_size=1, window_size=6, confidence=0.1)
    poses = torch.cat([high_conf, low_conf], dim=0)
    kinematics = torch.zeros((2, 6, 12), dtype=torch.float32)
    scene_features = torch.zeros((2, 6, 8), dtype=torch.float32)
    padding_mask = torch.zeros((2, 6), dtype=torch.bool)

    outputs = model(
        poses=poses,
        kinematics=kinematics,
        scene_features=scene_features,
        padding_mask=padding_mask,
    )

    high_quality = outputs['frame_quality'][0].mean().item()
    low_quality = outputs['frame_quality'][1].mean().item()
    assert high_quality > low_quality
