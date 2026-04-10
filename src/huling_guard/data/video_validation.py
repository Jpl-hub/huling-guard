from __future__ import annotations

from pathlib import Path

import cv2

from huling_guard.data.manifests import load_jsonl, write_jsonl
from huling_guard.extract import resolve_video_path


def validate_manifest_videos(
    manifest_path: str | Path,
    valid_output_path: str | Path,
    invalid_output_path: str | Path,
    source_root: str | Path | None = None,
) -> tuple[int, int]:
    manifest_path = Path(manifest_path)
    source_root = Path(source_root) if source_root is not None else None
    rows = load_jsonl(manifest_path)

    valid_rows: list[dict[str, object]] = []
    invalid_rows: list[dict[str, object]] = []

    for index, row in enumerate(rows, start=1):
        try:
            video_path = resolve_video_path(row, source_root)
            capture = cv2.VideoCapture(str(video_path))
            try:
                if not capture.isOpened():
                    raise FileNotFoundError(f"unable to open video: {video_path}")
                ok, _ = capture.read()
                if not ok:
                    raise RuntimeError(f"no frames were extracted from video: {video_path}")
            finally:
                capture.release()
            valid_rows.append(row)
        except Exception as exc:
            payload = dict(row)
            payload["validation_error"] = str(exc)
            invalid_rows.append(payload)

        if index % 100 == 0:
            print(
                f"[validate-videos] progress={index}/{len(rows)} valid={len(valid_rows)} invalid={len(invalid_rows)}",
                flush=True,
            )

    write_jsonl(valid_output_path, valid_rows)
    write_jsonl(invalid_output_path, invalid_rows)
    return len(valid_rows), len(invalid_rows)
