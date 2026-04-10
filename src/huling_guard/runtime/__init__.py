from __future__ import annotations

from importlib import import_module

__all__ = [
    "BatchVideoItem",
    "PipelineSnapshot",
    "RTMOPoseEstimator",
    "RealtimePipeline",
    "RuntimeArchiveStore",
    "RuntimeLaunchConfig",
    "RuntimeResources",
    "RuntimeReleaseBundle",
    "RoomPriorBuilder",
    "build_session_report",
    "VideoInferenceConfig",
    "build_runtime_pipeline",
    "build_runtime_pipeline_from_resources",
    "create_runtime_app",
    "format_runtime_release_verification",
    "format_session_report_markdown",
    "load_runtime_release_bundle",
    "load_runtime_resources",
    "load_session_snapshots",
    "load_batch_video_manifest",
    "run_release_video_batch",
    "run_video_inference",
    "run_video_inference_with_runtime",
    "serve_runtime",
    "summarize_session_jsonl",
    "verify_runtime_release_bundle",
    "write_session_report",
]

_EXPORTS = {
    "RuntimeArchiveStore": ("huling_guard.runtime.archive_store", "RuntimeArchiveStore"),
    "BatchVideoItem": ("huling_guard.runtime.batch_manifest", "BatchVideoItem"),
    "PipelineSnapshot": ("huling_guard.runtime.pipeline", "PipelineSnapshot"),
    "RTMOPoseEstimator": ("huling_guard.runtime.rtmo", "RTMOPoseEstimator"),
    "RealtimePipeline": ("huling_guard.runtime.pipeline", "RealtimePipeline"),
    "RuntimeLaunchConfig": ("huling_guard.runtime.service", "RuntimeLaunchConfig"),
    "RuntimeResources": ("huling_guard.runtime.service", "RuntimeResources"),
    "RuntimeReleaseBundle": ("huling_guard.runtime.release", "RuntimeReleaseBundle"),
    "RoomPriorBuilder": ("huling_guard.runtime.scene_init", "RoomPriorBuilder"),
    "build_session_report": ("huling_guard.runtime.session_report", "build_session_report"),
    "VideoInferenceConfig": ("huling_guard.runtime.video_inference", "VideoInferenceConfig"),
    "build_runtime_pipeline_from_resources": (
        "huling_guard.runtime.service",
        "build_runtime_pipeline_from_resources",
    ),
    "build_runtime_pipeline": ("huling_guard.runtime.service", "build_runtime_pipeline"),
    "create_runtime_app": ("huling_guard.runtime.api", "create_runtime_app"),
    "load_runtime_resources": ("huling_guard.runtime.service", "load_runtime_resources"),
    "load_runtime_release_bundle": ("huling_guard.runtime.release", "load_runtime_release_bundle"),
    "verify_runtime_release_bundle": ("huling_guard.runtime.release", "verify_runtime_release_bundle"),
    "format_runtime_release_verification": (
        "huling_guard.runtime.release",
        "format_runtime_release_verification",
    ),
    "load_batch_video_manifest": ("huling_guard.runtime.batch_manifest", "load_batch_video_manifest"),
    "run_release_video_batch": ("huling_guard.runtime.batch_inference", "run_release_video_batch"),
    "run_video_inference": ("huling_guard.runtime.video_inference", "run_video_inference"),
    "run_video_inference_with_runtime": (
        "huling_guard.runtime.video_inference",
        "run_video_inference_with_runtime",
    ),
    "serve_runtime": ("huling_guard.runtime.service", "serve_runtime"),
    "format_session_report_markdown": (
        "huling_guard.runtime.session_report",
        "format_session_report_markdown",
    ),
    "load_session_snapshots": ("huling_guard.runtime.session_report", "load_session_snapshots"),
    "summarize_session_jsonl": ("huling_guard.runtime.session_report", "summarize_session_jsonl"),
    "write_session_report": ("huling_guard.runtime.session_report", "write_session_report"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
