from __future__ import annotations

from importlib import import_module

__all__ = [
    "PoseCoverageSummary",
    "SubjectSplitResult",
    "WindowSpec",
    "build_window_manifest",
    "build_feature_cache_manifest",
    "export_missing_pose_entries",
    "export_clip_bundle_manifest",
    "export_omnifall_manifest",
    "filter_manifest_by_sample_ids",
    "load_omnifall_split",
    "merge_jsonl_manifests",
    "download_ur_fall_rgb_archives",
    "build_transition_interval_labels",
    "prepare_ur_fall_manifest",
    "split_manifest_by_subject",
    "split_pose_manifest_by_raw_split",
    "summarize_pose_manifest_coverage",
    "validate_manifest_videos",
]

_EXPORTS = {
    "PoseCoverageSummary": ("huling_guard.data.coverage", "PoseCoverageSummary"),
    "SubjectSplitResult": ("huling_guard.data.splits", "SubjectSplitResult"),
    "WindowSpec": ("huling_guard.data.windows", "WindowSpec"),
    "build_window_manifest": ("huling_guard.data.windows", "build_window_manifest"),
    "build_feature_cache_manifest": (
        "huling_guard.data.feature_cache",
        "build_feature_cache_manifest",
    ),
    "export_missing_pose_entries": (
        "huling_guard.data.coverage",
        "export_missing_pose_entries",
    ),
    "export_clip_bundle_manifest": ("huling_guard.data.clip_bundle", "export_clip_bundle_manifest"),
    "export_omnifall_manifest": ("huling_guard.data.omnifall", "export_omnifall_manifest"),
    "filter_manifest_by_sample_ids": ("huling_guard.data.splits", "filter_manifest_by_sample_ids"),
    "load_omnifall_split": ("huling_guard.data.omnifall", "load_omnifall_split"),
    "merge_jsonl_manifests": ("huling_guard.data.manifests", "merge_jsonl_manifests"),
    "download_ur_fall_rgb_archives": (
        "huling_guard.data.ur_fall",
        "download_ur_fall_rgb_archives",
    ),
    "build_transition_interval_labels": (
        "huling_guard.data.transition_mining",
        "build_transition_interval_labels",
    ),
    "prepare_ur_fall_manifest": ("huling_guard.data.ur_fall", "prepare_ur_fall_manifest"),
    "split_manifest_by_subject": ("huling_guard.data.splits", "split_manifest_by_subject"),
    "split_pose_manifest_by_raw_split": (
        "huling_guard.data.splits",
        "split_pose_manifest_by_raw_split",
    ),
    "summarize_pose_manifest_coverage": (
        "huling_guard.data.coverage",
        "summarize_pose_manifest_coverage",
    ),
    "validate_manifest_videos": (
        "huling_guard.data.video_validation",
        "validate_manifest_videos",
    ),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
