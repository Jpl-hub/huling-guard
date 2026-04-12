from __future__ import annotations

from collections.abc import Mapping

import cv2
import numpy as np

from huling_guard.runtime.pipeline import PipelineSnapshot

COCO_SKELETON = (
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 6),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
)


def _draw_keypoint_bbox(frame: np.ndarray, keypoints: np.ndarray, score_threshold: float) -> None:
    if keypoints.ndim != 2 or keypoints.shape[1] < 3:
        return
    visible_points = keypoints[keypoints[:, 2] >= score_threshold][:, :2]
    if visible_points.shape[0] < 3:
        return

    frame_height, frame_width = frame.shape[:2]
    x_min, y_min = np.min(visible_points, axis=0)
    x_max, y_max = np.max(visible_points, axis=0)
    padding = 8
    left = max(0, int(round(x_min)) - padding)
    top = max(0, int(round(y_min)) - padding)
    right = min(frame_width - 1, int(round(x_max)) + padding)
    bottom = min(frame_height - 1, int(round(y_max)) + padding)
    if right <= left or bottom <= top:
        return

    box_color = (80, 220, 255)
    cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
    label = "RTMO pose"
    label_origin = (left, max(18, top - 8))
    cv2.putText(
        frame,
        label,
        label_origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        box_color,
        2,
        cv2.LINE_AA,
    )


def draw_pose_overlay(frame: np.ndarray, keypoints: np.ndarray, score_threshold: float) -> None:
    _draw_keypoint_bbox(frame, keypoints, score_threshold)
    for start, end in COCO_SKELETON:
        p1 = keypoints[start]
        p2 = keypoints[end]
        if float(p1[2]) < score_threshold or float(p2[2]) < score_threshold:
            continue
        cv2.line(
            frame,
            (int(p1[0]), int(p1[1])),
            (int(p2[0]), int(p2[1])),
            (0, 220, 255),
            2,
        )
    for point in keypoints:
        if float(point[2]) < score_threshold:
            continue
        cv2.circle(frame, (int(point[0]), int(point[1])), 3, (40, 220, 40), -1)


def annotate_snapshot_overlay(frame: np.ndarray, snapshot: PipelineSnapshot | Mapping[str, object]) -> None:
    return
