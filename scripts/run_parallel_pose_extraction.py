from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
    return len(rows)


def shard_rows(rows: list[dict[str, Any]], num_shards: int) -> list[list[dict[str, Any]]]:
    shards = [[] for _ in range(num_shards)]
    for index, row in enumerate(rows):
        shards[index % num_shards].append(row)
    return shards


def merge_pose_manifests(
    *,
    merged_output_manifest: Path,
    shard_manifest_dir: Path,
) -> int:
    merged_rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_rows(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            sample_id = str(row.get("sample_id", "")).strip()
            if not sample_id or sample_id in seen:
                continue
            seen.add(sample_id)
            merged_rows.append(row)

    if merged_output_manifest.is_file():
        add_rows(load_jsonl(merged_output_manifest))
    if shard_manifest_dir.is_dir():
        for shard_manifest in sorted(shard_manifest_dir.glob("*.jsonl")):
            add_rows(load_jsonl(shard_manifest))

    return write_jsonl(merged_output_manifest, merged_rows)


def prewarm_pose_estimator(
    *,
    python_bin: str,
    repo_root: Path,
    model_name: str,
    device: str,
    env: dict[str, str],
) -> None:
    command = [
        python_bin,
        "-c",
        (
            "from huling_guard.runtime.rtmo import RTMOPoseEstimator; "
            f"RTMOPoseEstimator(model_name={model_name!r}, device={device!r}); "
            "print('pose_estimator_ready', flush=True)"
        ),
    ]
    subprocess.run(command, cwd=repo_root, env=env, check=True)


def collect_completed_sample_ids(
    *,
    merged_output_manifest: Path,
    shard_manifest_dir: Path,
) -> tuple[set[str], dict[str, int]]:
    completed_ids: set[str] = set()
    counts = {"merged_manifest_rows": 0, "shard_manifest_rows": 0}

    if merged_output_manifest.is_file():
        merged_rows = load_jsonl(merged_output_manifest)
        counts["merged_manifest_rows"] = len(merged_rows)
        completed_ids.update(str(row["sample_id"]) for row in merged_rows)

    if shard_manifest_dir.is_dir():
        for shard_manifest in sorted(shard_manifest_dir.glob("*.jsonl")):
            shard_rows_payload = load_jsonl(shard_manifest)
            counts["shard_manifest_rows"] += len(shard_rows_payload)
            completed_ids.update(str(row["sample_id"]) for row in shard_rows_payload)

    return completed_ids, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--merged-output-manifest", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--model-name", default="rtmo")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--frame-stride", type=int, default=1)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    manifest_path = args.manifest.resolve()
    output_dir = args.output_dir.resolve()
    merged_output_manifest = args.merged_output_manifest.resolve()
    work_dir = args.work_dir.resolve()
    workers = max(1, args.workers)

    shard_root = work_dir / "manifests"
    log_root = work_dir / "logs"
    output_manifest_root = work_dir / "pose_manifests"
    shard_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    output_manifest_root.mkdir(parents=True, exist_ok=True)

    rows = load_jsonl(manifest_path)
    completed_ids, completed_counts = collect_completed_sample_ids(
        merged_output_manifest=merged_output_manifest,
        shard_manifest_dir=output_manifest_root,
    )
    remaining_rows = [row for row in rows if str(row.get("sample_id")) not in completed_ids]

    shard_groups = [group for group in shard_rows(remaining_rows, workers) if group]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    env["OMP_NUM_THREADS"] = "8"
    env["MKL_NUM_THREADS"] = "8"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["NUMEXPR_NUM_THREADS"] = "1"

    prewarm_pose_estimator(
        python_bin=args.python,
        repo_root=repo_root,
        model_name=args.model_name,
        device=args.device,
        env=env,
    )

    launches: list[dict[str, Any]] = []
    processes: list[tuple[subprocess.Popen[bytes], dict[str, Any]]] = []
    for shard_id, shard_rows_payload in enumerate(shard_groups):
        shard_manifest = shard_root / f"shard_{shard_id:02d}.jsonl"
        shard_output_manifest = output_manifest_root / f"poses_shard_{shard_id:02d}.jsonl"
        shard_log = log_root / f"worker_{shard_id:02d}.log"
        write_jsonl(shard_manifest, shard_rows_payload)

        command = [
            args.python,
            "-m",
            "huling_guard.cli",
            "extract-poses",
            "--manifest",
            str(shard_manifest),
            "--output-dir",
            str(output_dir),
            "--output-manifest",
            str(shard_output_manifest),
            "--model-name",
            args.model_name,
            "--device",
            args.device,
            "--frame-stride",
            str(args.frame_stride),
        ]
        if args.source_root is not None:
            command.extend(["--source-root", str(args.source_root.resolve())])

        with shard_log.open("ab") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=repo_root,
                env=env,
                stdout=log_handle,
                stderr=log_handle,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        launches.append(
            {
                "worker_id": shard_id,
                "pid": process.pid,
                "rows": len(shard_rows_payload),
                "manifest": str(shard_manifest),
                "output_manifest": str(shard_output_manifest),
                "log": str(shard_log),
            }
        )
        processes.append((process, launches[-1]))
        print(
            f"[launch] worker={shard_id} pid={process.pid} rows={len(shard_rows_payload)} log={shard_log}",
            flush=True,
        )

    failed_workers: list[dict[str, Any]] = []
    for process, launch in processes:
        return_code = process.wait()
        launch["return_code"] = return_code
        launch["finished_at"] = time.time()
        if return_code != 0:
            failed_workers.append(
                {
                    "worker_id": launch["worker_id"],
                    "pid": launch["pid"],
                    "return_code": return_code,
                    "log": launch["log"],
                }
            )

    merged_rows = 0
    if not failed_workers:
        merged_rows = merge_pose_manifests(
            merged_output_manifest=merged_output_manifest,
            shard_manifest_dir=output_manifest_root,
        )

    summary = {
        "manifest": str(manifest_path),
        "merged_output_manifest": str(merged_output_manifest),
        "total_rows": len(rows),
        "completed_rows": len(completed_ids),
        "remaining_rows": len(remaining_rows),
        "completed_from_merged_manifest_rows": completed_counts["merged_manifest_rows"],
        "completed_from_shard_manifest_rows": completed_counts["shard_manifest_rows"],
        "workers": len(launches),
        "launches": launches,
        "merged_rows": merged_rows,
        "failed_workers": failed_workers,
    }
    summary_path = work_dir / "launch_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[summary] {summary_path}", flush=True)
    if failed_workers:
        failed_ids = ", ".join(f"worker={item['worker_id']} rc={item['return_code']}" for item in failed_workers)
        raise RuntimeError(f"parallel pose extraction failed: {failed_ids}")


if __name__ == "__main__":
    main()
