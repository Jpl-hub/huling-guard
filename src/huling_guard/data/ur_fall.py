from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.request import urlopen
import zipfile

import cv2
import numpy as np

from huling_guard.taxonomy import map_external_label

UR_FALL_BASE_URL = "https://fenix.ur.edu.pl/~mkepski/ds/data"
_ARCHIVE_PATTERN = re.compile(r"^(?P<label>fall|adl)-(?P<sequence>\d+)-(?P<camera>cam[01])-rgb\.zip$")


def _iter_ur_fall_archive_names(camera: str) -> list[str]:
    if camera not in {"cam0", "cam1", "both"}:
        raise ValueError("camera must be one of: cam0, cam1, both")

    names: list[str] = []
    if camera in {"cam0", "both"}:
        names.extend(f"adl-{index:02d}-cam0-rgb.zip" for index in range(1, 41))
    if camera in {"cam0", "both"}:
        names.extend(f"fall-{index:02d}-cam0-rgb.zip" for index in range(1, 31))
    if camera in {"cam1", "both"}:
        names.extend(f"fall-{index:02d}-cam1-rgb.zip" for index in range(1, 31))
    return names


def download_ur_fall_rgb_archives(
    target_dir: str | Path,
    *,
    camera: str = "cam0",
    overwrite: bool = False,
) -> int:
    output_dir = Path(target_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for archive_name in _iter_ur_fall_archive_names(camera):
        target_path = output_dir / archive_name
        if target_path.is_file() and not overwrite:
            continue
        url = f"{UR_FALL_BASE_URL}/{archive_name}"
        print(f"[download] {url} -> {target_path}", flush=True)
        with urlopen(url, timeout=120) as response:
            target_path.write_bytes(response.read())
        downloaded += 1
    return downloaded


def _sorted_image_names(archive: zipfile.ZipFile) -> list[str]:
    candidates = [
        name
        for name in archive.namelist()
        if not name.endswith("/")
        and Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
    ]
    return sorted(candidates)


def _decode_frame(archive: zipfile.ZipFile, image_name: str) -> np.ndarray:
    encoded = archive.read(image_name)
    buffer = np.frombuffer(encoded, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"unable to decode frame '{image_name}'")
    return frame


def _build_manifest_row(video_path: Path, archive_name: str) -> dict[str, object]:
    match = _ARCHIVE_PATTERN.match(archive_name)
    if match is None:
        raise ValueError(f"unsupported UR Fall archive name: {archive_name}")
    sequence_type = match.group("label")
    sequence_id = match.group("sequence")
    camera = match.group("camera")
    subject = archive_name.removesuffix("-rgb.zip")
    external_label = "fall" if sequence_type == "fall" else "adl"
    return {
        "sample_id": f"ur_fall__{subject}",
        "video_ref": str(video_path),
        "external_label": external_label,
        "internal_label": map_external_label(external_label),
        "metadata": {
            "dataset": "ur_fall",
            "subject": subject,
            "camera": camera,
            "sequence_id": sequence_id,
            "sequence_type": sequence_type,
            "source_archive": archive_name,
        },
    }


def prepare_ur_fall_manifest(
    source_root: str | Path,
    output_video_dir: str | Path,
    output_manifest_path: str | Path,
    *,
    camera: str = "cam0",
    fps: float = 18.0,
    overwrite: bool = False,
) -> int:
    source_dir = Path(source_root)
    if not source_dir.is_dir():
        raise FileNotFoundError(source_dir)

    if camera not in {"cam0", "cam1", "both"}:
        raise ValueError("camera must be one of: cam0, cam1, both")

    target_video_dir = Path(output_video_dir)
    target_video_dir.mkdir(parents=True, exist_ok=True)
    output_manifest = Path(output_manifest_path)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    accepted_cameras = {"cam0", "cam1"} if camera == "both" else {camera}
    archive_paths = []
    for archive_path in sorted(source_dir.glob("*-rgb.zip")):
        match = _ARCHIVE_PATTERN.match(archive_path.name)
        if match is None:
            continue
        if match.group("camera") not in accepted_cameras:
            continue
        archive_paths.append(archive_path)

    written = 0
    with output_manifest.open("w", encoding="utf-8") as manifest_handle:
        for archive_path in archive_paths:
            with zipfile.ZipFile(archive_path) as archive:
                image_names = _sorted_image_names(archive)
                if not image_names:
                    raise ValueError(f"archive contains no RGB frames: {archive_path}")
                video_path = target_video_dir / f"{archive_path.stem}.mp4"
                if overwrite or not video_path.is_file():
                    first_frame = _decode_frame(archive, image_names[0])
                    height, width = first_frame.shape[:2]
                    writer = cv2.VideoWriter(
                        str(video_path),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps,
                        (width, height),
                    )
                    if not writer.isOpened():
                        raise RuntimeError(f"unable to create video writer for {video_path}")
                    try:
                        writer.write(first_frame)
                        for image_name in image_names[1:]:
                            writer.write(_decode_frame(archive, image_name))
                    finally:
                        writer.release()
                row = _build_manifest_row(video_path=video_path, archive_name=archive_path.name)
                manifest_handle.write(json.dumps(row, ensure_ascii=True) + "\n")
                written += 1
    return written
