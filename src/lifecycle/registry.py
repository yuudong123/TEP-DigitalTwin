"""Immutable, hash-pinned bundles and an atomically replaced active pointer."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

BUNDLE_FILES = ('rul_hours.json', 'failure_within_4h.json', 'failure_within_2h.json',
                'failure_within_1h.json', 'feature_list.json', 'feature_schema.csv',
                'thresholds.json', 'metadata.json', 'prediction_schema.json')


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(hashes):
    return hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def bundle_manifest(directory):
    directory = Path(directory).resolve(strict=True)
    metadata = json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    version = metadata['version']
    if not isinstance(version, str) or not re.fullmatch(r'v[0-9][A-Za-z0-9._-]{0,63}', version):
        raise ValueError('Unsafe model version')
    features = json.loads((directory/'feature_list.json').read_text(encoding='utf-8'))['features']
    if len(features) != 728 or len(set(features)) != 728 or not all(isinstance(f, str) for f in features):
        raise ValueError('Expected 728 unique ordered features')
    if (metadata.get('feature_count'), metadata.get('sampling_interval_minutes'), metadata.get('warmup_minutes')) != (728, 3, 60):
        raise ValueError('Unsupported feature/time contract')
    for name in BUNDLE_FILES:
        if (directory/name).is_symlink():
            raise ValueError('Symlink bundle files are not allowed')
    hashes = {name: file_sha256(directory/name) for name in BUNDLE_FILES}
    return dict(version=version, files=hashes, fingerprint=fingerprint(hashes))


def verify_manifest(directory, manifest):
    actual = bundle_manifest(directory)
    if actual != {key: manifest[key] for key in ('version', 'files', 'fingerprint')}:
        raise ValueError('Model bundle differs from its approved hashes')
    return actual


def resolve_entry(root, entry):
    root = Path(root).resolve(strict=True)
    relative = entry['relative_dir']
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Model pointer must use a safe registry-relative path')
    target = (root/relative).resolve(strict=True)
    if target == root or root not in target.parents:
        raise ValueError('Model pointer escapes registry')
    verify_manifest(target, entry)
    return target


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def registry_lock(pointer):
    path = Path(str(pointer)+'.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink()


def entry_for(root, directory):
    directory, root = Path(directory).resolve(strict=True), Path(root).resolve(strict=True)
    if root not in directory.parents:
        raise ValueError('Baseline is outside production registry')
    return dict(bundle_manifest(directory), relative_dir=directory.relative_to(root).as_posix())


def write_change(pointer, active, previous, operation, approved_sha):
    payload = dict(schema_version='1.0', generation=uuid4().hex, active=active, previous=previous,
                   operation=operation, approved_report_sha256=approved_sha,
                   changed_at=datetime.now(timezone.utc).isoformat())
    # Persist an immutable audit record BEFORE publishing the pointer. An orphan
    # record does not prove application; runtime acknowledgements do.
    audit = Path(pointer).parent/'model-changes'/f"{payload['generation']}.json"
    atomic_json(audit, payload)
    atomic_json(pointer, payload)
    return payload


def promote(candidate, report_path, approved_sha, registry, pointer, baseline):
    report_path = Path(report_path)
    if file_sha256(report_path) != approved_sha:
        raise ValueError('Approval must pin the exact evaluation report SHA256')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if (report.get('schema_version') != '1.0' or report.get('split') != 'validation'
        or report.get('policy') != 'validation_nonregression_all_and_each_case_v1'
        or report.get('eligible') is not True or report.get('reasons')):
        raise ValueError('Candidate did not pass validation-only policy')
    # Do not treat an arbitrary eligible=true field as a quality gate.
    from .evaluate import non_regression
    required_scopes = {'all', *(f'case{index}' for index in range(1, 7))}
    required_metrics = {'rul_mae', 'rul_rmse', *(f'failure_within_{h}h_{name}'
                        for h in (4, 2, 1) for name in ('ap', 'f1', 'recall', 'fpr'))}
    for field in ('baseline_metrics', 'candidate_metrics'):
        if set(report.get(field, {})) != required_scopes or any(
            set(values) != required_metrics for values in report[field].values()
        ):
            raise ValueError('Evaluation metrics are incomplete')
    if non_regression(report['baseline_metrics'], report['candidate_metrics']):
        raise ValueError('Report contains a metric regression')
    if report.get('rows', 0) <= 0 or report.get('trajectories', 0) <= 0:
        raise ValueError('Evaluation did not include validation data')
    candidate = Path(candidate).resolve(strict=True)
    verify_manifest(candidate, report['candidate'])
    registry = Path(registry).resolve(strict=True)
    with registry_lock(pointer):
        current = json.loads(Path(pointer).read_text(encoding='utf-8'))['active'] if Path(pointer).exists() else entry_for(registry, baseline)
        resolve_entry(registry, current)
        if current['fingerprint'] != report['baseline']['fingerprint']:
            raise ValueError('Production changed since evaluation; reevaluate')
        version = report['candidate']['version']
        target = registry/version
        if target.exists():
            verify_manifest(target, report['candidate'])
        else:
            temporary = registry/('.candidate-'+uuid4().hex)
            try:
                temporary.mkdir()
                for name in BUNDLE_FILES:
                    shutil.copy2(candidate/name, temporary/name)
                verify_manifest(temporary, report['candidate'])
                # All files are complete before the immutable directory appears.
                os.rename(temporary, target)
            finally:
                if temporary.exists():
                    # Only this function's newly created directory, never root.
                    shutil.rmtree(temporary)
        active = entry_for(registry, target)
        return write_change(pointer, active, current, 'promote', approved_sha)


def rollback(registry, pointer, expected_generation):
    with registry_lock(pointer):
        current = json.loads(Path(pointer).read_text(encoding='utf-8'))
        if current['generation'] != expected_generation:
            raise ValueError('Model generation changed; inspect before rollback')
        previous = current.get('previous')
        if not previous:
            raise ValueError('No previous approved bundle')
        resolve_entry(registry, previous)
        return write_change(pointer, previous, current['active'], 'rollback', current['approved_report_sha256'])
