from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class PoseDetection:
    track_id: int
    keypoints: np.ndarray
    score: float


class RTMOPoseEstimator:
    def __init__(
        self,
        model_name: str = "rtmo",
        device: str = "cuda:0",
    ) -> None:
        try:
            from mmpose.apis import MMPoseInferencer
        except ImportError as exc:
            raise ImportError("mmpose is required for RTMO inference") from exc

        self._inferencer = MMPoseInferencer(pose2d=model_name, device=device)

    def infer(self, frame: np.ndarray) -> list[PoseDetection]:
        result = next(self._inferencer(frame, return_vis=False))
        raw_predictions = result.get("predictions", [])
        instances = raw_predictions[0] if raw_predictions else []
        detections: list[PoseDetection] = []
        for track_id, instance in enumerate(instances):
            keypoints = np.asarray(instance["keypoints"], dtype=np.float32)
            keypoint_scores = instance.get("keypoint_scores")
            if keypoint_scores is None:
                keypoint_scores = instance.get("keypoints_visible")
            if keypoint_scores is None:
                keypoint_scores = np.ones(keypoints.shape[0], dtype=np.float32)
            scores = np.asarray(keypoint_scores, dtype=np.float32).reshape(-1, 1)
            keypoints_with_scores = np.concatenate([keypoints, scores], axis=-1)
            score = float(instance.get("bbox_score") or instance.get("score") or scores.mean())
            detections.append(
                PoseDetection(track_id=track_id, keypoints=keypoints_with_scores, score=score)
            )
        return detections

    @staticmethod
    def select_primary(detections: list[PoseDetection]) -> PoseDetection | None:
        if not detections:
            return None
        return max(detections, key=lambda item: item.score)
