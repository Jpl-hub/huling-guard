from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

from huling_guard.contracts import ScenePrior
from huling_guard.events import EventEngine, Incident
from huling_guard.features import (
    build_kinematic_features,
    build_scene_relation_features,
    normalize_pose_sequence,
)
from huling_guard.taxonomy import INTERNAL_STATES


@dataclass(slots=True)
class PipelineSnapshot:
    timestamp: float
    ready: bool
    observed_frames: int
    window_size: int
    window_span_seconds: float
    state_probs: dict[str, float] = field(default_factory=dict)
    predicted_state: str | None = None
    confidence: float = 0.0
    risk_score: float = 0.0
    incidents: list[Incident] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "ready": self.ready,
            "observed_frames": self.observed_frames,
            "window_size": self.window_size,
            "window_span_seconds": self.window_span_seconds,
            "state_probs": self.state_probs,
            "predicted_state": self.predicted_state,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "incidents": [incident.to_dict() for incident in self.incidents],
        }


class RealtimePipeline:
    def __init__(
        self,
        model: torch.nn.Module,
        scene_prior: ScenePrior | None,
        event_engine: EventEngine,
        device: str = "cuda",
        window_size: int = 64,
        inference_stride: int = 4,
        kinematic_feature_set: str = "v1",
    ) -> None:
        self.model = model.to(device)
        self.model.eval()
        self.scene_prior = scene_prior
        self.event_engine = event_engine
        self.device = torch.device(device)
        self.window_size = window_size
        self.inference_stride = inference_stride
        self.kinematic_feature_set = kinematic_feature_set
        self._timestamps: deque[float] = deque(maxlen=window_size)
        self._poses: deque[np.ndarray] = deque(maxlen=window_size)
        self._steps = 0

    def reset(self) -> None:
        self._timestamps.clear()
        self._poses.clear()
        self._steps = 0
        self.event_engine.reset()

    def _window_span_seconds(self) -> float:
        if len(self._timestamps) < 2:
            return 0.0
        return float(self._timestamps[-1] - self._timestamps[0])

    def push_pose(self, keypoints: np.ndarray, timestamp: float) -> PipelineSnapshot:
        self._poses.append(np.asarray(keypoints, dtype=np.float32))
        self._timestamps.append(float(timestamp))
        self._steps += 1

        if len(self._poses) < self.window_size:
            return PipelineSnapshot(
                timestamp=timestamp,
                ready=False,
                observed_frames=len(self._poses),
                window_size=self.window_size,
                window_span_seconds=self._window_span_seconds(),
            )
        if self._steps % self.inference_stride != 0:
            return PipelineSnapshot(
                timestamp=timestamp,
                ready=False,
                observed_frames=len(self._poses),
                window_size=self.window_size,
                window_span_seconds=self._window_span_seconds(),
            )

        pose_window = np.stack(tuple(self._poses), axis=0)
        normalized_pose = normalize_pose_sequence(pose_window)
        kinematics = build_kinematic_features(
            pose_window,
            feature_set=self.kinematic_feature_set,
        )
        scene_features = build_scene_relation_features(pose_window, self.scene_prior)
        padding_mask = np.zeros((1, self.window_size), dtype=bool)

        with torch.no_grad():
            outputs = self.model(
                poses=torch.from_numpy(normalized_pose).unsqueeze(0).to(self.device),
                kinematics=torch.from_numpy(kinematics).unsqueeze(0).to(self.device),
                scene_features=torch.from_numpy(scene_features).unsqueeze(0).to(self.device),
                padding_mask=torch.from_numpy(padding_mask).to(self.device),
            )
            state_probs = torch.softmax(outputs["clip_logits"], dim=-1)[0].cpu().numpy()
            risk_score = float(torch.sigmoid(outputs["risk_logits"])[0].cpu().item())

        state_payload = {
            state: float(state_probs[idx])
            for idx, state in enumerate(INTERNAL_STATES)
        }
        predicted_idx = int(np.argmax(state_probs))
        incidents = self.event_engine.update(timestamp=timestamp, state_probs=state_payload)
        return PipelineSnapshot(
            timestamp=timestamp,
            ready=True,
            observed_frames=len(self._poses),
            window_size=self.window_size,
            window_span_seconds=self._window_span_seconds(),
            state_probs=state_payload,
            predicted_state=INTERNAL_STATES[predicted_idx],
            confidence=float(state_probs[predicted_idx]),
            risk_score=risk_score,
            incidents=incidents,
        )
