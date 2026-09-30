import json
from pathlib import Path
import shutil

import pytest

from src.inference.managed_model import ManagedPredictor
from src.lifecycle.evaluate import non_regression
from src.lifecycle.registry import (atomic_json, bundle_manifest, entry_for, file_sha256,
                                    promote, registry_lock, resolve_entry, rollback)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bundles(tmp_path):
    registry = tmp_path/'production'
    baseline = registry/'v1.0.0'
    # Production data is only read. All mutations are isolated temporary copies.
    shutil.copytree(ROOT/'models/production/v1.0.0', baseline)
    candidate = tmp_path/'candidate'
    shutil.copytree(baseline, candidate)
    metadata = json.loads((candidate/'metadata.json').read_text(encoding='utf-8'))
    metadata['version'] = 'v1.0.0-control'
    atomic_json(candidate/'metadata.json', metadata)
    report = tmp_path/'evaluation.json'
    metrics = {'rul_mae': 1., 'rul_rmse': 2., **{f'failure_within_{h}h_{name}': .9
               for h in (4, 2, 1) for name in ('ap', 'f1', 'recall', 'fpr')}}
    scoped = {scope: metrics for scope in ('all', *(f'case{index}' for index in range(1, 7)))}
    atomic_json(report, dict(schema_version='1.0', split='validation', eligible=True, reasons=[],
                            policy='validation_nonregression_all_and_each_case_v1', rows=238872, trajectories=90,
                            baseline_metrics=scoped, candidate_metrics=scoped,
                            candidate=bundle_manifest(candidate), baseline=bundle_manifest(baseline)))
    return registry, baseline, candidate, report, tmp_path/'model-active.json'


def test_manual_promotion_rollback_and_generation_lock(bundles):
    registry, baseline, candidate, report, pointer = bundles
    with pytest.raises(ValueError, match='SHA256'):
        promote(candidate, report, 'wrong', registry, pointer, baseline)
    state = promote(candidate, report, file_sha256(report), registry, pointer, baseline)
    assert state['active']['version'] == 'v1.0.0-control'
    assert resolve_entry(registry, state['active']).name == 'v1.0.0-control'
    with pytest.raises(ValueError, match='generation'):
        rollback(registry, pointer, 'wrong-generation')
    restored = rollback(registry, pointer, state['generation'])
    assert restored['active']['version'] == 'v1.0.0'


def test_modified_candidate_and_rejected_report_cannot_promote(bundles):
    registry, baseline, candidate, report, pointer = bundles
    payload = json.loads(report.read_text())
    payload['eligible'] = False
    atomic_json(report, payload)
    with pytest.raises(ValueError, match='policy'):
        promote(candidate, report, file_sha256(report), registry, pointer, baseline)
    payload['eligible'] = True
    atomic_json(report, payload)
    (candidate/'thresholds.json').write_text('{}')
    with pytest.raises(ValueError, match='hashes'):
        promote(candidate, report, file_sha256(report), registry, pointer, baseline)
    assert not pointer.exists()


def test_pointer_cannot_escape_registry(bundles):
    registry, baseline, _, _, _ = bundles
    entry = entry_for(registry, baseline)
    for path in ('../candidate', str(baseline.resolve())):
        with pytest.raises(ValueError):
            resolve_entry(registry, dict(entry, relative_dir=path))


def test_promotion_lock_is_exclusive(bundles):
    pointer = bundles[-1]
    with registry_lock(pointer):
        with pytest.raises(FileExistsError):
            with registry_lock(pointer):
                pass
    assert not Path(str(pointer)+'.lock').exists()


def test_nonregression_includes_each_case():
    baseline = {'all': {'rul_mae': 2., 'rul_rmse': 3., 'risk_f1': .9, 'risk_fpr': .01},
                'case1': {'risk_recall': .95}}
    assert non_regression(baseline, baseline) == []
    candidate = json.loads(json.dumps(baseline))
    candidate['case1']['risk_recall'] = .94
    candidate['all']['rul_mae'] = 1.0
    assert any('case1' in reason for reason in non_regression(baseline, candidate))


class FakePredictor:
    def __init__(self, directory):
        self.features = json.loads((directory/'feature_list.json').read_text())['features']
        self.version = json.loads((directory/'metadata.json').read_text())['version']

    def predict(self, frame, key, timestamp):
        return dict(schema_version='1.0', model_version=self.version, trajectory_key=key,
                    timestamp_hours=timestamp, rul={'hours': 1}, status='NORMAL',
                    explanation_model='failure_within_4h', top_risk_factors=[],
                    risk={f'failure_within_{h}h': dict(score=.1, threshold=.5, alert=False) for h in (4, 2, 1)})


def test_live_swap_failure_retention_restart_and_rollback(bundles, tmp_path):
    registry, baseline, candidate, report, pointer = bundles
    status = tmp_path/'ack.json'
    manager = ManagedPredictor(baseline, registry, pointer, status, loader=FakePredictor)
    state = promote(candidate, report, file_sha256(report), registry, pointer, baseline)
    assert manager.refresh(force=True)
    assert manager.current.version == 'v1.0.0-control'
    bad = dict(state, generation='corrupt', active=dict(state['active'], relative_dir='../candidate'))
    atomic_json(pointer, bad)
    assert not manager.refresh(force=True)
    assert manager.current.version == 'v1.0.0-control'
    rebooted = ManagedPredictor(baseline, registry, pointer, status, loader=FakePredictor)
    assert rebooted.current.version == 'v1.0.0-control'
    atomic_json(pointer, state)
    rollback(registry, pointer, state['generation'])
    assert rebooted.refresh(force=True)
    assert rebooted.current.version == 'v1.0.0'


def test_real_four_model_load_and_hot_application(bundles, tmp_path):
    registry, baseline, candidate, report, pointer = bundles
    manager = ManagedPredictor(baseline, registry, pointer, tmp_path/'real-ack.json')
    promote(candidate, report, file_sha256(report), registry, pointer, baseline)
    assert manager.refresh(force=True)
    assert manager.current.metadata['version'] == 'v1.0.0-control'
    # A report hash does not make later modified files safe.
    active_dir = registry/'v1.0.0-control'
    metadata = json.loads((active_dir/'metadata.json').read_text())
    metadata['version'] = 'v9-bad'
    atomic_json(active_dir/'metadata.json', metadata)
    payload = json.loads(pointer.read_text())
    payload['generation'] = 'modified-files'
    atomic_json(pointer, payload)
    assert not manager.refresh(force=True)
    assert manager.current.metadata['version'] == 'v1.0.0-control'
