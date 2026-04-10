from __future__ import annotations

import math

import numpy as np

LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_ANKLE = 15
RIGHT_ANKLE = 16
DEFAULT_KINEMATIC_FEATURE_SET = "v1"
KINEMATIC_FEATURE_DIMS = {
    "v1": 8,
    "v2": 12,
}


def _midpoint(points: np.ndarray, left_idx: int, right_idx: int) -> np.ndarray:
    return (points[:, left_idx, :2] + points[:, right_idx, :2]) / 2.0


def _safe_norm(values: np.ndarray, axis: int = -1) -> np.ndarray:
    return np.linalg.norm(values, axis=axis) + 1e-6


def _stabilize_motion_scale(scale: np.ndarray, minimum: float = 0.05) -> np.ndarray:
    return np.maximum(scale, minimum).astype(np.float32)


def resolve_kinematic_feature_set(feature_set: str | None) -> str:
    if feature_set is None:
        return DEFAULT_KINEMATIC_FEATURE_SET
    normalized = str(feature_set).strip().lower()
    if not normalized:
        return DEFAULT_KINEMATIC_FEATURE_SET
    if normalized not in KINEMATIC_FEATURE_DIMS:
        raise ValueError(
            f"unsupported kinematic feature set: {feature_set!r}; "
            f"expected one of {sorted(KINEMATIC_FEATURE_DIMS)}"
        )
    return normalized


def get_kinematic_feature_dim(feature_set: str | None) -> int:
    return KINEMATIC_FEATURE_DIMS[resolve_kinematic_feature_set(feature_set)]


def normalize_pose_sequence(keypoints: np.ndarray) -> np.ndarray:
    keypoints = np.asarray(keypoints, dtype=np.float32)
    normalized = keypoints.copy()
    hip_center = _midpoint(normalized, LEFT_HIP, RIGHT_HIP)
    torso_center = _midpoint(normalized, LEFT_SHOULDER, RIGHT_SHOULDER)
    scale = _safe_norm(torso_center - hip_center)
    normalized[:, :, :2] -= hip_center[:, None, :]
    normalized[:, :, :2] /= scale[:, None, None]
    return normalized


def body_tilt_degrees(keypoints: np.ndarray) -> np.ndarray:
    hip_center = _midpoint(keypoints, LEFT_HIP, RIGHT_HIP)
    torso_center = _midpoint(keypoints, LEFT_SHOULDER, RIGHT_SHOULDER)
    vector = torso_center - hip_center
    angles = np.degrees(np.arctan2(vector[:, 0], np.abs(vector[:, 1]) + 1e-6))
    return angles.astype(np.float32)


def center_of_mass(keypoints: np.ndarray) -> np.ndarray:
    coords = keypoints[:, :, :2]
    confidence = np.clip(keypoints[:, :, 2:3], 0.0, 1.0)
    weighted_sum = (coords * confidence).sum(axis=1)
    denom = np.maximum(confidence.sum(axis=1), 1e-6)
    return (weighted_sum / denom).astype(np.float32)


def build_kinematic_features(
    keypoints: np.ndarray,
    *,
    feature_set: str | None = None,
) -> np.ndarray:
    normalized_feature_set = resolve_kinematic_feature_set(feature_set)
    keypoints = np.asarray(keypoints, dtype=np.float32)
    com = center_of_mass(keypoints)
    hip_center = _midpoint(keypoints, LEFT_HIP, RIGHT_HIP)
    shoulders = _midpoint(keypoints, LEFT_SHOULDER, RIGHT_SHOULDER)

    com_delta = np.diff(com, axis=0, prepend=com[:1])
    com_speed = _safe_norm(com_delta)
    com_accel = np.diff(com_speed, axis=0, prepend=com_speed[:1])
    torso_length = _safe_norm(shoulders - hip_center)
    body_width = _safe_norm(
        keypoints[:, LEFT_SHOULDER, :2] - keypoints[:, RIGHT_SHOULDER, :2]
    )
    ankle_span = _safe_norm(keypoints[:, LEFT_ANKLE, :2] - keypoints[:, RIGHT_ANKLE, :2])
    tilt = body_tilt_degrees(keypoints) / 90.0

    base_features = [
        com[:, 0],
        com[:, 1],
        hip_center[:, 1],
        tilt,
        com_speed,
        com_accel,
        body_width / torso_length,
        ankle_span / torso_length,
    ]
    if normalized_feature_set == "v1":
        return np.stack(base_features, axis=-1).astype(np.float32)

    hip_delta_y = np.diff(hip_center[:, 1], axis=0, prepend=hip_center[:1, 1])
    tilt_delta = np.diff(tilt, axis=0, prepend=tilt[:1])
    motion_scale = _stabilize_motion_scale(torso_length)
    enhanced_features = np.stack(
        [
            *base_features,
            np.clip(com_delta[:, 0] / motion_scale, -12.0, 12.0),
            np.clip(com_delta[:, 1] / motion_scale, -12.0, 12.0),
            np.clip(hip_delta_y / motion_scale, -12.0, 12.0),
            np.clip(tilt_delta, -2.0, 2.0),
        ],
        axis=-1,
    )
    return enhanced_features.astype(np.float32)
