from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from evaluate_sample_classification import evaluate_sample_classification
from huling_guard.calibration import calibrate_runtime_thresholds


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_checkpoint_path(run_dir: Path, checkpoint_path: str | Path) -> Path:
    path = Path(checkpoint_path)
    if path.is_absolute():
        return path
    return (run_dir / path).resolve()


def _summarize_sample_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "num_samples": int(summary.get("num_samples", 0)),
        "num_windows": int(summary.get("num_windows", 0)),
        "accuracy": float(summary.get("accuracy", 0.0)),
        "macro_f1": float(summary.get("macro_f1", 0.0)),
        "weighted_f1": float(summary.get("weighted_f1", 0.0)),
        "per_class": summary.get("per_class", {}),
    }


def _rank_candidate(candidate: dict[str, Any]) -> tuple[float, ...]:
    sample_metrics = candidate["sample_metrics"]
    per_class = sample_metrics.get("per_class", {})
    train_metrics = candidate["train_metrics"]
    return (
        float(sample_metrics.get("macro_f1", 0.0)),
        float(sample_metrics.get("weighted_f1", 0.0)),
        float(sample_metrics.get("accuracy", 0.0)),
        float(per_class.get("fall", {}).get("f1", 0.0)),
        float(per_class.get("recovery", {}).get("f1", 0.0)),
        float(per_class.get("prolonged_lying", {}).get("f1", 0.0)),
        float(train_metrics.get("macro_f1", 0.0)),
        float(candidate.get("metric_value", 0.0)),
        float(candidate.get("epoch", 0)),
    )


def _build_candidates(
    *,
    run_dir: Path,
    train_summary: dict[str, Any],
    history: list[dict[str, Any]],
    train_config_path: Path,
    device: str,
) -> list[dict[str, Any]]:
    history_by_epoch = {
        int(entry["epoch"]): (entry["eval"] if "eval" in entry else entry["train"])
        for entry in history
    }
    configured_candidates = train_summary.get("candidate_checkpoints", [])
    if not configured_candidates:
        configured_candidates = [
            {
                "epoch": int(train_summary.get("best_epoch") or 0),
                "selection_metric": str(train_summary.get("selection_metric") or "macro_f1"),
                "selection_scope": "eval",
                "metric_value": float(train_summary.get("best_metrics", {}).get("macro_f1", 0.0)),
                "checkpoint_path": str(run_dir / "best.pt"),
            }
        ]

    candidates: list[dict[str, Any]] = []
    for configured in configured_candidates:
        epoch = int(configured.get("epoch", 0))
        checkpoint_path = _resolve_checkpoint_path(run_dir, configured["checkpoint_path"])
        if not checkpoint_path.is_file():
            raise FileNotFoundError(checkpoint_path)
        sample_summary = evaluate_sample_classification(
            train_config_path=train_config_path,
            checkpoint_path=checkpoint_path,
            device=device,
        )
        candidates.append(
            {
                "epoch": epoch,
                "selection_metric": str(configured.get("selection_metric") or "macro_f1"),
                "selection_scope": str(configured.get("selection_scope") or "eval"),
                "metric_value": float(configured.get("metric_value", 0.0)),
                "checkpoint_path": str(checkpoint_path),
                "train_metrics": history_by_epoch.get(epoch, {}),
                "sample_metrics": _summarize_sample_metrics(sample_summary),
                "ranking_key": list(_rank_candidate(
                    {
                        "epoch": epoch,
                        "metric_value": float(configured.get("metric_value", 0.0)),
                        "train_metrics": history_by_epoch.get(epoch, {}),
                        "sample_metrics": _summarize_sample_metrics(sample_summary),
                    }
                )),
            }
        )
    return candidates


def select_deployment_checkpoint(
    *,
    run_dir: str | Path,
    train_config_path: str | Path,
    runtime_template_path: str | Path,
    runtime_output_path: str | Path,
    device: str = "cuda",
    selected_checkpoint_output: str | Path | None = None,
) -> dict[str, Any]:
    resolved_run_dir = Path(run_dir).resolve()
    resolved_train_config_path = Path(train_config_path).resolve()
    resolved_runtime_template_path = Path(runtime_template_path).resolve()
    resolved_runtime_output_path = Path(runtime_output_path).resolve()
    resolved_selected_output = (
        Path(selected_checkpoint_output).resolve()
        if selected_checkpoint_output is not None
        else resolved_run_dir / "selected.pt"
    )

    train_summary_path = resolved_run_dir / "summary.json"
    history_path = resolved_run_dir / "history.json"
    if not train_summary_path.is_file():
        raise FileNotFoundError(train_summary_path)
    if not history_path.is_file():
        raise FileNotFoundError(history_path)

    train_summary = _load_json(train_summary_path)
    history = _load_json(history_path)
    candidates = _build_candidates(
        run_dir=resolved_run_dir,
        train_summary=train_summary,
        history=history,
        train_config_path=resolved_train_config_path,
        device=device,
    )
    selected = max(candidates, key=_rank_candidate)

    resolved_selected_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected["checkpoint_path"], resolved_selected_output)
    calibrate_runtime_thresholds(
        train_config_path=resolved_train_config_path,
        runtime_config_path=resolved_runtime_template_path,
        checkpoint_path=resolved_selected_output,
        output_path=resolved_runtime_output_path,
        device=device,
    )

    summary = {
        "run_dir": str(resolved_run_dir),
        "train_config_path": str(resolved_train_config_path),
        "runtime_template_path": str(resolved_runtime_template_path),
        "runtime_output_path": str(resolved_runtime_output_path),
        "selection_rule": {
            "primary": "sample_macro_f1",
            "secondary": "sample_weighted_f1",
            "tertiary": "sample_accuracy",
            "then": [
                "sample_fall_f1",
                "sample_recovery_f1",
                "sample_prolonged_lying_f1",
                "window_macro_f1",
                "training_selection_metric",
                "epoch",
            ],
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "selected": {
            "epoch": int(selected["epoch"]),
            "checkpoint_path": str(resolved_selected_output),
            "source_checkpoint_path": selected["checkpoint_path"],
            "selection_metric": selected["selection_metric"],
            "selection_scope": selected["selection_scope"],
            "metric_value": float(selected["metric_value"]),
            "ranking_key": selected["ranking_key"],
            "train_metrics": selected["train_metrics"],
            "sample_metrics": selected["sample_metrics"],
        },
    }
    return summary


def build_markdown(summary: dict[str, Any]) -> str:
    selected = summary["selected"]
    selected_sample = selected["sample_metrics"]
    selected_train = selected["train_metrics"]
    lines = [
        "# 部署 checkpoint 选择",
        "",
        f"- candidate_count: {summary['candidate_count']}",
        f"- 选中 epoch: {selected['epoch']}",
        f"- selected_checkpoint: {selected['checkpoint_path']}",
        f"- source_checkpoint: {selected['source_checkpoint_path']}",
        f"- runtime_output: {summary['runtime_output_path']}",
        "",
        "## 选择规则",
        "- primary: sample_macro_f1",
        "- secondary: sample_weighted_f1",
        "- tertiary: sample_accuracy",
        "- tie_breakers: sample_fall_f1, sample_recovery_f1, sample_prolonged_lying_f1, window_macro_f1, training_selection_metric, epoch",
        "",
        "## 选中候选指标",
        f"- sample_macro_f1: {float(selected_sample.get('macro_f1', 0.0)):.4f}",
        f"- sample_weighted_f1: {float(selected_sample.get('weighted_f1', 0.0)):.4f}",
        f"- sample_accuracy: {float(selected_sample.get('accuracy', 0.0)):.4f}",
        f"- train_macro_f1: {float(selected_train.get('macro_f1', 0.0)):.4f}",
        "",
        "## 候选列表",
    ]
    for candidate in summary["candidates"]:
        sample_metrics = candidate["sample_metrics"]
        train_metrics = candidate["train_metrics"]
        lines.append(
            (
                f"- epoch {int(candidate['epoch'])}: sample_macro_f1={float(sample_metrics.get('macro_f1', 0.0)):.4f}, "
                f"sample_weighted_f1={float(sample_metrics.get('weighted_f1', 0.0)):.4f}, "
                f"sample_accuracy={float(sample_metrics.get('accuracy', 0.0)):.4f}, "
                f"train_macro_f1={float(train_metrics.get('macro_f1', 0.0)):.4f}, "
                f"source={candidate['checkpoint_path']}"
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--train-config", type=Path, required=True)
    parser.add_argument("--runtime-template", type=Path, required=True)
    parser.add_argument("--runtime-output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--selected-checkpoint-output", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    summary = select_deployment_checkpoint(
        run_dir=args.run_dir,
        train_config_path=args.train_config,
        runtime_template_path=args.runtime_template,
        runtime_output_path=args.runtime_output,
        device=args.device,
        selected_checkpoint_output=args.selected_checkpoint_output,
    )
    markdown = build_markdown(summary)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {args.output_json}", flush=True)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)
    print(markdown, end="")


if __name__ == "__main__":
    main()
