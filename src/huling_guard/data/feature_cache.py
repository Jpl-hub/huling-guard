from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from huling_guard.contracts import ScenePrior
from huling_guard.data.pose_io import load_pose_archive, normalize_pose_archive_coords
from huling_guard.features import (
    build_kinematic_features,
    build_scene_relation_features,
    get_kinematic_feature_dim,
    normalize_pose_sequence,
    resolve_kinematic_feature_set,
)


def _load_completed_samples(output_manifest_path: Path) -> set[str]:
    if not output_manifest_path.is_file():
        return set()
    completed: set[str] = set()
    with output_manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = str(payload.get("sample_id", "")).strip()
            if sample_id:
                completed.add(sample_id)
    return completed


def build_feature_cache_manifest(
    pose_manifest_path: str | Path,
    output_dir: str | Path,
    output_manifest_path: str | Path,
    *,
    kinematic_feature_set: str | None = None,
) -> int:
    pose_manifest = Path(pose_manifest_path)
    output_root = Path(output_dir)
    output_manifest = Path(output_manifest_path)
    normalized_feature_set = resolve_kinematic_feature_set(kinematic_feature_set)
    expected_kinematic_dim = get_kinematic_feature_dim(normalized_feature_set)
    output_root.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    completed_samples = _load_completed_samples(output_manifest)
    mode = "a" if output_manifest.exists() else "w"
    written = 0

    with pose_manifest.open("r", encoding="utf-8") as reader, output_manifest.open(
        mode, encoding="utf-8"
    ) as writer:
        for line in reader:
            if not line.strip():
                continue
            entry = json.loads(line)
            sample_id = str(entry["sample_id"])
            feature_path = output_root / f"{sample_id}.npz"
            if sample_id in completed_samples:
                if not feature_path.is_file():
                    raise FileNotFoundError(
                        f"feature manifest already contains {sample_id} but feature file is missing: {feature_path}"
                    )
                continue

            keypoints, payload = load_pose_archive(entry["pose_path"])
            keypoints = normalize_pose_archive_coords(keypoints, payload)
            scene_prior = (
                ScenePrior.load(entry["scene_prior_path"])
                if entry.get("scene_prior_path")
                else None
            )

            poses = normalize_pose_sequence(keypoints).astype(np.float32)
            kinematics = build_kinematic_features(
                keypoints,
                feature_set=normalized_feature_set,
            ).astype(np.float32)
            scene_features = build_scene_relation_features(keypoints, scene_prior).astype(np.float32)

            np.savez(
                feature_path,
                poses=poses,
                kinematics=kinematics,
                scene_features=scene_features,
            )
            payload = {
                "sample_id": sample_id,
                "feature_path": str(feature_path),
                "pose_path": entry["pose_path"],
                "num_frames": int(keypoints.shape[0]),
                "external_label": entry["external_label"],
                "internal_label": entry["internal_label"],
                "kinematic_feature_set": normalized_feature_set,
                "kinematic_dim": expected_kinematic_dim,
                "scene_prior_path": entry.get("scene_prior_path"),
                "metadata": entry.get("metadata", {}),
                "video_ref": entry.get("video_ref"),
            }
            writer.write(json.dumps(payload, ensure_ascii=True) + "\n")
            written += 1
            if written <= 3 or written % 50 == 0:
                print(f"[feature-cache] written={written} sample_id={sample_id}", flush=True)
    return written
