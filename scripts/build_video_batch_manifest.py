from __future__ import annotations

import argparse
import json
from pathlib import Path

from huling_guard.review import build_video_batch_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--internal-labels", nargs="*")
    parser.add_argument("--dataset")
    parser.add_argument("--scene-prior")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    payload = build_video_batch_manifest(
        args.source_manifest.resolve(),
        internal_labels=tuple(args.internal_labels) if args.internal_labels else None,
        dataset=args.dataset,
        scene_prior=args.scene_prior,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {args.output}", flush=True)


if __name__ == "__main__":
    main()
