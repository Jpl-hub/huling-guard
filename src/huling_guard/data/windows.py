from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from huling_guard.data.pose_io import load_pose_archive


@dataclass(slots=True, frozen=True)
class WindowSpec:
    window_size: int
    stride: int
    min_length: int = 32


@dataclass(slots=True, frozen=True)
class IntervalLabel:
    sample_id: str
    label: str
    start_time: float
    end_time: float
    source: str = "manual_review"


def load_interval_labels(path: str | Path) -> dict[str, list[IntervalLabel]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    intervals = payload.get("intervals")
    if not isinstance(intervals, list):
        raise ValueError("interval label file must contain an 'intervals' array")

    by_sample: dict[str, list[IntervalLabel]] = {}
    for item in intervals:
        if not isinstance(item, dict):
            raise ValueError("each interval label must be an object")
        sample_id = item.get("sample_id")
        label = item.get("label")
        start_time = item.get("start_time")
        end_time = item.get("end_time")
        if not isinstance(sample_id, str) or not isinstance(label, str):
            raise ValueError("interval label must contain 'sample_id' and 'label'")
        if start_time is None or end_time is None:
            raise ValueError("interval label must contain 'start_time' and 'end_time'")
        interval = IntervalLabel(
            sample_id=sample_id,
            label=label,
            start_time=float(start_time),
            end_time=float(end_time),
            source=str(item.get("source") or "manual_review"),
        )
        by_sample.setdefault(sample_id, []).append(interval)
    return by_sample


def iter_window_slices(length: int, spec: WindowSpec) -> list[tuple[int, int]]:
    if length < spec.min_length:
        return []
    if length <= spec.window_size:
        return [(0, length)]
    windows: list[tuple[int, int]] = []
    start = 0
    while start + spec.window_size <= length:
        windows.append((start, start + spec.window_size))
        start += spec.stride
    if windows and windows[-1][1] < length:
        windows.append((length - spec.window_size, length))
    return windows


def _resolve_window_override(
    *,
    entry: dict[str, object],
    start: int,
    end: int,
    interval_labels: dict[str, list[IntervalLabel]] | None,
    min_overlap_ratio: float,
    timestamp_cache: dict[str, np.ndarray],
) -> tuple[str, str | None]:
    if interval_labels is None:
        return str(entry["internal_label"]), None
    sample_id = str(entry["sample_id"])
    sample_intervals = interval_labels.get(sample_id)
    if not sample_intervals:
        return str(entry["internal_label"]), None

    timestamps = timestamp_cache.get(sample_id)
    if timestamps is None:
        _, payload = load_pose_archive(entry["pose_path"])
        raw_timestamps = payload.get("timestamps")
        if raw_timestamps is None:
            timestamps = np.arange(int(entry["num_frames"]), dtype=np.float32)
        else:
            timestamps = np.asarray(raw_timestamps, dtype=np.float32).reshape(-1)
        timestamp_cache[sample_id] = timestamps

    window_timestamps = timestamps[start:end]
    if window_timestamps.size == 0:
        return str(entry["internal_label"]), None

    best_interval: IntervalLabel | None = None
    best_overlap_ratio = 0.0
    for interval in sample_intervals:
        interval_mask = (window_timestamps >= interval.start_time) & (window_timestamps <= interval.end_time)
        overlap_frames = int(interval_mask.sum())
        if overlap_frames == 0:
            continue
        interval_total = int(((timestamps >= interval.start_time) & (timestamps <= interval.end_time)).sum())
        reference = max(1, min(window_timestamps.size, interval_total))
        overlap_ratio = overlap_frames / reference
        if overlap_ratio > best_overlap_ratio:
            best_overlap_ratio = overlap_ratio
            best_interval = interval

    if best_interval is None or best_overlap_ratio < min_overlap_ratio:
        return str(entry["internal_label"]), None
    return best_interval.label, best_interval.source


def build_window_manifest(
    pose_manifest_path: str | Path,
    output_path: str | Path,
    spec: WindowSpec,
    *,
    interval_labels_path: str | Path | None = None,
    interval_min_overlap: float = 0.5,
) -> int:
    source = Path(pose_manifest_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    interval_labels = load_interval_labels(interval_labels_path) if interval_labels_path is not None else None
    timestamp_cache: dict[str, np.ndarray] = {}

    written = 0
    with source.open("r", encoding="utf-8") as reader, target.open("w", encoding="utf-8") as writer:
        for line in reader:
            entry = json.loads(line)
            num_frames = int(entry["num_frames"])
            for start, end in iter_window_slices(num_frames, spec):
                internal_label, label_source = _resolve_window_override(
                    entry=entry,
                    start=start,
                    end=end,
                    interval_labels=interval_labels,
                    min_overlap_ratio=interval_min_overlap,
                    timestamp_cache=timestamp_cache,
                )
                payload = {
                    "sample_id": entry["sample_id"],
                    "pose_path": entry["pose_path"],
                    "feature_path": entry.get("feature_path"),
                    "kinematic_feature_set": entry.get("kinematic_feature_set"),
                    "kinematic_dim": entry.get("kinematic_dim"),
                    "scene_prior_path": entry.get("scene_prior_path"),
                    "external_label": entry["external_label"],
                    "internal_label": internal_label,
                    "start": start,
                    "end": end,
                }
                if label_source is not None:
                    payload["label_source"] = label_source
                writer.write(json.dumps(payload, ensure_ascii=True) + "\n")
                written += 1
    return written
