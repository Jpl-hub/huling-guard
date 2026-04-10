from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from huling_guard.contracts import ScenePrior
from huling_guard.runtime.scene_init import DetectionPrompt, RoomPriorBuilder


@dataclass(slots=True)
class RoomPriorConfig:
    media_path: Path
    output_path: Path
    grounding_config_path: str
    grounding_checkpoint_path: str
    sam2_model_config: str
    sam2_checkpoint_path: str
    device: str


def _load_reference_frame(media_path: str | Path) -> np.ndarray:
    media_path = Path(media_path)
    if media_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
        frame = cv2.imread(str(media_path))
        if frame is None:
            raise FileNotFoundError(f"unable to read image: {media_path}")
        return frame

    capture = cv2.VideoCapture(str(media_path))
    if not capture.isOpened():
        raise FileNotFoundError(f"unable to open media: {media_path}")
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise RuntimeError(f"unable to read a frame from media: {media_path}")
    return frame


def build_room_prior(config: RoomPriorConfig) -> ScenePrior:
    builder = RoomPriorBuilder(
        grounding_config_path=config.grounding_config_path,
        grounding_checkpoint_path=config.grounding_checkpoint_path,
        sam2_model_config=config.sam2_model_config,
        sam2_checkpoint_path=config.sam2_checkpoint_path,
        device=config.device,
    )
    reference_frame = _load_reference_frame(config.media_path)
    prior = builder.build(reference_frame, prompt=DetectionPrompt())
    prior.save(config.output_path)
    return prior
