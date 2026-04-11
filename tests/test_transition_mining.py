from pathlib import Path

import numpy as np

from huling_guard.data.transition_mining import (
    TransitionMiningConfig,
    build_transition_interval_labels,
    mine_transition_intervals,
)


def _build_pose_sequence(hip_y_values: list[float], *, recover: bool) -> np.ndarray:
    frames = len(hip_y_values)
    keypoints = np.zeros((frames, 17, 3), dtype=np.float32)
    keypoints[:, :, 2] = 1.0
    for index, hip_y in enumerate(hip_y_values):
        shoulder_y = hip_y - 0.16
        ankle_y = hip_y + 0.18
        shoulder_x_left = 0.42
        shoulder_x_right = 0.58
        if 5 <= index <= 10:
            shoulder_x_left -= 0.03
            shoulder_x_right += 0.03
        if recover and index >= 12:
            shoulder_x_left -= 0.015
            shoulder_x_right += 0.015

        keypoints[index, 5, :2] = [shoulder_x_left, shoulder_y]
        keypoints[index, 6, :2] = [shoulder_x_right, shoulder_y]
        keypoints[index, 11, :2] = [0.46, hip_y]
        keypoints[index, 12, :2] = [0.54, hip_y]
        keypoints[index, 15, :2] = [0.47, ankle_y]
        keypoints[index, 16, :2] = [0.53, ankle_y]
    return keypoints


def test_mine_transition_intervals_extracts_near_fall_and_recovery() -> None:
    keypoints = _build_pose_sequence(
        [0.34, 0.34, 0.35, 0.35, 0.38, 0.44, 0.54, 0.65, 0.73, 0.79, 0.81, 0.8, 0.76, 0.69, 0.61, 0.53, 0.47, 0.43],
        recover=True,
    )
    timestamps = np.arange(keypoints.shape[0], dtype=np.float32) * 0.1

    intervals = mine_transition_intervals(
        sample_id="fall_case",
        internal_label="fall",
        keypoints=keypoints,
        timestamps=timestamps,
        config=TransitionMiningConfig(),
    )

    labels = [item["label"] for item in intervals]
    assert "near_fall" in labels
    assert "recovery" in labels
    near_fall = next(item for item in intervals if item["label"] == "near_fall")
    recovery = next(item for item in intervals if item["label"] == "recovery")
    assert near_fall["end_time"] > near_fall["start_time"]
    assert recovery["end_time"] > recovery["start_time"]
    assert near_fall["end_time"] <= recovery["start_time"]


def test_mine_transition_intervals_skips_normal_motion() -> None:
    keypoints = _build_pose_sequence(
        [0.34, 0.341, 0.342, 0.34, 0.341, 0.343, 0.344, 0.343, 0.342, 0.341, 0.34, 0.339, 0.34, 0.341, 0.34, 0.339],
        recover=False,
    )
    timestamps = np.arange(keypoints.shape[0], dtype=np.float32) * 0.1

    intervals = mine_transition_intervals(
        sample_id="normal_case",
        internal_label="normal",
        keypoints=keypoints,
        timestamps=timestamps,
        config=TransitionMiningConfig(),
    )

    assert intervals == []


def test_build_transition_interval_labels_writes_summary(tmp_path: Path) -> None:
    pose_path = tmp_path / "fall_case.npz"
    keypoints = _build_pose_sequence(
        [0.34, 0.34, 0.35, 0.35, 0.38, 0.44, 0.54, 0.65, 0.73, 0.79, 0.81, 0.8, 0.76, 0.69, 0.61, 0.53, 0.47, 0.43],
        recover=True,
    )
    np.savez(
        pose_path,
        keypoints=keypoints,
        timestamps=np.arange(keypoints.shape[0], dtype=np.float32) * 0.1,
        frame_width=np.asarray([1], dtype=np.int32),
        frame_height=np.asarray([1], dtype=np.int32),
    )

    manifest_path = tmp_path / "poses.jsonl"
    manifest_path.write_text(
        '{"sample_id":"fall_case","pose_path":"%s","num_frames":18,"external_label":"fall","internal_label":"fall"}\n'
        % str(pose_path),
        encoding="utf-8",
    )

    output_path = tmp_path / "intervals.json"
    summary = build_transition_interval_labels(
        pose_manifest_path=manifest_path,
        output_path=output_path,
        config=TransitionMiningConfig(),
    )

    assert output_path.is_file()
    assert summary["samples_scanned"] == 1
    assert summary["eligible_samples"] == 1
    assert summary["interval_count"] >= 1
    assert summary["per_label"]["near_fall"] >= 1
