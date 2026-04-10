from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

BBox = tuple[float, float, float, float]


@dataclass(slots=True, frozen=True)
class SceneRegion:
    label: str
    bbox: BBox
    score: float = 1.0

    def contains(self, x: float, y: float) -> bool:
        x1, y1, x2, y2 = self.bbox
        return x1 <= x <= x2 and y1 <= y <= y2

    def distance_to(self, x: float, y: float) -> float:
        x1, y1, x2, y2 = self.bbox
        dx = max(x1 - x, 0.0, x - x2)
        dy = max(y1 - y, 0.0, y - y2)
        return float(np.hypot(dx, dy))


@dataclass(slots=True)
class ScenePrior:
    frame_width: int
    frame_height: int
    regions: tuple[SceneRegion, ...]
    floor_line_y: float | None = None

    def find(self, *labels: str) -> tuple[SceneRegion, ...]:
        wanted = tuple(label.lower() for label in labels)
        return tuple(region for region in self.regions if region.label.lower() in wanted)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "floor_line_y": self.floor_line_y,
            "regions": [asdict(region) for region in self.regions],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenePrior":
        regions = tuple(SceneRegion(**region) for region in payload.get("regions", []))
        return cls(
            frame_width=int(payload["frame_width"]),
            frame_height=int(payload["frame_height"]),
            regions=regions,
            floor_line_y=payload.get("floor_line_y"),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ScenePrior":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def save(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


@dataclass(slots=True)
class PoseTrackWindow:
    sample_id: str
    timestamps: np.ndarray
    keypoints: np.ndarray
    external_label: str | None = None
    internal_label: str | None = None
    scene_prior: ScenePrior | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class ModelBatch:
    poses: np.ndarray
    kinematics: np.ndarray
    scene_features: np.ndarray
    label_ids: np.ndarray
    risk_targets: np.ndarray

