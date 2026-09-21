import csv
import json

from src.monitoring.reference_builder import build_reference


def _write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_reference_uses_only_train_window(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    manifest_path = tmp_path / "split_manifest.csv"
    schema_path = tmp_path / "feature_schema.csv"
    output_path = tmp_path / "reference.json"
    features = [f"feature_{index}" for index in range(52)]

    _write_csv(
        schema_path,
        ["column", "model_b_feature"],
        [{"column": feature, "model_b_feature": "True"} for feature in features],
    )
    _write_csv(
        manifest_path,
        ["trajectory_key", "case", "Id", "split"],
        [
            {"trajectory_key": "case1::1", "case": "case1", "Id": 1, "split": "train"},
            {"trajectory_key": "case1::2", "case": "case1", "Id": 2, "split": "test"},
        ],
    )
    rows = []
    for trajectory_id in (1, 2):
        for timestamp in (29.0, 30.0, 31.0, 60.0):
            row = {"Id": trajectory_id, "Time": timestamp}
            row.update({feature: trajectory_id * 100 + timestamp for feature in features})
            rows.append(row)
    _write_csv(raw_dir / "case1.csv", ["Id", "Time", *features], rows)

    result = build_reference(
        raw_dir=raw_dir,
        manifest_path=manifest_path,
        feature_schema_path=schema_path,
        output_path=output_path,
        cases=["case1"],
        sample_limit=20,
    )

    case = result["cases"]["case1"]
    feature = case["features"]["feature_0"]
    assert case["trajectory_count"] == 1
    assert case["row_count"] == 2
    assert feature["reference_sample"] == [130.0, 131.0]
    assert feature["missing_rate"] == 0.0
    assert json.loads(output_path.read_text(encoding="utf-8"))["split"] == "train"
