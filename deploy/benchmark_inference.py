"""Compare exact predictions and elapsed time on three real CSV windows, without changing model files."""
import argparse
import csv
import json
from pathlib import Path
import time

from src.inference.model_loader import ProductionPredictor
from src.inference.temporal_features import base_features_from_feature_list, build_latest_features


def verify(output):
    root = Path(__file__).resolve().parents[1]
    predictor = ProductionPredictor(root/'models/production/v1.0.0', threads=1)
    base = base_features_from_feature_list(predictor.features)
    history, windows = [], []
    targets = [1., 35., 130.]
    with (root/'data/raw/TEP/case1.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if int(float(row['Id'])) != 1:
                continue
            history.append({name: float(row[name]) for name in base})
            history = history[-21:]
            timestamp = float(row['Time'])
            if targets and timestamp >= targets[0] and len(history) == 21:
                windows.append((timestamp, build_latest_features(history, base, predictor.features)))
                targets.pop(0)
                if not targets:
                    break
    results = {}
    for threads in (0, 1):
        # Zero is used only here to reproduce the old unrestricted XGBoost policy.
        predictor.threads = threads
        for model in predictor.models.values():
            model.set_param({'nthread': threads})
        started = time.perf_counter()
        values = [predictor.predict(frame, 'case1::1', timestamp) for timestamp, frame in windows]
        results[str(threads)] = {'elapsed_seconds': time.perf_counter()-started, 'predictions': values}
    report = {'source': 'three_real_case1_csv_windows', 'timestamps': [item[0] for item in windows],
              'old_unrestricted_seconds': results['0']['elapsed_seconds'], 'one_thread_seconds': results['1']['elapsed_seconds'],
              'prediction_json_identical': results['0']['predictions'] == results['1']['predictions'],
              'model_files_modified': False}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    if not report['prediction_json_identical'] or len(windows) != 3:
        raise AssertionError('Thread policy changed predictions or missing real source windows')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    verify(parser.parse_args().output)
