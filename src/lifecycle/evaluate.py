"""Frozen validation data only. No fitting, threshold search or test-set tuning."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, mean_absolute_error, mean_squared_error, recall_score
import xgboost as xgb

from src.inference.model_loader import ProductionPredictor
from src.inference.prediction_schema import RISK_TARGETS
from .registry import atomic_json, bundle_manifest, file_sha256


def non_regression(baseline, candidate, epsilon=1e-8):
    reasons = []
    for scope, old in baseline.items():
        for name, value in old.items():
            new = candidate[scope][name]
            if not np.isfinite(new) or not np.isfinite(value):
                reasons.append(f'{scope}/{name}: nonfinite metric')
            elif (new > value + epsilon if name.endswith(('mae', 'rmse', 'fpr')) else new < value - epsilon):
                reasons.append(f'{scope}/{name}: regression {value:.8f} -> {new:.8f}')
    return reasons


def metrics(labels, predictions, thresholds, mask):
    y = {key: value[mask] for key, value in labels.items()}
    scores = {key: value[mask] for key, value in predictions.items()}
    result = {'rul_mae': float(mean_absolute_error(y['rul_hours'], scores['rul_hours'])),
              'rul_rmse': float(np.sqrt(mean_squared_error(y['rul_hours'], scores['rul_hours'])))}
    for target in RISK_TARGETS:
        truth, score = y[target], scores[target]
        if set(np.unique(truth)) != {0, 1}:
            raise ValueError(f'Validation requires both classes for {target}')
        alert = score >= thresholds[target]
        tn, fp, _, _ = confusion_matrix(truth, alert, labels=[0, 1]).ravel()
        result.update({target+'_ap': float(average_precision_score(truth, score)),
                       target+'_f1': float(f1_score(truth, alert)),
                       target+'_recall': float(recall_score(truth, alert)),
                       target+'_fpr': float(fp/(fp+tn))})
    return result


def evaluate(candidate_dir, baseline_dir, validation_path, split_manifest, output):
    validation_path, split_manifest = Path(validation_path), Path(split_manifest)
    if validation_path.name != 'validation.parquet':
        raise ValueError('Only frozen validation.parquet is accepted; never test.parquet')
    models = [ProductionPredictor(Path(baseline_dir)), ProductionPredictor(Path(candidate_dir))]
    if models[0].features != models[1].features:
        raise ValueError('Feature contract/order changed; separate migration is required')
    manifests = [bundle_manifest(directory) for directory in (baseline_dir, candidate_dir)]
    if manifests[0]['version'] == manifests[1]['version']:
        raise ValueError('Candidate needs a distinct immutable version')
    with split_manifest.open(encoding='utf-8-sig', newline='') as stream:
        split_rows = list(csv.DictReader(stream))
    manifest_hash = file_sha256(split_manifest)
    summary_path = split_manifest.parent/'temporal_dataset_summary.csv'
    with summary_path.open(encoding='utf-8-sig', newline='') as stream:
        summary = next(row for row in csv.DictReader(stream) if row['split'] == 'validation')
    known = {}
    for row in split_rows:
        key, split = row['trajectory_key'], row['split']
        if key in known:
            raise ValueError('Duplicate/overlapping trajectory in split manifest')
        known[key] = split
    expected = {key for key, split in known.items() if split == 'validation'}
    if not expected:
        raise ValueError('Validation trajectory manifest is empty')
    labels, keys = [], []
    outputs = [[], []]
    for model in models:
        for booster in model.models.values():
            booster.set_param({'nthread': 2})
    targets = ('rul_hours', *RISK_TARGETS)
    dataset_hash = file_sha256(validation_path)
    for batch in pq.ParquetFile(validation_path).iter_batches(batch_size=8192, columns=['trajectory_key', 'Time', *targets, *models[0].features]):
        frame = batch.to_pandas()
        if not frame['trajectory_key'].isin(expected).all():
            raise ValueError('Validation contains non-validation trajectories')
        values = frame[['Time', *targets]+models[0].features].to_numpy()
        if not np.isfinite(values).all() or (frame['rul_hours'] < 0).any():
            raise ValueError('Nonfinite/invalid validation data')
        keys.extend(frame['trajectory_key'].tolist())
        labels.append(frame[list(targets)])
        matrix = xgb.DMatrix(frame[models[0].features], feature_names=models[0].features)
        for index, model in enumerate(models):
            result = {target: model.models[target].predict(matrix) for target in targets}
            result['rul_hours'] = np.maximum(result['rul_hours'], 0)
            if any(not np.isfinite(value).all() for value in result.values()):
                raise ValueError('Candidate produced nonfinite predictions')
            if any(((result[target] < 0) | (result[target] > 1)).any() for target in RISK_TARGETS):
                raise ValueError('Invalid risk probability')
            outputs[index].append(pd.DataFrame(result))
    if set(keys) != expected:
        raise ValueError('Validation must include every frozen validation trajectory')
    if len(keys) != int(summary['output_rows']) or len(expected) != int(summary['trajectory_count']):
        raise ValueError('Validation size differs from the frozen dataset summary')
    if manifest_hash != file_sha256(split_manifest):
        raise ValueError('Split manifest changed during evaluation')
    if dataset_hash != file_sha256(validation_path):
        raise ValueError('Dataset changed during evaluation')
    truth = {column: series.to_numpy() for column, series in pd.concat(labels, ignore_index=True).items()}
    cases = np.array([key.split('::')[0] for key in keys])
    if set(cases) != {f'case{index}' for index in range(1, 7)}:
        raise ValueError('All six cases are required')
    scores = []
    for index, model in enumerate(models):
        probabilities = {column: series.to_numpy() for column, series in pd.concat(outputs[index], ignore_index=True).items()}
        scores.append({scope: metrics(truth, probabilities, model.thresholds, np.ones(len(keys), dtype=bool) if scope == 'all' else cases == scope)
                       for scope in ('all', *sorted(set(cases)))})
    # Rehash model files too, before publishing an approval-ready report.
    if manifests != [bundle_manifest(directory) for directory in (baseline_dir, candidate_dir)]:
        raise ValueError('Model bundle changed during evaluation')
    reasons = non_regression(scores[0], scores[1])
    report = dict(schema_version='1.0', time=datetime.now(timezone.utc).isoformat(),
                  policy='validation_nonregression_all_and_each_case_v1', split='validation',
                  dataset_sha256=dataset_hash, split_manifest_sha256=file_sha256(split_manifest),
                  rows=len(keys), trajectories=len(expected), baseline=manifests[0], candidate=manifests[1],
                  baseline_metrics=scores[0], candidate_metrics=scores[1], eligible=not reasons, reasons=reasons,
                  automatic_retraining=False, improvement_claim=False)
    atomic_json(output, report)
    print(json.dumps({'eligible': report['eligible'], 'rows': len(keys), 'reasons': reasons,
                      'report_sha256': file_sha256(output)}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--validation', required=True, type=Path)
    parser.add_argument('--split-manifest', default='data/metadata/split_manifest.csv', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(args.candidate, args.baseline, args.validation, args.split_manifest, args.output)
    raise SystemExit(0 if report['eligible'] else 2)
