import json
from pathlib import Path

import numpy as np

from huling_guard.contracts import ScenePrior, SceneRegion
from huling_guard.data.feature_cache import build_feature_cache_manifest
from huling_guard.data.manifests import load_jsonl
from huling_guard.data.windows import WindowSpec, build_window_manifest


def _build_pose_clip(num_frames: int) -> np.ndarray:
    clip = np.zeros((num_frames, 17, 3), dtype=np.float32)
    clip[:, :, 2] = 1.0
    for frame_idx in range(num_frames):
        x = 0.2 + frame_idx * 0.01
        y = 0.6 + frame_idx * 0.005
        clip[frame_idx, 5, :2] = [x, y - 0.1]
        clip[frame_idx, 6, :2] = [x, y - 0.1]
        clip[frame_idx, 11, :2] = [x, y]
        clip[frame_idx, 12, :2] = [x, y]
        clip[frame_idx, 15, :2] = [x, y + 0.05]
        clip[frame_idx, 16, :2] = [x, y + 0.05]
    return clip


def test_feature_cache_manifest_and_windows_include_feature_path(tmp_path: Path) -> None:
    pose_dir = tmp_path / "poses"
    pose_dir.mkdir()
    pose_path = pose_dir / "sample_a.npz"
    np.savez(
        pose_path,
        keypoints=_build_pose_clip(12),
        frame_width=np.asarray([1920], dtype=np.int32),
        frame_height=np.asarray([1080], dtype=np.int32),
    )

    scene_prior_path = tmp_path / "room.json"
    ScenePrior(
        frame_width=1920,
        frame_height=1080,
        regions=(
            SceneRegion(label="floor", bbox=(0.0, 0.7, 1.0, 1.0), score=1.0),
            SceneRegion(label="bed", bbox=(0.05, 0.55, 0.4, 0.95), score=0.9),
        ),
    ).save(scene_prior_path)

    pose_manifest = tmp_path / "poses.jsonl"
    pose_manifest.write_text(
        json.dumps(
            {
                "sample_id": "sample_a",
                "pose_path": str(pose_path),
                "num_frames": 12,
                "external_label": "fall",
                "internal_label": "fall",
                "scene_prior_path": str(scene_prior_path),
                "metadata": {"dataset": "unit"},
            },
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    feature_dir = tmp_path / "features"
    feature_manifest = tmp_path / "features.jsonl"
    written = build_feature_cache_manifest(
        pose_manifest_path=pose_manifest,
        output_dir=feature_dir,
        output_manifest_path=feature_manifest,
        kinematic_feature_set="v2",
    )

    assert written == 1
    feature_rows = load_jsonl(feature_manifest)
    assert feature_rows[0]["sample_id"] == "sample_a"
    assert Path(feature_rows[0]["feature_path"]).is_file()
    assert feature_rows[0]["kinematic_feature_set"] == "v2"
    assert feature_rows[0]["kinematic_dim"] == 12

    cached = np.load(feature_rows[0]["feature_path"], allow_pickle=False)
    assert cached["poses"].shape == (12, 17, 3)
    assert cached["kinematics"].shape == (12, 12)
    assert cached["scene_features"].shape == (12, 8)

    window_manifest = tmp_path / "windows.jsonl"
    build_window_manifest(
        pose_manifest_path=feature_manifest,
        output_path=window_manifest,
        spec=WindowSpec(window_size=8, stride=4, min_length=4),
    )
    window_rows = load_jsonl(window_manifest)
    assert window_rows
    assert window_rows[0]["feature_path"] == feature_rows[0]["feature_path"]
    assert window_rows[0]["kinematic_feature_set"] == "v2"
    assert window_rows[0]["kinematic_dim"] == 12
    assert window_rows[0]["pose_path"] == str(pose_path)


def test_build_window_manifest_applies_interval_label_overrides(tmp_path: Path) -> None:
    pose_dir = tmp_path / "poses"
    pose_dir.mkdir()
    pose_path = pose_dir / "sample_b.npz"
    np.savez(
        pose_path,
        keypoints=_build_pose_clip(12),
        timestamps=np.arange(12, dtype=np.float32) * 0.5,
        frame_width=np.asarray([1920], dtype=np.int32),
        frame_height=np.asarray([1080], dtype=np.int32),
    )

    pose_manifest = tmp_path / "poses_override.jsonl"
    pose_manifest.write_text(
        json.dumps(
            {
                "sample_id": "sample_b",
                "pose_path": str(pose_path),
                "num_frames": 12,
                "external_label": "walk",
                "internal_label": "normal",
                "metadata": {"dataset": "unit"},
            },
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    interval_labels = tmp_path / "interval_labels.json"
    interval_labels.write_text(
        json.dumps(
            {
                "intervals": [
                    {
                        "sample_id": "sample_b",
                        "label": "near_fall",
                        "start_time": 1.5,
                        "end_time": 3.0,
                        "source": "review_queue:sample_b",
                        "sample_weight": 3.5,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    window_manifest = tmp_path / "windows_override.jsonl"
    build_window_manifest(
        pose_manifest_path=pose_manifest,
        output_path=window_manifest,
        spec=WindowSpec(window_size=4, stride=2, min_length=4),
        interval_labels_path=interval_labels,
        interval_min_overlap=0.5,
    )

    window_rows = load_jsonl(window_manifest)
    overridden = [row for row in window_rows if row["internal_label"] == "near_fall"]
    assert overridden
    assert overridden[0]["label_source"] == "review_queue:sample_b"
    assert overridden[0]["sample_weight"] == 3.5
