from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import cv2
import numpy as np

from huling_guard.runtime.rtmo import RTMOPoseEstimator


@dataclass(slots=True)
class PoseExtractionConfig:
    manifest_path: Path
    output_dir: Path
    output_manifest_path: Path
    model_name: str
    device: str
    frame_stride: int = 1
    source_root: Path | None = None


COMMON_VIDEO_SUFFIXES = (".mp4", ".avi", ".mov", ".mkv", ".webm")


def _load_completed_samples(output_manifest_path: Path) -> set[str]:
    if not output_manifest_path.is_file():
        return set()
    completed: set[str] = set()
    with output_manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = str(payload.get("sample_id", "")).strip()
            if sample_id:
                completed.add(sample_id)
    return completed


def _should_report_progress(index: int, written: int, skipped: int) -> bool:
    if written <= 3 and written > 0:
        return True
    if index % 10 == 0:
        return True
    if skipped > 0 and index % 50 == 0:
        return True
    return False


def _timestamp_seconds(capture: cv2.VideoCapture, frame_index: int, fps: float) -> float:
    pos_msec = capture.get(cv2.CAP_PROP_POS_MSEC)
    if pos_msec > 0:
        return pos_msec / 1000.0
    return frame_index / max(fps, 1.0)


def resolve_video_path(entry: dict[str, object], source_root: Path | None) -> Path:
    raw_ref = entry.get("video_ref")
    if isinstance(raw_ref, str):
        raw_path = Path(raw_ref)
        if raw_path.is_file():
            return raw_path
        if raw_path.is_absolute():
            raise FileNotFoundError(f"video file not found: {raw_path}")

    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    if source_root is None:
        raise FileNotFoundError(
            "manifest video_ref is not directly usable; provide source_root for relative dataset paths"
        )

    relative = str(raw_ref or metadata.get("path") or "").strip()
    dataset_name = str(metadata.get("dataset") or "").strip()
    base_candidates: list[Path] = []
    if dataset_name and relative:
        base_candidates.append(source_root / dataset_name / relative)
    if relative:
        base_candidates.append(source_root / relative)

    for base in base_candidates:
        if base.is_file():
            return base
        for suffix in COMMON_VIDEO_SUFFIXES:
            candidate = base.with_suffix(suffix)
            if candidate.is_file():
                return candidate

    stem = Path(relative).name
    if dataset_name:
        for suffix in COMMON_VIDEO_SUFFIXES:
            matches = list((source_root / dataset_name).rglob(f"{stem}{suffix}"))
            if matches:
                return matches[0]
    for suffix in COMMON_VIDEO_SUFFIXES:
        matches = list(source_root.rglob(f"{stem}{suffix}"))
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"unable to resolve video path for sample {entry.get('sample_id')} from {relative}"
    )


def extract_primary_pose_track(
    video_path: str | Path,
    estimator: RTMOPoseEstimator,
    frame_stride: int = 1,
    start_time: float | None = None,
    end_time: float | None = None,
) -> tuple[np.ndarray, np.ndarray, int, int, float]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise FileNotFoundError(f"unable to open video: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if start_time is not None and start_time > 0:
        capture.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000.0)
    frame_index = 0
    timestamps: list[float] = []
    keypoints: list[np.ndarray] = []

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if width <= 1 or height <= 1:
                height, width = frame.shape[:2]
            current_timestamp = _timestamp_seconds(capture, frame_index, fps)
            if end_time is not None and current_timestamp > end_time:
                break
            if frame_index % frame_stride != 0:
                frame_index += 1
                continue
            detections = estimator.infer(frame)
            primary = estimator.select_primary(detections)
            pose = primary.keypoints if primary else np.zeros((17, 3), dtype=np.float32)
            keypoints.append(pose.astype(np.float32))
            timestamps.append(current_timestamp)
            frame_index += 1
    finally:
        capture.release()

    if not keypoints:
        raise RuntimeError(f"no frames were extracted from video: {video_path}")

    return (
        np.stack(keypoints, axis=0),
        np.asarray(timestamps, dtype=np.float32),
        width,
        height,
        fps,
    )


def extract_from_manifest(config: PoseExtractionConfig) -> int:
    manifest_path = Path(config.manifest_path)
    output_dir = Path(config.output_dir)
    output_manifest_path = Path(config.output_manifest_path)
    source_root = Path(config.source_root) if config.source_root is not None else None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    estimator = RTMOPoseEstimator(model_name=config.model_name, device=config.device)
    completed_samples = _load_completed_samples(output_manifest_path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        total_entries = sum(1 for _ in handle)
    mode = "a" if output_manifest_path.exists() else "w"

    written = 0
    skipped = 0
    with manifest_path.open("r", encoding="utf-8") as reader, output_manifest_path.open(
        mode, encoding="utf-8"
    ) as writer:
        for index, line in enumerate(reader, start=1):
            entry = json.loads(line)
            sample_id = entry["sample_id"]
            output_path = output_dir / f"{sample_id}.npz"
            if sample_id in completed_samples:
                if not output_path.is_file():
                    raise FileNotFoundError(
                        f"pose manifest already contains {sample_id} but npz is missing: {output_path}"
                    )
                skipped += 1
                if _should_report_progress(index=index, written=written, skipped=skipped):
                    print(
                        f"[extract] progress={index}/{total_entries} written={written} skipped={skipped}",
                        flush=True,
                    )
                continue
            video_path = resolve_video_path(entry, source_root)
            metadata = entry.get("metadata") or {}
            try:
                keypoints, timestamps, width, height, fps = extract_primary_pose_track(
                    video_path=video_path,
                    estimator=estimator,
                    frame_stride=config.frame_stride,
                    start_time=float(metadata["start"]) if "start" in metadata else None,
                    end_time=float(metadata["end"]) if "end" in metadata else None,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"pose extraction failed for sample_id={sample_id} video={video_path}"
                ) from exc
            np.savez_compressed(
                output_path,
                keypoints=keypoints,
                timestamps=timestamps,
                frame_width=np.asarray([width], dtype=np.int32),
                frame_height=np.asarray([height], dtype=np.int32),
                fps=np.asarray([fps], dtype=np.float32),
            )
            payload = {
                "sample_id": sample_id,
                "pose_path": str(output_path),
                "num_frames": int(keypoints.shape[0]),
                "external_label": entry["external_label"],
                "internal_label": entry["internal_label"],
                "scene_prior_path": entry.get("scene_prior_path"),
                "metadata": metadata,
                "video_ref": str(video_path),
            }
            writer.write(json.dumps(payload, ensure_ascii=True) + "\n")
            written += 1
            if _should_report_progress(index=index, written=written, skipped=skipped):
                print(
                    f"[extract] progress={index}/{total_entries} written={written} skipped={skipped}",
                    flush=True,
                )
    return written
