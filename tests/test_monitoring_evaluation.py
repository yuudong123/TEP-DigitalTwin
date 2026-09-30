import csv
import json

import pytest

from src.monitoring import evaluate_drift as evaluation


@pytest.mark.parametrize("start,end,expected", [
    (30, 35.95, "stable_30_60"),
    (54, 59.95, "stable_30_60"),
    (54.05, 60, "transition_or_boundary"),
    (65, 70.95, "transition_or_boundary"),
    (70, 75.95, "post_70"),
])
def test_phase_uses_both_window_bounds(start, end, expected):
    assert evaluation.window_phase(start, end) == expected


def test_late_degradation_does_not_count_as_stable_alert(tmp_path, monkeypatch):
    manifest = tmp_path / "split.csv"
    manifest.write_text("case,Id,split\ncase1,1,validation\n", encoding="utf-8")
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(evaluation, "load_reference", lambda _: (
        "v-test", {"case1": {"a": [float(i % 10) for i in range(1000)]}}
    ))
    with (tmp_path / "case1.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["Id", "Time", "a"])
        for i in range(1800):
            hour = round(i * 0.05, 2)
            writer.writerow([1, hour, i % 10 + (100 if hour >= 70 else 0)])
    result = evaluation.evaluate(
        raw_dir=tmp_path, manifest_path=manifest, reference_path=reference,
        split="validation",
    )
    stable = result["phases"]["stable_30_60"]
    late = result["phases"]["post_70"]
    assert stable["windows"] == 5
    assert stable["alerts"] == 0
    assert late["windows"] > 0
    assert late["alerts"] == late["windows"]
    assert sum(p["windows"] for p in result["phases"].values()) == result["evaluated_windows"]
    assert sum(p["alerts"] for p in result["phases"].values()) == result["alert_windows"]


def test_rejects_partial_windows_before_loading_files(tmp_path):
    with pytest.raises(ValueError, match="complete windows"):
        evaluation.evaluate(
            raw_dir=tmp_path, manifest_path=tmp_path / "missing",
            reference_path=tmp_path / "missing", split="validation", min_samples=20,
        )
