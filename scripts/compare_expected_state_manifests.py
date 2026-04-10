from __future__ import annotations

import argparse
import json
from pathlib import Path

from huling_guard.runtime.expected_state_compare import (
    build_expected_state_comparison,
    build_expected_state_comparison_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--expected-state", default="normal")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    payload = build_expected_state_comparison(
        baseline_manifest_path=args.baseline_manifest.resolve(),
        candidate_manifest_path=args.candidate_manifest.resolve(),
        expected_state=args.expected_state,
    )
    markdown = build_expected_state_comparison_markdown(payload)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {args.output_json}", flush=True)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
