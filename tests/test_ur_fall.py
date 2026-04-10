from pathlib import Path
import zipfile

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from huling_guard.data.manifests import load_jsonl
from huling_guard.data.ur_fall import prepare_ur_fall_manifest


def _make_frame(path: Path, value: int) -> None:
    frame = np.full((24, 32, 3), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), frame)


def test_prepare_ur_fall_manifest_converts_archives_to_videos(tmp_path: Path) -> None:
    source_root = tmp_path / "raw"
    source_root.mkdir()
    output_video_dir = tmp_path / "videos"
    manifest_path = tmp_path / "ur_fall_manifest.jsonl"

    staging = tmp_path / "staging"
    staging.mkdir()
    frame_a = staging / "rgb001.png"
    frame_b = staging / "rgb002.png"
    _make_frame(frame_a, 32)
    _make_frame(frame_b, 224)

    for archive_name in ("fall-01-cam0-rgb.zip", "adl-01-cam0-rgb.zip"):
        with zipfile.ZipFile(source_root / archive_name, "w") as archive:
            archive.write(frame_a, arcname="rgb001.png")
            archive.write(frame_b, arcname="rgb002.png")

    written = prepare_ur_fall_manifest(
        source_root=source_root,
        output_video_dir=output_video_dir,
        output_manifest_path=manifest_path,
        camera="cam0",
        fps=12.0,
    )

    assert written == 2
    rows = load_jsonl(manifest_path)
    assert [row["metadata"]["dataset"] for row in rows] == ["ur_fall", "ur_fall"]
    assert rows[0]["internal_label"] == "normal"
    assert rows[1]["internal_label"] == "fall"
    assert rows[0]["metadata"]["subject"] == "adl-01-cam0"
    assert rows[1]["metadata"]["subject"] == "fall-01-cam0"

    for row in rows:
        video_path = Path(row["video_ref"])
        assert video_path.is_file()
        capture = cv2.VideoCapture(str(video_path))
        assert capture.isOpened()
        ok, _ = capture.read()
        capture.release()
        assert ok
