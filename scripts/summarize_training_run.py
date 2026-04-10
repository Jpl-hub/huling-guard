from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_line(title: str, value: Any) -> str:
    if isinstance(value, float):
        return f"- {title}: {value:.4f}"
    return f"- {title}: {value}"


def _build_markdown(run_dir: Path, history: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    best_metrics = summary.get("best_metrics", {})
    final_metrics = summary.get("final_metrics", {})
    lines = [
        f"# 训练结果汇总：{run_dir.name}",
        "",
        "## 关键信息",
        _metric_line("最佳 epoch", summary.get("best_epoch", "unknown")),
        _metric_line("选择指标", summary.get("selection_metric", "macro_f1")),
        _metric_line("最佳 macro_f1", best_metrics.get("macro_f1", 0.0)),
        _metric_line("最佳 accuracy", best_metrics.get("accuracy", 0.0)),
        _metric_line("最终 macro_f1", final_metrics.get("macro_f1", 0.0)),
        _metric_line("最终 accuracy", final_metrics.get("accuracy", 0.0)),
        _metric_line("batch_size", summary.get("batch_size", "unknown")),
        _metric_line("num_workers", summary.get("num_workers", "unknown")),
        _metric_line("scheduler", summary.get("scheduler", "unknown")),
        _metric_line("amp", summary.get("amp", "unknown")),
        "",
        "## 训练轨迹",
    ]
    for epoch in history:
        train_metrics = epoch["train"]
        eval_metrics = epoch.get("eval")
        line = (
            f"- epoch {epoch['epoch']}: "
            f"lr={epoch.get('lr', 0.0):.6f}, "
            f"seconds={epoch.get('epoch_seconds', 0.0):.2f}, "
            f"train_macro_f1={train_metrics['macro_f1']:.4f}, "
            f"train_loss={train_metrics['loss']:.4f}"
        )
        if eval_metrics is not None:
            line += (
                f", eval_macro_f1={eval_metrics['macro_f1']:.4f}, "
                f"eval_loss={eval_metrics['loss']:.4f}"
            )
        lines.append(line)
    lines.extend(
        [
            "",
            "## 训练集类别分布",
        ]
    )
    for state, count in summary.get("train_class_counts", {}).items():
        lines.append(_metric_line(state, count))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    history_path = run_dir / "history.json"
    summary_path = run_dir / "summary.json"
    if not history_path.is_file():
        raise FileNotFoundError(history_path)
    if not summary_path.is_file():
        raise FileNotFoundError(summary_path)

    history = _load_json(history_path)
    summary = _load_json(summary_path)
    markdown = _build_markdown(run_dir, history, summary)

    print(markdown, end="")
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")
        print(f"[write] {args.output_markdown}", flush=True)


if __name__ == "__main__":
    main()
