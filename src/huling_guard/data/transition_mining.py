from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from huling_guard.data.pose_io import load_pose_archive, normalize_pose_archive_coords
from huling_guard.features.geometry import LEFT_HIP, RIGHT_HIP, body_tilt_degrees


@dataclass(slots=True, frozen=True)
class TransitionMiningConfig:
    include_labels: tuple[str, ...] = ("fall", "prolonged_lying")
    source: str = "auto_transition_miner:v1"
    min_frames: int = 16
    min_pose_confidence: float = 0.2
    near_fall_lead_seconds: float = 0.9
    near_fall_tail_gap_seconds: float = 0.12
    near_fall_min_seconds: float = 0.35
    min_drop_delta: float = 0.08
    min_downward_velocity: float = 0.05
    recovery_window_seconds: float = 1.2
    recovery_min_seconds: float = 0.35
    min_recovery_lift: float = 0.06


def _midpoint(points: np.ndarray, left_idx: int, right_idx: int) -> np.ndarray:
    return (points[:, left_idx, :2] + points[:, right_idx, :2]) / 2.0


def _moving_average(values: np.ndarray, window: int = 5) -> np.ndarray:
    if window <= 1 or values.size <= 2:
        return values.astype(np.float32, copy=False)
    radius = max(1, window // 2)
    padded = np.pad(values.astype(np.float32), (radius, radius), mode="edge")
    kernel = np.full(radius * 2 + 1, 1.0 / (radius * 2 + 1), dtype=np.float32)
    return np.convolve(padded, kernel, mode="valid").astype(np.float32)


def _resolve_timestamps(payload: dict[str, object], num_frames: int) -> np.ndarray:
    raw_timestamps = payload.get("timestamps")
    if raw_timestamps is not None:
        timestamps = np.asarray(raw_timestamps, dtype=np.float32).reshape(-1)
        if timestamps.size == num_frames:
            return timestamps

    fps = float(np.asarray(payload.get("fps", 30.0)).reshape(-1)[0])
    if fps <= 1e-6:
        fps = 30.0
    return (np.arange(num_frames, dtype=np.float32) / fps).astype(np.float32)


def _safe_scale(values: np.ndarray, minimum: float) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return minimum
    percentile = float(np.percentile(finite, 95))
    return max(minimum, percentile)


def mine_transition_intervals(
    *,
    sample_id: str,
    internal_label: str,
    keypoints: np.ndarray,
    timestamps: np.ndarray,
    config: TransitionMiningConfig,
) -> list[dict[str, object]]:
    if internal_label not in config.include_labels:
        return []

    keypoints = np.asarray(keypoints, dtype=np.float32)
    timestamps = np.asarray(timestamps, dtype=np.float32).reshape(-1)
    num_frames = int(keypoints.shape[0])
    if num_frames < config.min_frames or timestamps.size != num_frames:
        return []

    pose_quality = _moving_average(np.clip(keypoints[:, :, 2], 0.0, 1.0).mean(axis=1))
    valid_mask = pose_quality >= config.min_pose_confidence
    if int(valid_mask.sum()) < max(6, num_frames // 3):
        return []

    hip_y = _moving_average(_midpoint(keypoints, LEFT_HIP, RIGHT_HIP)[:, 1])
    tilt = _moving_average(np.abs(body_tilt_degrees(keypoints)) / 90.0)

    dt = np.diff(timestamps, prepend=timestamps[:1])
    positive_dt = dt[dt > 1e-6]
    fallback_dt = float(np.median(positive_dt)) if positive_dt.size else (1.0 / 30.0)
    dt = np.where(dt > 1e-6, dt, fallback_dt)
    hip_velocity = _moving_average(np.diff(hip_y, prepend=hip_y[:1]) / dt)

    baseline_count = min(max(4, num_frames // 5), 12)
    baseline_y = float(np.median(hip_y[:baseline_count]))
    baseline_tilt = float(np.median(tilt[:baseline_count]))

    downward = np.clip(hip_velocity, 0.0, None)
    drop = np.clip(hip_y - baseline_y, 0.0, None)
    tilt_delta = np.clip(tilt - baseline_tilt, 0.0, None)

    score = (
        0.5 * (downward / _safe_scale(downward, config.min_downward_velocity))
        + 0.35 * (drop / _safe_scale(drop, config.min_drop_delta))
        + 0.15 * (tilt_delta / _safe_scale(tilt_delta, 0.08))
    )
    score = np.where(valid_mask, score, 0.0)
    score[:1] = 0.0
    score[-1:] = 0.0

    anchor_idx = int(np.argmax(score))
    anchor_time = float(timestamps[anchor_idx])
    anchor_drop = float(drop[anchor_idx])
    anchor_downward = float(downward[anchor_idx])
    if anchor_drop < config.min_drop_delta or anchor_downward < config.min_downward_velocity:
        return []

    intervals: list[dict[str, object]] = []

    near_start_time = max(float(timestamps[0]), anchor_time - config.near_fall_lead_seconds)
    near_end_time = min(float(timestamps[-1]), anchor_time - config.near_fall_tail_gap_seconds)
    if near_end_time - near_start_time >= config.near_fall_min_seconds:
        intervals.append(
            {
                "sample_id": sample_id,
                "label": "near_fall",
                "start_time": round(float(near_start_time), 4),
                "end_time": round(float(near_end_time), 4),
                "source": config.source,
                "metadata": {
                    "anchor_index": anchor_idx,
                    "anchor_time": round(anchor_time, 4),
                    "anchor_score": round(float(score[anchor_idx]), 4),
                    "anchor_drop": round(anchor_drop, 4),
                },
            }
        )

    low_idx = int(np.argmax(hip_y[anchor_idx:]) + anchor_idx)
    if low_idx < num_frames - 3:
        tail_count = max(3, num_frames // 6)
        tail_start = max(low_idx + 1, num_frames - tail_count)
        tail_y = float(np.median(hip_y[tail_start:]))
        recovery_lift = float(hip_y[low_idx] - tail_y)
        if recovery_lift >= config.min_recovery_lift:
            upward = np.clip(-hip_velocity, 0.0, None)
            upward_candidates = np.where(
                (np.arange(num_frames) > low_idx)
                & (upward >= max(0.03, float(np.percentile(upward, 75)) if upward.size else 0.03))
                & valid_mask
            )[0]
            recovery_start_idx = int(upward_candidates[0]) if upward_candidates.size else low_idx + 1
            recovery_start_time = float(timestamps[recovery_start_idx])
            recovery_end_time = min(float(timestamps[-1]), recovery_start_time + config.recovery_window_seconds)
            if recovery_end_time - recovery_start_time < config.recovery_min_seconds:
                recovery_end_time = float(timestamps[-1])
            if recovery_end_time - recovery_start_time >= config.recovery_min_seconds:
                intervals.append(
                    {
                        "sample_id": sample_id,
                        "label": "recovery",
                        "start_time": round(recovery_start_time, 4),
                        "end_time": round(recovery_end_time, 4),
                        "source": config.source,
                        "metadata": {
                            "low_index": low_idx,
                            "low_time": round(float(timestamps[low_idx]), 4),
                            "recovery_lift": round(recovery_lift, 4),
                        },
                    }
                )

    return intervals


def mine_transition_intervals_from_entry(
    entry: dict[str, object],
    *,
    config: TransitionMiningConfig,
) -> list[dict[str, object]]:
    keypoints, payload = load_pose_archive(entry["pose_path"])
    normalized = normalize_pose_archive_coords(keypoints, payload)
    timestamps = _resolve_timestamps(payload, normalized.shape[0])
    return mine_transition_intervals(
        sample_id=str(entry["sample_id"]),
        internal_label=str(entry["internal_label"]),
        keypoints=normalized,
        timestamps=timestamps,
        config=config,
    )


def build_transition_interval_labels(
    pose_manifest_path: str | Path,
    output_path: str | Path,
    *,
    config: TransitionMiningConfig,
) -> dict[str, object]:
    pose_manifest = Path(pose_manifest_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    intervals: list[dict[str, object]] = []
    samples_scanned = 0
    eligible_samples = 0
    skipped_errors: list[dict[str, str]] = []

    with pose_manifest.open("r", encoding="utf-8") as reader:
        for line in reader:
            if not line.strip():
                continue
            entry = json.loads(line)
            samples_scanned += 1
            if str(entry.get("internal_label")) not in config.include_labels:
                continue
            eligible_samples += 1
            try:
                intervals.extend(mine_transition_intervals_from_entry(entry, config=config))
            except Exception as exc:  # pragma: no cover - summary keeps failures explicit
                skipped_errors.append(
                    {
                        "sample_id": str(entry.get("sample_id", "")),
                        "error": str(exc),
                    }
                )

    per_label: dict[str, int] = {}
    for item in intervals:
        label = str(item["label"])
        per_label[label] = per_label.get(label, 0) + 1

    payload = {
        "source": config.source,
        "samples_scanned": samples_scanned,
        "eligible_samples": eligible_samples,
        "interval_count": len(intervals),
        "per_label": per_label,
        "include_labels": list(config.include_labels),
        "skipped_errors": skipped_errors,
        "intervals": intervals,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
