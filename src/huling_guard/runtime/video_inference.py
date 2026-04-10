from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import cv2
import numpy as np

from huling_guard.data.pose_io import normalize_pose_coords
from huling_guard.runtime.rtmo import RTMOPoseEstimator
from huling_guard.runtime.session_report import build_session_report, write_session_report
from huling_guard.runtime.service import RuntimeLaunchConfig, build_runtime_pipeline
from huling_guard.runtime.visualize import annotate_snapshot_overlay, draw_pose_overlay


@dataclass(slots=True)
class VideoInferenceConfig:
    launch: RuntimeLaunchConfig
    input_path: Path
    output_jsonl: Path | None = None
    output_video: Path | None = None
    output_report_json: Path | None = None
    output_report_markdown: Path | None = None
    rtmo_device: str = "cuda:0"
    score_threshold: float = 0.2

def run_video_inference_with_runtime(
    *,
    input_path: Path,
    pipeline,
    estimator: RTMOPoseEstimator,
    output_jsonl: Path | None = None,
    output_video: Path | None = None,
    output_report_json: Path | None = None,
    output_report_markdown: Path | None = None,
    score_threshold: float = 0.2,
) -> int:
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise FileNotFoundError(f"unable to open video: {input_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_index = 0
    writer = None

    if output_video is not None:
        output_video.parent.mkdir(parents=True, exist_ok=True)

    jsonl_handle = None
    if output_jsonl is not None:
        output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        jsonl_handle = output_jsonl.open("w", encoding="utf-8")

    processed = 0
    pipeline.reset()
    collect_report = output_report_json is not None or output_report_markdown is not None
    session_snapshots: list[dict[str, object]] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if width <= 1 or height <= 1:
                height, width = frame.shape[:2]
            if writer is None and output_video is not None:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(output_video), fourcc, fps, (width, height))
            timestamp = frame_index / max(fps, 1.0)
            detections = estimator.infer(frame)
            primary = estimator.select_primary(detections)
            pose = primary.keypoints if primary is not None else np.zeros((17, 3), dtype=np.float32)
            normalized_pose = normalize_pose_coords(
                pose,
                frame_width=width,
                frame_height=height,
            )
            snapshot = pipeline.push_pose(keypoints=normalized_pose, timestamp=timestamp)
            snapshot_payload = snapshot.to_dict()

            if jsonl_handle is not None:
                jsonl_handle.write(json.dumps(snapshot_payload, ensure_ascii=True) + "\n")
            if collect_report:
                session_snapshots.append(snapshot_payload)

            if writer is not None:
                annotated = frame.copy()
                if primary is not None:
                    draw_pose_overlay(annotated, pose, score_threshold)
                annotate_snapshot_overlay(annotated, snapshot)
                writer.write(annotated)

            processed += 1
            frame_index += 1
            if processed % 30 == 0:
                print(
                    f"[video-inference] processed_frames={processed} timestamp={timestamp:.2f}",
                    flush=True,
                )
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        if jsonl_handle is not None:
            jsonl_handle.close()

    if collect_report:
        report = build_session_report(
            snapshots=session_snapshots,
            session_name=input_path.stem,
            source_path=str(input_path.resolve()),
        )
        write_session_report(
            report,
            output_json=output_report_json,
            output_markdown=output_report_markdown,
        )

    return processed


def run_video_inference(config: VideoInferenceConfig) -> int:
    pipeline = build_runtime_pipeline(config.launch)
    estimator = RTMOPoseEstimator(device=config.rtmo_device)
    return run_video_inference_with_runtime(
        input_path=config.input_path,
        pipeline=pipeline,
        estimator=estimator,
        output_jsonl=config.output_jsonl,
        output_video=config.output_video,
        output_report_json=config.output_report_json,
        output_report_markdown=config.output_report_markdown,
        score_threshold=config.score_threshold,
    )
