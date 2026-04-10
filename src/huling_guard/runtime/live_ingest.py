from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import cv2
import numpy as np

from huling_guard.data.pose_io import normalize_pose_coords
from huling_guard.runtime.rtmo import RTMOPoseEstimator
from huling_guard.runtime.visualize import annotate_snapshot_overlay, draw_pose_overlay


@dataclass(slots=True)
class LiveIngestConfig:
    runtime_url: str
    source: str
    source_label: str | None = None
    rtmo_device: str = "cuda:0"
    frame_stride: int = 1
    preview_stride: int = 4
    score_threshold: float = 0.2
    request_timeout: float = 10.0
    max_frames: int | None = None
    loop: bool = False


def _normalized_runtime_url(value: str) -> str:
    return value.rstrip("/")


def _post_json(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_bytes(url: str, payload: bytes, timeout: float) -> None:
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "image/jpeg"},
        method="POST",
    )
    with urlopen(request, timeout=timeout):
        return


def _open_capture(source: str) -> cv2.VideoCapture:
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def _source_label(source: str, explicit_label: str | None) -> str:
    if explicit_label:
        return explicit_label
    if source.isdigit():
        return f"USB 摄像头 {source}"
    if source.startswith("rtsp://"):
        return "RTSP 视频流"
    return Path(source).stem or "视频输入"


def run_live_ingest(config: LiveIngestConfig) -> int:
    estimator = RTMOPoseEstimator(device=config.rtmo_device)
    runtime_url = _normalized_runtime_url(config.runtime_url)
    source_label = _source_label(config.source, config.source_label)
    processed = 0

    while True:
        capture = _open_capture(config.source)
        if not capture.isOpened():
            raise FileNotFoundError(f"unable to open source: {config.source}")

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
        frame_index = 0
        started_at = time.perf_counter()
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % max(1, config.frame_stride) != 0:
                    frame_index += 1
                    continue

                frame_height, frame_width = frame.shape[:2]
                pos_msec = capture.get(cv2.CAP_PROP_POS_MSEC)
                if pos_msec > 0:
                    timestamp = pos_msec / 1000.0
                else:
                    timestamp = time.perf_counter() - started_at if config.source.isdigit() else frame_index / max(fps, 1.0)

                detections = estimator.infer(frame)
                primary = estimator.select_primary(detections)
                pose = primary.keypoints if primary is not None else np.zeros((17, 3), dtype=np.float32)
                normalized_pose = normalize_pose_coords(
                    pose,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )

                snapshot = _post_json(
                    f"{runtime_url}/pose-frame",
                    {
                        "timestamp": timestamp,
                        "frame_width": frame_width,
                        "frame_height": frame_height,
                        "keypoints": normalized_pose.tolist(),
                    },
                    timeout=config.request_timeout,
                )

                if processed % max(1, config.preview_stride) == 0:
                    preview = frame.copy()
                    if primary is not None:
                        draw_pose_overlay(preview, pose, config.score_threshold)
                    annotate_snapshot_overlay(preview, snapshot)
                    ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 84])
                    if ok:
                        query = urlencode(
                            {
                                "source": config.source,
                                "source_label": source_label,
                                "timestamp": f"{timestamp:.3f}",
                                "frame_width": frame_width,
                                "frame_height": frame_height,
                                "annotated": "true",
                            }
                        )
                        _post_bytes(
                            f"{runtime_url}/live-frame?{query}",
                            encoded.tobytes(),
                            timeout=config.request_timeout,
                        )

                processed += 1
                frame_index += 1
                if processed % 30 == 0:
                    print(
                        f"[live-ingest] processed_frames={processed} source={source_label} timestamp={timestamp:.2f}",
                        flush=True,
                    )
                if config.max_frames is not None and processed >= config.max_frames:
                    return processed
        finally:
            capture.release()

        if not config.loop:
            return processed

