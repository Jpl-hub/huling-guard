from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from merge_interval_labels import merge_interval_labels


def test_merge_interval_labels_dedupes_and_sorts(tmp_path: Path) -> None:
    first = tmp_path / "intervals_a.json"
    second = tmp_path / "intervals_b.json"
    first.write_text(
        """
{
  "intervals": [
    {
      "sample_id": "sample_b",
      "label": "near_fall",
      "start_time": 1.0,
      "end_time": 2.0,
      "source": "queue_a"
    },
    {
      "sample_id": "sample_a",
      "label": "recovery",
      "start_time": 3.0,
      "end_time": 4.0,
      "source": "queue_a"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    second.write_text(
        """
{
  "intervals": [
    {
      "sample_id": "sample_b",
      "label": "near_fall",
      "start_time": 1.0,
      "end_time": 2.0,
      "source": "queue_a"
    },
    {
      "sample_id": "sample_b",
      "label": "fall",
      "start_time": 4.0,
      "end_time": 5.0,
      "source": "queue_b"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    merged = merge_interval_labels([first, second])

    assert len(merged["intervals"]) == 3
    assert merged["intervals"][0]["sample_id"] == "sample_a"
    assert merged["intervals"][-1]["label"] == "fall"
