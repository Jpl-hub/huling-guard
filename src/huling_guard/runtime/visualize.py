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


def draw_pose_overlay(frame: np.ndarray, keypoints: np.ndarray, score_threshold: float) -> None:
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
    if isinstance(snapshot, PipelineSnapshot):
        predicted_state = snapshot.predicted_state or "warming_up"
        confidence = float(snapshot.confidence)
        risk_score = float(snapshot.risk_score)
        ready = bool(snapshot.ready)
        window_span_seconds = float(snapshot.window_span_seconds)
        incidents = [incident.kind for incident in snapshot.incidents]
    else:
        predicted_state = str(snapshot.get("predicted_state") or "warming_up")
        confidence = float(snapshot.get("confidence") or 0.0)
        risk_score = float(snapshot.get("risk_score") or 0.0)
        ready = bool(snapshot.get("ready"))
        window_span_seconds = float(snapshot.get("window_span_seconds") or 0.0)
        incidents_payload = snapshot.get("incidents") or []
        incidents = [
            str(item.get("kind"))
            for item in incidents_payload
            if isinstance(item, Mapping) and item.get("kind")
        ]

    lines = [
        f"ready: {ready}",
        f"state: {predicted_state}",
        f"confidence: {confidence:.3f}",
        f"risk: {risk_score:.3f}",
        f"window_span: {window_span_seconds:.2f}s",
    ]
    if incidents:
        lines.append("incidents: " + ", ".join(incidents))
    for index, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (16, 28 + index * 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
