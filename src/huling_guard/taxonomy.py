from __future__ import annotations

import re

INTERNAL_STATES = (
    "normal",
    "near_fall",
    "fall",
    "recovery",
    "prolonged_lying",
)

STATE_TO_INDEX = {state: idx for idx, state in enumerate(INTERNAL_STATES)}

_PROLONGED_LYING_HINTS = (
    "fallen",
    "lying",
    "long_lie",
    "longlie",
    "remain_down",
    "prolonged_lying",
    "lying_after_fall",
    "still_lying",
)
_RECOVERY_HINTS = ("recover", "recovery", "get_up", "stand_up", "rise_up")
_NEAR_FALL_HINTS = (
    "near_fall",
    "nearfall",
    "almost_fall",
    "stumble",
    "trip",
    "slip",
    "imbalance",
    "loss_of_balance",
)
_FALL_HINTS = ("fall", "collapse", "slump", "drop")


def canonicalize_label(label: str) -> str:
    lowered = label.strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")


def map_external_label(label: str) -> str:
    normalized = canonicalize_label(label)
    if any(token in normalized for token in _PROLONGED_LYING_HINTS):
        return "prolonged_lying"
    if any(token in normalized for token in _RECOVERY_HINTS):
        return "recovery"
    if any(token in normalized for token in _NEAR_FALL_HINTS):
        return "near_fall"
    if any(token in normalized for token in _FALL_HINTS):
        return "fall"
    return "normal"


def risk_target_for_state(state: str) -> float:
    return 0.0 if state == "normal" else 1.0
