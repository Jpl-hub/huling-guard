from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


def _run(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    print("[run]", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def _count_jsonl_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path("/root/autodl-tmp/huling-data"))
    parser.add_argument("--camera", choices=("cam0", "cam1", "both"), default="cam0")
    parser.add_argument("--fps", type=float, default=18.0)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--overwrite-download", action="store_true")
    parser.add_argument("--overwrite-video", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()

    raw_root = data_root / "raw" / "ur_fall"
    archive_root = raw_root / "archives"
    video_root = raw_root / "videos"
    manifest_root = data_root / "manifests"
    processed_root = data_root / "processed"
    work_root = processed_root / "parallel_extract_ur_fall"
    pose_root = processed_root / "pose_npz_ur_fall"

    archive_root.mkdir(parents=True, exist_ok=True)
    video_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)
    processed_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    pose_root.mkdir(parents=True, exist_ok=True)

    raw_manifest = manifest_root / "ur_fall_raw.jsonl"
    valid_manifest = manifest_root / "ur_fall_valid.jsonl"
    invalid_manifest = manifest_root / "ur_fall_invalid.jsonl"
    pose_manifest = processed_root / "poses_ur_fall.jsonl"

    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS") or "8"
    env["MKL_NUM_THREADS"] = env.get("MKL_NUM_THREADS") or "8"
    env["OPENBLAS_NUM_THREADS"] = env.get("OPENBLAS_NUM_THREADS") or "1"
    env["NUMEXPR_NUM_THREADS"] = env.get("NUMEXPR_NUM_THREADS") or "1"

    cli = [args.python, "-m", "huling_guard.cli"]

    skipped_download = False
    skipped_prepare = False
    skipped_validate = False

    if not args.skip_download and not (args.resume and raw_manifest.is_file()):
        command = cli + [
            "download-ur-fall-rgb",
            "--target-dir",
            str(archive_root),
            "--camera",
            args.camera,
        ]
        if args.overwrite_download:
            command.append("--overwrite")
        _run(command, cwd=repo_root, env=env)
    else:
        skipped_download = True

    if args.resume and raw_manifest.is_file() and _count_jsonl_rows(raw_manifest) > 0 and not args.overwrite_video:
        skipped_prepare = True
    else:
        prepare_command = cli + [
            "prepare-ur-fall",
            "--source-root",
            str(archive_root),
            "--output-video-dir",
            str(video_root),
            "--output-manifest",
            str(raw_manifest),
            "--camera",
            args.camera,
            "--fps",
            str(args.fps),
        ]
        if args.overwrite_video:
            prepare_command.append("--overwrite")
        _run(prepare_command, cwd=repo_root, env=env)

    if args.resume and valid_manifest.is_file() and invalid_manifest.is_file():
        skipped_validate = True
    else:
        _run(
            cli
            + [
                "validate-videos",
                "--manifest",
                str(raw_manifest),
                "--valid-output",
                str(valid_manifest),
                "--invalid-output",
                str(invalid_manifest),
            ],
            cwd=repo_root,
            env=env,
        )

    if not args.skip_extract:
        _run(
            [
                args.python,
                "scripts/run_parallel_pose_extraction.py",
                "--python",
                args.python,
                "--repo-root",
                str(repo_root),
                "--manifest",
                str(valid_manifest),
                "--output-dir",
                str(pose_root),
                "--merged-output-manifest",
                str(pose_manifest),
                "--work-dir",
                str(work_root),
                "--workers",
                str(args.workers),
                "--device",
                args.device,
                "--frame-stride",
                str(args.frame_stride),
            ],
            cwd=repo_root,
            env=env,
        )

    summary = {
        "dataset": "ur_fall",
        "camera": args.camera,
        "raw_manifest": str(raw_manifest),
        "valid_manifest": str(valid_manifest),
        "invalid_manifest": str(invalid_manifest),
        "pose_manifest": str(pose_manifest),
        "raw_rows": _count_jsonl_rows(raw_manifest),
        "valid_rows": _count_jsonl_rows(valid_manifest),
        "invalid_rows": _count_jsonl_rows(invalid_manifest),
        "pose_rows": _count_jsonl_rows(pose_manifest),
        "video_root": str(video_root),
        "archive_root": str(archive_root),
        "workers": args.workers,
        "device": args.device,
        "resume": args.resume,
        "skipped_download": skipped_download,
        "skipped_prepare": skipped_prepare,
        "skipped_validate": skipped_validate,
    }
    summary_path = manifest_root / "ur_fall_prepare_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[summary] {summary_path}", flush=True)


if __name__ == "__main__":
    main()
