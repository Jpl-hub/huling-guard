from __future__ import annotations

import numpy as np

from huling_guard.contracts import ScenePrior, SceneRegion

LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_ANKLE = 15
RIGHT_ANKLE = 16


def _midpoint(keypoints: np.ndarray, left_idx: int, right_idx: int) -> np.ndarray:
    return (keypoints[:, left_idx, :2] + keypoints[:, right_idx, :2]) / 2.0


def _keypoints_are_normalized(keypoints: np.ndarray) -> bool:
    if keypoints.size == 0:
        return False
    coords = np.asarray(keypoints[:, :, :2], dtype=np.float32)
    finite_coords = coords[np.isfinite(coords)]
    if finite_coords.size == 0:
        return False
    return float(np.max(np.abs(finite_coords))) <= 2.0


def _regions_are_normalized(regions: tuple[SceneRegion, ...]) -> bool:
    if not regions:
        return False
    max_coord = max(max(abs(value) for value in region.bbox) for region in regions)
    return float(max_coord) <= 2.0


def _normalize_region_bbox(region: SceneRegion, scene_prior: ScenePrior) -> tuple[float, float, float, float]:
    width = max(float(scene_prior.frame_width), 1.0)
    height = max(float(scene_prior.frame_height), 1.0)
    x1, y1, x2, y2 = region.bbox
    return (x1 / width, y1 / height, x2 / width, y2 / height)


def _prepare_regions(
    regions: tuple[SceneRegion, ...],
    scene_prior: ScenePrior,
    *,
    normalize: bool,
) -> tuple[tuple[tuple[float, float, float, float], float], ...]:
    if not normalize:
        return tuple((region.bbox, float(region.score)) for region in regions)
    return tuple(
        (_normalize_region_bbox(region, scene_prior), float(region.score))
        for region in regions
    )


def _support_score(
    regions: tuple[tuple[tuple[float, float, float, float], float], ...],
    points: np.ndarray,
) -> np.ndarray:
    scores = np.zeros(points.shape[0], dtype=np.float32)
    for frame_idx, (x, y) in enumerate(points):
        inside = 0.0
        for bbox, score in regions:
            x1, y1, x2, y2 = bbox
            if x1 <= float(x) <= x2 and y1 <= float(y) <= y2:
                inside = max(inside, score)
        scores[frame_idx] = inside
    return scores


def _distance_score(
    regions: tuple[tuple[tuple[float, float, float, float], float], ...],
    points: np.ndarray,
) -> np.ndarray:
    if not regions:
        return np.ones(points.shape[0], dtype=np.float32)
    distances = np.ones(points.shape[0], dtype=np.float32)
    for frame_idx, (x, y) in enumerate(points):
        best = min(
            float(
                np.hypot(
                    max(bbox[0] - float(x), 0.0, float(x) - bbox[2]),
                    max(bbox[1] - float(y), 0.0, float(y) - bbox[3]),
                )
            )
            for bbox, _ in regions
        )
        distances[frame_idx] = np.clip(best, 0.0, 1.0)
    return distances


def build_scene_relation_features(
    keypoints: np.ndarray,
    scene_prior: ScenePrior | None,
) -> np.ndarray:
    keypoints = np.asarray(keypoints, dtype=np.float32)
    if scene_prior is None:
        return np.zeros((keypoints.shape[0], 8), dtype=np.float32)

    torso = (_midpoint(keypoints, LEFT_SHOULDER, RIGHT_SHOULDER) + _midpoint(
        keypoints, LEFT_HIP, RIGHT_HIP
    )) / 2.0
    ankles = _midpoint(keypoints, LEFT_ANKLE, RIGHT_ANKLE)
    normalize_regions = _keypoints_are_normalized(keypoints) and not _regions_are_normalized(
        scene_prior.regions
    )

    floor_regions = _prepare_regions(scene_prior.find("floor"), scene_prior, normalize=normalize_regions)
    bed_regions = _prepare_regions(scene_prior.find("bed"), scene_prior, normalize=normalize_regions)
    sofa_regions = _prepare_regions(scene_prior.find("sofa"), scene_prior, normalize=normalize_regions)
    chair_regions = _prepare_regions(scene_prior.find("chair"), scene_prior, normalize=normalize_regions)
    hazard_regions = _prepare_regions(
        scene_prior.find("table", "cabinet", "hazard", "desk"),
        scene_prior,
        normalize=normalize_regions,
    )

    features = np.stack(
        [
            _support_score(floor_regions, ankles),
            _support_score(bed_regions, ankles),
            _support_score(sofa_regions, ankles),
            _support_score(chair_regions, ankles),
            _support_score(bed_regions, torso),
            _support_score(sofa_regions, torso),
            _support_score(chair_regions, torso),
            _distance_score(hazard_regions, torso),
        ],
        axis=-1,
    )
    return features.astype(np.float32)
