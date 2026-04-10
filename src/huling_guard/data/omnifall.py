from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from huling_guard.taxonomy import map_external_label

if TYPE_CHECKING:
    from datasets import Dataset, IterableDataset

DEFAULT_DATASET_ID = "simplexsigil2/omnifall"
OMNIFALL_CLASS_NAMES = (
    "walk",
    "fall",
    "fallen",
    "sit_down",
    "sitting",
    "lie_down",
    "lying",
    "stand_up",
    "standing",
    "other",
    "kneel_down",
    "kneeling",
    "squat_down",
    "squatting",
    "crawl",
    "jump",
)
VIDEO_KEYS = ("video", "clip", "mp4", "filepath", "file", "path")
LABEL_KEYS = ("label", "activity", "activity_label", "coarse_label", "class")
ID_KEYS = ("id", "sample_id", "clip_id", "video_id", "uid")


def load_omnifall_split(
    split: str,
    dataset_id: str = DEFAULT_DATASET_ID,
    config_name: str | None = None,
    streaming: bool = False,
) -> "Dataset | IterableDataset":
    from datasets import load_dataset

    kwargs: dict[str, Any] = {"split": split, "streaming": streaming}
    if config_name:
        return load_dataset(dataset_id, config_name, **kwargs)
    return load_dataset(dataset_id, **kwargs)


def _pick_column(columns: Iterable[str], candidates: tuple[str, ...], name: str) -> str:
    lower_map = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    raise KeyError(f"unable to infer {name} column from {sorted(columns)}")


def _pick_optional_column(columns: Iterable[str], candidates: tuple[str, ...]) -> str | None:
    lower_map = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def _resolve_label_name(dataset: "Dataset | IterableDataset", label_key: str, raw_value: Any) -> str:
    from datasets import ClassLabel

    features = getattr(dataset, "features", None)
    if not features:
        return str(raw_value)
    feature = features[label_key]
    if isinstance(feature, ClassLabel):
        return feature.int2str(int(raw_value))
    if isinstance(raw_value, int) and 0 <= raw_value < len(OMNIFALL_CLASS_NAMES):
        return OMNIFALL_CLASS_NAMES[int(raw_value)]
    return str(raw_value)


def _extract_video_ref(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("path", "filepath", "filename"):
            if value.get(key):
                return str(value[key])
    return str(value)


def _derive_sample_id(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("dataset", "unknown")),
        str(row.get("path", "unknown")),
        str(row.get("subject", "na")),
        str(row.get("cam", "na")),
        f"{float(row.get('start', 0.0)):.3f}",
        f"{float(row.get('end', 0.0)):.3f}",
    ]
    joined = "__".join(parts)
    return joined.replace("/", "_").replace("\\", "_").replace(" ", "_")


def export_omnifall_manifest(
    output_path: str | Path,
    split: str,
    dataset_id: str = DEFAULT_DATASET_ID,
    config_name: str | None = None,
    streaming: bool = False,
    limit: int | None = None,
    include_datasets: set[str] | None = None,
) -> int:
    dataset = load_omnifall_split(
        split=split,
        dataset_id=dataset_id,
        config_name=config_name,
        streaming=streaming,
    )
    columns = tuple(dataset.column_names)
    id_key = _pick_optional_column(columns, ID_KEYS)
    label_key = _pick_column(columns, LABEL_KEYS, "label")
    video_key = _pick_column(columns, VIDEO_KEYS, "video")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with target.open("w", encoding="utf-8") as handle:
        for row in dataset:
            row_dataset = str(row.get("dataset", "")).strip()
            if include_datasets and row_dataset not in include_datasets:
                continue
            external_label = _resolve_label_name(dataset, label_key, row[label_key])
            sample_id = str(row[id_key]) if id_key else _derive_sample_id(row)
            payload = {
                "sample_id": sample_id,
                "video_ref": _extract_video_ref(row.get(video_key)),
                "external_label": external_label,
                "internal_label": map_external_label(external_label),
                "metadata": {
                    key: value
                    for key, value in row.items()
                    if key not in {id_key, label_key, video_key}
                },
            }
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
            written += 1
            if limit is not None and written >= limit:
                break
    return written
