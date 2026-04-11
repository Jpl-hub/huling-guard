from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_experiment_round_complete import build_markdown, check_experiment_round_complete


def test_check_experiment_round_complete_passes_when_artifacts_are_consistent(tmp_path: Path) -> None:
    training_summary = tmp_path / "summary.json"
    sample_summary = tmp_path / "sample.json"
    event_summary = tmp_path / "event.json"
    release_verification = tmp_path / "verification.json"
    deployment_selection = tmp_path / "selection.json"
    comparison_summary = tmp_path / "comparison.json"
    promotion_summary = tmp_path / "promotion.json"
    round_summary = tmp_path / "round.json"

    training_summary.write_text('{"best_epoch": 9, "best_metrics": {"macro_f1": 0.5}}', encoding="utf-8")
    sample_summary.write_text('{"macro_f1": 0.4, "accuracy": 0.8}', encoding="utf-8")
    event_summary.write_text('{"f1": 0.8}', encoding="utf-8")
    release_verification.write_text('{"ok": true, "checked_artifacts": 6}', encoding="utf-8")
    deployment_selection.write_text('{"selected": {"epoch": 9}}', encoding="utf-8")
    comparison_summary.write_text('{"training": {"macro_f1": {"delta": 0.03}}}', encoding="utf-8")
    promotion_summary.write_text('{"verdict": "promote", "passed_checks": 4, "total_checks": 4}', encoding="utf-8")
    round_summary.write_text(
        (
            '{"artifacts": {"has_sample_summary": true, "has_event_summary": true, "has_release_verification": true, '
            '"has_deployment_selection": true, '
            '"has_comparison_summary": true, "has_promotion_summary": true}}'
        ),
        encoding="utf-8",
    )

    summary = check_experiment_round_complete(
        run_name="public_plus_ur_refined_v1",
        training_summary_path=training_summary,
        sample_summary_path=sample_summary,
        event_summary_path=event_summary,
        release_verification_path=release_verification,
        deployment_selection_path=deployment_selection,
        comparison_summary_path=comparison_summary,
        promotion_summary_path=promotion_summary,
        round_summary_path=round_summary,
    )

    assert summary["complete"] is True
    assert "## 检查项" in build_markdown(summary)


def test_check_experiment_round_complete_fails_when_release_verification_is_bad(tmp_path: Path) -> None:
    training_summary = tmp_path / "summary.json"
    sample_summary = tmp_path / "sample.json"
    release_verification = tmp_path / "verification.json"
    deployment_selection = tmp_path / "selection.json"
    round_summary = tmp_path / "round.json"

    training_summary.write_text('{"best_epoch": 9, "best_metrics": {"macro_f1": 0.5}}', encoding="utf-8")
    sample_summary.write_text('{"macro_f1": 0.4, "accuracy": 0.8}', encoding="utf-8")
    release_verification.write_text('{"ok": false, "checked_artifacts": 6}', encoding="utf-8")
    deployment_selection.write_text('{"selected": {"epoch": 9}}', encoding="utf-8")
    round_summary.write_text(
        '{"artifacts": {"has_sample_summary": true, "has_release_verification": false, "has_deployment_selection": true}}',
        encoding="utf-8",
    )

    summary = check_experiment_round_complete(
        run_name="public_plus_ur_v1",
        training_summary_path=training_summary,
        sample_summary_path=sample_summary,
        release_verification_path=release_verification,
        deployment_selection_path=deployment_selection,
        round_summary_path=round_summary,
    )

    assert summary["complete"] is False
    failed = [check for check in summary["checks"] if not check["passed"]]
    assert any(check["name"] == "release_verification_ok" for check in failed)


def test_check_experiment_round_complete_treats_missing_event_summary_as_optional(tmp_path: Path) -> None:
    training_summary = tmp_path / "summary.json"
    round_summary = tmp_path / "round.json"
    missing_event_summary = tmp_path / "event.json"

    training_summary.write_text('{"best_epoch": 9, "best_metrics": {"macro_f1": 0.5}}', encoding="utf-8")
    round_summary.write_text('{"artifacts": {"has_event_summary": false}}', encoding="utf-8")

    summary = check_experiment_round_complete(
        run_name="public_plus_ur_v1",
        training_summary_path=training_summary,
        event_summary_path=missing_event_summary,
        round_summary_path=round_summary,
    )

    assert "event_summary" not in summary["required_artifacts"]
