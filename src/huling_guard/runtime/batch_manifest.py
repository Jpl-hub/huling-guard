from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BatchVideoItem:
    clip_id: str
    input_path: Path
    sample_id: str | None = None
    expected_state: str | None = None
    expected_incident: bool | None = None
    annotations_path: Path | None = None
    scene_prior_path: Path | None = None


def load_batch_video_manifest(path: str | Path) -> list[BatchVideoItem]:
    manifest_path = Path(path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("batch video manifest must be a JSON object")
    raw_clips = payload.get("clips")
    if not isinstance(raw_clips, list):
        raise ValueError("batch video manifest must contain a 'clips' array")

    base_dir = manifest_path.parent
    clips: list[BatchVideoItem] = []
    for index, item in enumerate(raw_clips):
        if not isinstance(item, dict):
            raise ValueError("each clip entry must be an object")
        input_value = item.get("input")
        if not isinstance(input_value, str):
            raise ValueError("each clip entry must contain 'input'")
        clip_id = str(item.get("clip_id") or Path(input_value).stem or f"clip_{index:04d}")
        annotations_value = item.get("annotations")
        scene_prior_value = item.get("scene_prior")
        clips.append(
            BatchVideoItem(
                clip_id=clip_id,
                input_path=(base_dir / input_value).resolve(),
                sample_id=str(item.get("sample_id")) if item.get("sample_id") is not None else None,
                expected_state=str(item.get("expected_state"))
                if item.get("expected_state") is not None
                else None,
                expected_incident=bool(item.get("expected_incident"))
                if item.get("expected_incident") is not None
                else None,
                annotations_path=(base_dir / annotations_value).resolve()
                if isinstance(annotations_value, str)
                else None,
                scene_prior_path=(base_dir / scene_prior_value).resolve()
                if isinstance(scene_prior_value, str)
                else None,
            )
        )
    return clips
