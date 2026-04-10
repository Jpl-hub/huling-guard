from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def normalize_pose_coords(
    keypoints: np.ndarray,
    *,
    frame_width: float | int | np.ndarray | None,
    frame_height: float | int | np.ndarray | None,
) -> np.ndarray:
    if frame_width is None or frame_height is None:
        return np.asarray(keypoints, dtype=np.float32)
    width_value = float(np.asarray(frame_width).reshape(-1)[0])
    height_value = float(np.asarray(frame_height).reshape(-1)[0])
    if width_value <= 1.0 or height_value <= 1.0:
        return np.asarray(keypoints, dtype=np.float32)

    normalized = np.asarray(keypoints, dtype=np.float32).copy()
    normalized[..., 0] /= width_value
    normalized[..., 1] /= height_value
    return normalized


def load_pose_archive(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    loaded = np.load(Path(path), allow_pickle=False)
    if isinstance(loaded, np.ndarray):
        return loaded.astype(np.float32), {}
    payload = {key: loaded[key] for key in loaded.files}
    if "keypoints" not in payload:
        raise KeyError(f"{path} does not contain a 'keypoints' array")
    return payload["keypoints"].astype(np.float32), payload


def normalize_pose_archive_coords(keypoints: np.ndarray, payload: dict[str, Any]) -> np.ndarray:
    return normalize_pose_coords(
        keypoints,
        frame_width=payload.get("frame_width"),
        frame_height=payload.get("frame_height"),
    )
