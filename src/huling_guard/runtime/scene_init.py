from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from huling_guard.contracts import ScenePrior, SceneRegion

DEFAULT_PROMPTS = ("bed", "sofa", "chair", "floor", "table", "cabinet")


@dataclass(slots=True)
class DetectionPrompt:
    labels: tuple[str, ...] = DEFAULT_PROMPTS
    box_threshold: float = 0.3
    text_threshold: float = 0.25


class RoomPriorBuilder:
    def __init__(
        self,
        grounding_config_path: str,
        grounding_checkpoint_path: str,
        sam2_model_config: str,
        sam2_checkpoint_path: str,
        device: str = "cuda",
    ) -> None:
        try:
            import groundingdino.datasets.transforms as T
            from groundingdino.util import box_ops
            from groundingdino.util.inference import load_model, predict
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor
        except ImportError as exc:
            raise ImportError("Grounding DINO and SAM 2 must be installed for room prior creation") from exc

        self._box_ops = box_ops
        self._grounding_predict = predict
        self._grounding_model = load_model(
            grounding_config_path,
            grounding_checkpoint_path,
            device=device,
        )
        self._grounding_transform = T.Compose(
            [
                T.RandomResize([800], max_size=1333),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        sam_model = build_sam2(sam2_model_config, sam2_checkpoint_path, device=device)
        self._sam_predictor = SAM2ImagePredictor(sam_model)

    @staticmethod
    def _mask_to_normalized_bbox(mask: np.ndarray, width: int, height: int) -> tuple[float, float, float, float]:
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            return (0.0, 0.0, 0.0, 0.0)
        x1, x2 = float(xs.min()) / width, float(xs.max()) / width
        y1, y2 = float(ys.min()) / height, float(ys.max()) / height
        return (x1, y1, x2, y2)

    @staticmethod
    def _normalize_label(raw_phrase: str) -> str:
        cleaned = raw_phrase.split("(")[0].strip().lower()
        return cleaned.replace(".", "").strip()

    def build(self, frame_bgr: np.ndarray, prompt: DetectionPrompt | None = None) -> ScenePrior:
        prompt = prompt or DetectionPrompt()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        _, transformed = self._grounding_transform(pil_image, None)
        height, width = frame_rgb.shape[:2]
        caption = " . ".join(prompt.labels)

        boxes, logits, phrases = self._grounding_predict(
            model=self._grounding_model,
            image=transformed,
            caption=caption,
            box_threshold=prompt.box_threshold,
            text_threshold=prompt.text_threshold,
        )
        if hasattr(boxes, "cpu"):
            boxes = boxes.cpu()
        absolute_boxes = self._box_ops.box_cxcywh_to_xyxy(boxes).numpy()
        absolute_boxes *= np.array([width, height, width, height], dtype=np.float32)

        self._sam_predictor.set_image(frame_rgb)
        regions: list[SceneRegion] = []
        for box, phrase, score in zip(absolute_boxes, phrases, logits):
            mask, _, _ = self._sam_predictor.predict(box=box, multimask_output=False)
            current_mask = np.asarray(mask[0], dtype=np.uint8)
            normalized_bbox = self._mask_to_normalized_bbox(current_mask, width, height)
            regions.append(
                SceneRegion(
                    label=self._normalize_label(str(phrase)),
                    bbox=normalized_bbox,
                    score=float(score),
                )
            )

        floor_candidates = [region.bbox[3] for region in regions if region.label == "floor"]
        floor_line_y = max(floor_candidates) if floor_candidates else None
        return ScenePrior(
            frame_width=width,
            frame_height=height,
            regions=tuple(regions),
            floor_line_y=floor_line_y,
        )
