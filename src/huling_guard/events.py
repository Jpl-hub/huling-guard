from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from huling_guard.taxonomy import INTERNAL_STATES


@dataclass(slots=True)
class EventThresholds:
    near_fall_threshold: float = 0.55
    fall_threshold: float = 0.7
    recovery_threshold: float = 0.55
    prolonged_lying_threshold: float = 0.6
    prolonged_lying_seconds: float = 15.0
    warning_cooldown_seconds: float = 8.0
    fall_confirm_hits: int = 2


@dataclass(slots=True)
class Incident:
    kind: str
    timestamp: float
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "payload": self.payload,
        }


class EventEngine:
    def __init__(self, thresholds: EventThresholds | None = None) -> None:
        self.thresholds = thresholds or EventThresholds()
        self._last_warning_ts = -1e9
        self._fall_candidate_hits = 0
        self._fall_started_at: float | None = None
        self._fall_confirmed = False
        self._long_lie_emitted = False

    def reset(self) -> None:
        self._last_warning_ts = -1e9
        self._fall_candidate_hits = 0
        self._fall_started_at = None
        self._fall_confirmed = False
        self._long_lie_emitted = False

    def _normalize_probs(self, state_probs: dict[str, float] | np.ndarray) -> dict[str, float]:
        if isinstance(state_probs, dict):
            return {key: float(value) for key, value in state_probs.items()}
        if len(state_probs) != len(INTERNAL_STATES):
            raise ValueError("state_probs size does not match INTERNAL_STATES")
        return {
            state: float(state_probs[idx])
            for idx, state in enumerate(INTERNAL_STATES)
        }

    def update(self, timestamp: float, state_probs: dict[str, float] | np.ndarray) -> list[Incident]:
        probs = self._normalize_probs(state_probs)
        incidents: list[Incident] = []

        if (
            probs["near_fall"] >= self.thresholds.near_fall_threshold
            and timestamp - self._last_warning_ts >= self.thresholds.warning_cooldown_seconds
        ):
            incidents.append(
                Incident(
                    kind="near_fall_warning",
                    timestamp=timestamp,
                    confidence=probs["near_fall"],
                    payload={"state_probs": probs},
                )
            )
            self._last_warning_ts = timestamp

        if probs["fall"] >= self.thresholds.fall_threshold:
            self._fall_candidate_hits += 1
            if self._fall_started_at is None:
                self._fall_started_at = timestamp
        else:
            self._fall_candidate_hits = 0

        if (
            not self._fall_confirmed
            and self._fall_candidate_hits >= self.thresholds.fall_confirm_hits
            and self._fall_started_at is not None
        ):
            self._fall_confirmed = True
            incidents.append(
                Incident(
                    kind="confirmed_fall",
                    timestamp=timestamp,
                    confidence=probs["fall"],
                    payload={"state_probs": probs},
                )
            )

        if self._fall_confirmed and self._fall_started_at is not None:
            if (
                probs["prolonged_lying"] >= self.thresholds.prolonged_lying_threshold
                and not self._long_lie_emitted
                and timestamp - self._fall_started_at >= self.thresholds.prolonged_lying_seconds
            ):
                incidents.append(
                    Incident(
                        kind="prolonged_lying",
                        timestamp=timestamp,
                        confidence=probs["prolonged_lying"],
                        payload={"fall_started_at": self._fall_started_at, "state_probs": probs},
                    )
                )
                self._long_lie_emitted = True

            if probs["recovery"] >= self.thresholds.recovery_threshold:
                incidents.append(
                    Incident(
                        kind="recovery",
                        timestamp=timestamp,
                        confidence=probs["recovery"],
                        payload={"state_probs": probs},
                    )
                )
                self.reset()

        return incidents
