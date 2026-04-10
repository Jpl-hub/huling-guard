from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from huling_guard.data.omnifall import OMNIFALL_CLASS_NAMES
from huling_guard.taxonomy import map_external_label

_CLIP_PATTERN = re.compile(
    r"^(?P<stem>.+)_(?P<label>\d+)_(?P<start>\d+\.\d+)_(?P<end>\d+\.\d+)_(?P<subject>\d+)_(?P<cam>\d+)_(?P<dataset>.+)\.avi$"
)


def _format_time(value: float) -> str:
    return f"{value:.3f}"


def _resolve_clip_path(
    clips_root: Path,
    stem: str,
    label_id: int,
    start: float,
    end: float,
    subject: int,
    cam: int,
    dataset_name: str,
) -> Path:
    subject_dir = clips_root / f"Subject.{subject}"
    candidate = subject_dir / (
        f"{stem}_{label_id}_{_format_time(start)}_{_format_time(end)}_{subject}_{cam}_{dataset_name}.avi"
    )
    if candidate.is_file():
        return candidate

    pattern = f"{stem}_{label_id}_*_{subject}_{cam}_{dataset_name}.avi"
    matches = sorted(subject_dir.glob(pattern))
    if matches:
        return matches[0]

    raise FileNotFoundError(f"unable to resolve clip file for stem={stem} subject={subject}")


def _build_payload(
    *,
    clip_path: Path,
    label_id: int,
    start: float,
    end: float,
    subject: int,
    cam: int,
    dataset_name: str,
    relative_path: str,
) -> dict[str, object]:
    external_label = OMNIFALL_CLASS_NAMES[label_id]
    return {
        "sample_id": (
            f"{dataset_name}__{relative_path.replace('/', '_')}__{label_id}"
            f"__{_format_time(start)}__{_format_time(end)}__{subject}__{cam}"
        ),
        "video_ref": str(clip_path),
        "external_label": external_label,
        "internal_label": map_external_label(external_label),
        "metadata": {
            "source_start": start,
            "source_end": end,
            "subject": subject,
            "cam": cam,
            "dataset": dataset_name,
            "path": relative_path,
        },
    }


def _iter_payloads_from_csv(csv_path: Path, clips_root: Path):
    with csv_path.open("r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            label_id = int(row["label"])
            start = float(row["start"])
            end = float(row["end"])
            subject = int(row["subject"])
            cam = int(row["cam"])
            dataset_name = str(row["dataset"])
            relative_path = str(row["path"])
            stem = Path(relative_path).name
            clip_path = _resolve_clip_path(
                clips_root=clips_root,
                stem=stem,
                label_id=label_id,
                start=start,
                end=end,
                subject=subject,
                cam=cam,
                dataset_name=dataset_name,
            )
            yield _build_payload(
                clip_path=clip_path,
                label_id=label_id,
                start=start,
                end=end,
                subject=subject,
                cam=cam,
                dataset_name=dataset_name,
                relative_path=relative_path,
            )


def _iter_payloads_from_clips(clips_root: Path):
    for clip_path in sorted(clips_root.rglob("*.avi")):
        match = _CLIP_PATTERN.match(clip_path.name)
        if not match:
            raise ValueError(f"unsupported clip filename format: {clip_path.name}")
        label_id = int(match.group("label"))
        start = float(match.group("start"))
        end = float(match.group("end"))
        subject = int(match.group("subject"))
        cam = int(match.group("cam"))
        dataset_name = match.group("dataset")
        relative_path = clip_path.relative_to(clips_root).with_suffix("").as_posix()
        yield _build_payload(
            clip_path=clip_path,
            label_id=label_id,
            start=start,
            end=end,
            subject=subject,
            cam=cam,
            dataset_name=dataset_name,
            relative_path=relative_path,
        )


def export_clip_bundle_manifest(
    csv_path: str | Path | None,
    clips_root: str | Path,
    output_path: str | Path,
) -> int:
    csv_path = Path(csv_path) if csv_path else None
    clips_root = Path(clips_root)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    iterator = _iter_payloads_from_csv(csv_path, clips_root) if csv_path else _iter_payloads_from_clips(clips_root)
    with output_path.open("w", encoding="utf-8") as writer:
        for payload in iterator:
            writer.write(json.dumps(payload, ensure_ascii=True) + "\n")
            written += 1
    return written
