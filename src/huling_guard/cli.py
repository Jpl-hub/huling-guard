from __future__ import annotations

import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="huling-guard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-omnifall")
    prepare.add_argument("--split", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--dataset-id", default="simplexsigil2/omnifall")
    prepare.add_argument("--config-name")
    prepare.add_argument("--streaming", action="store_true")
    prepare.add_argument("--limit", type=int)
    prepare.add_argument("--include-datasets", nargs="*")

    build_windows = subparsers.add_parser("build-windows")
    build_windows.add_argument("--pose-manifest", required=True)
    build_windows.add_argument("--output", required=True)
    build_windows.add_argument("--window-size", type=int, default=64)
    build_windows.add_argument("--stride", type=int, default=16)
    build_windows.add_argument("--min-length", type=int, default=32)
    build_windows.add_argument("--interval-labels")
    build_windows.add_argument("--interval-min-overlap", type=float, default=0.5)

    cache_features = subparsers.add_parser("cache-features")
    cache_features.add_argument("--pose-manifest", required=True)
    cache_features.add_argument("--output-dir", required=True)
    cache_features.add_argument("--output-manifest", required=True)
    cache_features.add_argument("--kinematic-feature-set", default="v2")

    clip_bundle = subparsers.add_parser("prepare-clip-bundle")
    clip_bundle.add_argument("--csv")
    clip_bundle.add_argument("--clips-root", required=True)
    clip_bundle.add_argument("--output", required=True)

    download_ur_fall = subparsers.add_parser("download-ur-fall-rgb")
    download_ur_fall.add_argument("--target-dir", required=True)
    download_ur_fall.add_argument("--camera", choices=("cam0", "cam1", "both"), default="cam0")
    download_ur_fall.add_argument("--overwrite", action="store_true")

    prepare_ur_fall = subparsers.add_parser("prepare-ur-fall")
    prepare_ur_fall.add_argument("--source-root", required=True)
    prepare_ur_fall.add_argument("--output-video-dir", required=True)
    prepare_ur_fall.add_argument("--output-manifest", required=True)
    prepare_ur_fall.add_argument("--camera", choices=("cam0", "cam1", "both"), default="cam0")
    prepare_ur_fall.add_argument("--fps", type=float, default=18.0)
    prepare_ur_fall.add_argument("--overwrite", action="store_true")

    split_subjects = subparsers.add_parser("split-by-subject")
    split_subjects.add_argument("--input", required=True)
    split_subjects.add_argument("--train-output", required=True)
    split_subjects.add_argument("--val-output", required=True)
    split_subjects.add_argument("--val-subjects", nargs="+", required=True)
    split_subjects.add_argument("--subject-key", default="subject")

    split_pose = subparsers.add_parser("split-pose-by-raw")
    split_pose.add_argument("--raw-train", required=True)
    split_pose.add_argument("--raw-val", required=True)
    split_pose.add_argument("--pose-manifest", required=True)
    split_pose.add_argument("--train-output", required=True)
    split_pose.add_argument("--val-output", required=True)

    merge_manifests = subparsers.add_parser("merge-manifests")
    merge_manifests.add_argument("--inputs", nargs="+", required=True)
    merge_manifests.add_argument("--output", required=True)
    merge_manifests.add_argument("--dedupe-by", default="sample_id")

    validate_videos = subparsers.add_parser("validate-videos")
    validate_videos.add_argument("--manifest", required=True)
    validate_videos.add_argument("--valid-output", required=True)
    validate_videos.add_argument("--invalid-output", required=True)
    validate_videos.add_argument("--source-root")

    extract = subparsers.add_parser("extract-poses")
    extract.add_argument("--manifest", required=True)
    extract.add_argument("--output-dir", required=True)
    extract.add_argument("--output-manifest", required=True)
    extract.add_argument("--model-name", default="rtmo")
    extract.add_argument("--device", default="cuda:0")
    extract.add_argument("--frame-stride", type=int, default=1)
    extract.add_argument("--source-root")

    room_prior = subparsers.add_parser("build-room-prior")
    room_prior.add_argument("--media", required=True)
    room_prior.add_argument("--output", required=True)
    room_prior.add_argument("--grounding-config", required=True)
    room_prior.add_argument("--grounding-checkpoint", required=True)
    room_prior.add_argument("--sam2-config", required=True)
    room_prior.add_argument("--sam2-checkpoint", required=True)
    room_prior.add_argument("--device", default="cuda")

    serve_runtime = subparsers.add_parser("serve-runtime")
    serve_runtime.add_argument("--train-config", required=True)
    serve_runtime.add_argument("--runtime-config", required=True)
    serve_runtime.add_argument("--checkpoint", required=True)
    serve_runtime.add_argument("--scene-prior")
    serve_runtime.add_argument("--archive-root")
    serve_runtime.add_argument("--demo-video-root")
    serve_runtime.add_argument("--device", default="cuda")
    serve_runtime.add_argument("--host", default="0.0.0.0")
    serve_runtime.add_argument("--port", type=int, default=8000)

    serve_release = subparsers.add_parser("serve-release")
    serve_release.add_argument("--release-dir", required=True)
    serve_release.add_argument("--scene-prior")
    serve_release.add_argument("--archive-root")
    serve_release.add_argument("--demo-video-root")
    serve_release.add_argument("--device", default="cuda")
    serve_release.add_argument("--host", default="0.0.0.0")
    serve_release.add_argument("--port", type=int, default=8000)

    verify_release = subparsers.add_parser("verify-release")
    verify_release.add_argument("--release-dir", required=True)
    verify_release.add_argument("--output")

    run_video_inference = subparsers.add_parser("run-video-inference")
    run_video_inference.add_argument("--train-config", required=True)
    run_video_inference.add_argument("--runtime-config", required=True)
    run_video_inference.add_argument("--checkpoint", required=True)
    run_video_inference.add_argument("--input", required=True)
    run_video_inference.add_argument("--output-jsonl")
    run_video_inference.add_argument("--output-video")
    run_video_inference.add_argument("--output-report-json")
    run_video_inference.add_argument("--output-report-markdown")
    run_video_inference.add_argument("--scene-prior")
    run_video_inference.add_argument("--device", default="cuda")
    run_video_inference.add_argument("--rtmo-device", default="cuda:0")

    run_release_video_inference = subparsers.add_parser("run-release-video-inference")
    run_release_video_inference.add_argument("--release-dir", required=True)
    run_release_video_inference.add_argument("--input", required=True)
    run_release_video_inference.add_argument("--output-jsonl")
    run_release_video_inference.add_argument("--output-video")
    run_release_video_inference.add_argument("--output-report-json")
    run_release_video_inference.add_argument("--output-report-markdown")
    run_release_video_inference.add_argument("--scene-prior")
    run_release_video_inference.add_argument("--device", default="cuda")
    run_release_video_inference.add_argument("--rtmo-device", default="cuda:0")

    run_release_video_batch = subparsers.add_parser("run-release-video-batch")
    run_release_video_batch.add_argument("--release-dir", required=True)
    run_release_video_batch.add_argument("--manifest", required=True)
    run_release_video_batch.add_argument("--output-dir", required=True)
    run_release_video_batch.add_argument("--device", default="cuda")
    run_release_video_batch.add_argument("--rtmo-device", default="cuda:0")
    run_release_video_batch.add_argument("--write-video", action="store_true")
    run_release_video_batch.add_argument("--tolerance-seconds", type=float, default=2.0)

    calibrate_runtime = subparsers.add_parser("calibrate-runtime")
    calibrate_runtime.add_argument("--train-config", required=True)
    calibrate_runtime.add_argument("--runtime-config", required=True)
    calibrate_runtime.add_argument("--checkpoint", required=True)
    calibrate_runtime.add_argument("--output", required=True)
    calibrate_runtime.add_argument("--device", default="cuda")
    calibrate_runtime.add_argument("--threshold-step", type=float, default=0.02)

    evaluate_event_stream = subparsers.add_parser("evaluate-event-stream")
    evaluate_event_stream.add_argument("--predictions", required=True)
    evaluate_event_stream.add_argument("--annotations", required=True)
    evaluate_event_stream.add_argument("--output")
    evaluate_event_stream.add_argument("--tolerance-seconds", type=float, default=2.0)
    evaluate_event_stream.add_argument("--duration-seconds", type=float)

    evaluate_event_corpus = subparsers.add_parser("evaluate-event-corpus")
    evaluate_event_corpus.add_argument("--manifest", required=True)
    evaluate_event_corpus.add_argument("--output")
    evaluate_event_corpus.add_argument("--tolerance-seconds", type=float, default=2.0)

    summarize_session = subparsers.add_parser("summarize-session")
    summarize_session.add_argument("--predictions", required=True)
    summarize_session.add_argument("--output-json")
    summarize_session.add_argument("--output-markdown")
    summarize_session.add_argument("--session-name")
    summarize_session.add_argument("--source-path")

    import_session_reports = subparsers.add_parser("import-session-reports")
    import_session_reports.add_argument("--archive-root", required=True)
    import_session_reports.add_argument("--inputs", nargs="+", required=True)
    import_session_reports.add_argument("--output")

    train = subparsers.add_parser("train")
    train.add_argument("--config", required=True)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "prepare-omnifall":
        from huling_guard.data import export_omnifall_manifest

        export_omnifall_manifest(
            output_path=args.output,
            split=args.split,
            dataset_id=args.dataset_id,
            config_name=args.config_name,
            streaming=args.streaming,
            limit=args.limit,
            include_datasets=set(args.include_datasets) if args.include_datasets else None,
        )
        return

    if args.command == "build-windows":
        from huling_guard.data import WindowSpec, build_window_manifest

        build_window_manifest(
            pose_manifest_path=args.pose_manifest,
            output_path=args.output,
            spec=WindowSpec(
                window_size=args.window_size,
                stride=args.stride,
                min_length=args.min_length,
            ),
            interval_labels_path=args.interval_labels,
            interval_min_overlap=args.interval_min_overlap,
        )
        return

    if args.command == "cache-features":
        from huling_guard.data import build_feature_cache_manifest

        build_feature_cache_manifest(
            pose_manifest_path=args.pose_manifest,
            output_dir=args.output_dir,
            output_manifest_path=args.output_manifest,
            kinematic_feature_set=args.kinematic_feature_set,
        )
        return

    if args.command == "prepare-clip-bundle":
        from huling_guard.data import export_clip_bundle_manifest

        export_clip_bundle_manifest(
            csv_path=args.csv,
            clips_root=args.clips_root,
            output_path=args.output,
        )
        return

    if args.command == "download-ur-fall-rgb":
        from huling_guard.data import download_ur_fall_rgb_archives

        count = download_ur_fall_rgb_archives(
            target_dir=args.target_dir,
            camera=args.camera,
            overwrite=args.overwrite,
        )
        print(f"[downloaded] {count}", flush=True)
        return

    if args.command == "prepare-ur-fall":
        from huling_guard.data import prepare_ur_fall_manifest

        count = prepare_ur_fall_manifest(
            source_root=args.source_root,
            output_video_dir=args.output_video_dir,
            output_manifest_path=args.output_manifest,
            camera=args.camera,
            fps=args.fps,
            overwrite=args.overwrite,
        )
        print(f"[write] {count}", flush=True)
        return

    if args.command == "split-by-subject":
        from huling_guard.data import split_manifest_by_subject

        split_manifest_by_subject(
            input_path=args.input,
            train_output_path=args.train_output,
            val_output_path=args.val_output,
            val_subjects=set(args.val_subjects),
            subject_key=args.subject_key,
        )
        return

    if args.command == "split-pose-by-raw":
        from huling_guard.data import split_pose_manifest_by_raw_split

        split_pose_manifest_by_raw_split(
            raw_train_path=args.raw_train,
            raw_val_path=args.raw_val,
            pose_manifest_path=args.pose_manifest,
            train_output_path=args.train_output,
            val_output_path=args.val_output,
        )
        return

    if args.command == "merge-manifests":
        from huling_guard.data import merge_jsonl_manifests

        merge_jsonl_manifests(
            input_paths=args.inputs,
            output_path=args.output,
            dedupe_by=args.dedupe_by,
        )
        return

    if args.command == "validate-videos":
        from huling_guard.data import validate_manifest_videos

        validate_manifest_videos(
            manifest_path=args.manifest,
            valid_output_path=args.valid_output,
            invalid_output_path=args.invalid_output,
            source_root=args.source_root,
        )
        return

    if args.command == "extract-poses":
        from huling_guard.extract import PoseExtractionConfig, extract_from_manifest

        extract_from_manifest(
            PoseExtractionConfig(
                manifest_path=args.manifest,
                output_dir=args.output_dir,
                output_manifest_path=args.output_manifest,
                model_name=args.model_name,
                device=args.device,
                frame_stride=args.frame_stride,
                source_root=args.source_root,
            )
        )
        return

    if args.command == "build-room-prior":
        from huling_guard.room_prior import RoomPriorConfig, build_room_prior

        build_room_prior(
            RoomPriorConfig(
                media_path=args.media,
                output_path=args.output,
                grounding_config_path=args.grounding_config,
                grounding_checkpoint_path=args.grounding_checkpoint,
                sam2_model_config=args.sam2_config,
                sam2_checkpoint_path=args.sam2_checkpoint,
                device=args.device,
            )
        )
        return

    if args.command == "serve-runtime":
        from pathlib import Path

        from huling_guard.runtime import RuntimeLaunchConfig, serve_runtime

        serve_runtime(
            RuntimeLaunchConfig(
                train_config_path=Path(args.train_config),
                runtime_config_path=Path(args.runtime_config),
                checkpoint_path=Path(args.checkpoint),
                scene_prior_path=Path(args.scene_prior) if args.scene_prior else None,
                archive_root=Path(args.archive_root) if args.archive_root else None,
                demo_video_root=Path(args.demo_video_root) if args.demo_video_root else None,
                device=args.device,
                host=args.host,
                port=args.port,
            )
        )
        return

    if args.command == "serve-release":
        from pathlib import Path

        from huling_guard.runtime import (
            RuntimeLaunchConfig,
            load_runtime_release_bundle,
            serve_runtime,
        )

        bundle = load_runtime_release_bundle(args.release_dir)
        serve_runtime(
            RuntimeLaunchConfig(
                train_config_path=bundle.train_config_path,
                runtime_config_path=bundle.runtime_config_path,
                checkpoint_path=bundle.checkpoint_path,
                scene_prior_path=Path(args.scene_prior) if args.scene_prior else None,
                archive_root=Path(args.archive_root) if args.archive_root else None,
                demo_video_root=Path(args.demo_video_root) if args.demo_video_root else None,
                device=args.device,
                host=args.host,
                port=args.port,
            )
        )
        return

    if args.command == "verify-release":
        import json
        from pathlib import Path

        from huling_guard.runtime import (
            format_runtime_release_verification,
            verify_runtime_release_bundle,
        )

        summary = verify_runtime_release_bundle(args.release_dir)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(format_runtime_release_verification(summary), end="")
        return

    if args.command == "run-video-inference":
        from pathlib import Path

        from huling_guard.runtime import (
            RuntimeLaunchConfig,
            VideoInferenceConfig,
            run_video_inference,
        )

        run_video_inference(
            VideoInferenceConfig(
                launch=RuntimeLaunchConfig(
                    train_config_path=Path(args.train_config),
                    runtime_config_path=Path(args.runtime_config),
                    checkpoint_path=Path(args.checkpoint),
                    scene_prior_path=Path(args.scene_prior) if args.scene_prior else None,
                    device=args.device,
                ),
                input_path=Path(args.input),
                output_jsonl=Path(args.output_jsonl) if args.output_jsonl else None,
                output_video=Path(args.output_video) if args.output_video else None,
                output_report_json=Path(args.output_report_json) if args.output_report_json else None,
                output_report_markdown=Path(args.output_report_markdown) if args.output_report_markdown else None,
                rtmo_device=args.rtmo_device,
            )
        )
        return

    if args.command == "run-release-video-inference":
        from pathlib import Path

        from huling_guard.runtime import (
            RuntimeLaunchConfig,
            VideoInferenceConfig,
            load_runtime_release_bundle,
            run_video_inference,
        )

        bundle = load_runtime_release_bundle(args.release_dir)
        run_video_inference(
            VideoInferenceConfig(
                launch=RuntimeLaunchConfig(
                    train_config_path=bundle.train_config_path,
                    runtime_config_path=bundle.runtime_config_path,
                    checkpoint_path=bundle.checkpoint_path,
                    scene_prior_path=Path(args.scene_prior) if args.scene_prior else None,
                    device=args.device,
                ),
                input_path=Path(args.input),
                output_jsonl=Path(args.output_jsonl) if args.output_jsonl else None,
                output_video=Path(args.output_video) if args.output_video else None,
                output_report_json=Path(args.output_report_json) if args.output_report_json else None,
                output_report_markdown=Path(args.output_report_markdown) if args.output_report_markdown else None,
                rtmo_device=args.rtmo_device,
            )
        )
        return

    if args.command == "run-release-video-batch":
        import json

        from huling_guard.runtime import run_release_video_batch

        result = run_release_video_batch(
            release_dir=args.release_dir,
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            device=args.device,
            rtmo_device=args.rtmo_device,
            write_video=args.write_video,
            tolerance_seconds=args.tolerance_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2), end="")
        return

    if args.command == "calibrate-runtime":
        from huling_guard.calibration import (
            calibrate_runtime_thresholds,
            summarize_calibration_output,
        )

        output_path = calibrate_runtime_thresholds(
            train_config_path=args.train_config,
            runtime_config_path=args.runtime_config,
            checkpoint_path=args.checkpoint,
            output_path=args.output,
            device=args.device,
            threshold_step=args.threshold_step,
        )
        print(summarize_calibration_output(output_path), end="")
        return

    if args.command == "evaluate-event-stream":
        import json
        from pathlib import Path

        from huling_guard.evaluation import (
            format_event_evaluation,
            load_annotation_events,
            load_prediction_events,
            summarize_event_detection,
        )

        ground_truth_events, annotated_duration = load_annotation_events(args.annotations)
        predicted_events, inferred_duration = load_prediction_events(args.predictions)
        duration_seconds = args.duration_seconds
        if duration_seconds is None:
            duration_seconds = annotated_duration if annotated_duration is not None else inferred_duration
        summary = summarize_event_detection(
            ground_truth_events=ground_truth_events,
            predicted_events=predicted_events,
            tolerance_seconds=args.tolerance_seconds,
            duration_seconds=float(duration_seconds),
        )
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(format_event_evaluation(summary), end="")
        return

    if args.command == "evaluate-event-corpus":
        import json
        from pathlib import Path

        from huling_guard.evaluation import (
            format_event_corpus_evaluation,
            load_event_evaluation_manifest,
            summarize_event_corpus,
        )

        clips = load_event_evaluation_manifest(args.manifest)
        summary = summarize_event_corpus(
            clips=clips,
            tolerance_seconds=args.tolerance_seconds,
        )
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(format_event_corpus_evaluation(summary), end="")
        return

    if args.command == "summarize-session":
        import json
        from pathlib import Path

        from huling_guard.runtime import (
            format_session_report_markdown,
            summarize_session_jsonl,
            write_session_report,
        )

        report = summarize_session_jsonl(
            predictions_path=args.predictions,
            session_name=args.session_name,
            source_path=args.source_path,
        )
        write_session_report(
            report,
            output_json=Path(args.output_json) if args.output_json else None,
            output_markdown=Path(args.output_markdown) if args.output_markdown else None,
        )
        if args.output_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        print(format_session_report_markdown(report), end="")
        return

    if args.command == "import-session-reports":
        import json
        from pathlib import Path

        from huling_guard.runtime import RuntimeArchiveStore

        summary = RuntimeArchiveStore(args.archive_root).import_report_files(args.inputs)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2), end="")
        return

    if args.command == "train":
        from huling_guard.train import run_training

        run_training(args.config)
        return

    parser.error(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
