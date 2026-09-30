"""Load and smoke-test all four models before swapping a live reference."""
import json
import logging
import os
from pathlib import Path
import threading
import time

from src.lifecycle.registry import atomic_json, entry_for, resolve_entry, verify_manifest


class ManagedPredictor:
    def __init__(self, model_dir, registry=None, pointer=None, status_path=None, loader=None):
        if loader is None:
            from .model_loader import ProductionPredictor
            loader = ProductionPredictor
        self.loader = loader
        self.registry = Path(registry or model_dir.parent)
        self.pointer = Path(pointer or 'logs/model-active.json')
        self.status_path = Path(status_path or 'logs/model-status.json')
        self.lock = threading.RLock()
        self.current = loader(Path(model_dir))
        self.features = self.current.features
        self.active = entry_for(self.registry, model_dir)
        self.generation = None
        self.rejected_generation = None
        self.last_probe = 0.0
        # A malformed new pointer must not lose the last acknowledged bundle
        # across process restarts. Hash validation still applies to the fallback.
        if self.status_path.exists():
            try:
                acknowledged = json.loads(self.status_path.read_text(encoding='utf-8'))
                directory = resolve_entry(self.registry, acknowledged['active'])
                previous = loader(directory)
                if previous.features != self.features:
                    raise ValueError('Fallback feature order mismatch')
                self.current, self.active = previous, acknowledged['active']
                self.generation = acknowledged['generation']
            except Exception:
                logging.warning('Previous model acknowledgement invalid; using configured baseline')
        self._write_status('loaded')
        self.refresh(force=True)

    def _write_status(self, status, error=None):
        try:
            atomic_json(self.status_path, dict(status=status, model_version=self.active['version'],
                        active=self.active, fingerprint=self.active['fingerprint'], generation=self.generation,
                        rejected_generation=self.rejected_generation, error=error))
        except OSError:
            logging.error('Could not persist model status; inspect runtime logs and Prediction.model_version')

    def refresh(self, force=False):
        with self.lock:
            if not force and time.monotonic() - self.last_probe < 1:
                return False
            self.last_probe = time.monotonic()
            attempted = None
            try:
                if not self.pointer.exists():
                    return False
                state = json.loads(self.pointer.read_text(encoding='utf-8'))
                attempted = state['generation']
                if attempted in (self.generation, self.rejected_generation):
                    return False
                if state.get('schema_version') != '1.0':
                    raise ValueError('Unsupported active pointer schema')
                directory = resolve_entry(self.registry, state['active'])
                candidate = self.loader(directory)
                if candidate.features != self.features:
                    raise ValueError('Hot application cannot change feature order')
                # A Prediction and its SHAP payload must validate before use.
                import pandas as pd
                from .prediction_schema import validate_prediction
                smoke = pd.DataFrame([[0.0]*len(candidate.features)], columns=candidate.features)
                validate_prediction(candidate.predict(smoke, 'case1::0', 1.0))
                verify_manifest(directory, state['active'])
                self.current = candidate
                self.active = state['active']
                self.generation = attempted
                self.rejected_generation = None
                self._write_status('applied')
                return True
            except Exception as error:
                self.rejected_generation = attempted
                logging.warning('Model application rejected; retaining %s (%s)', self.active['version'], type(error).__name__)
                self._write_status('rejected_retaining_previous', type(error).__name__)
                return False

    def predict(self, features, trajectory_key, timestamp_hours):
        with self.lock:
            self.refresh()
            return self.current.predict(features, trajectory_key, timestamp_hours)


def model_from_environment(model_dir, service):
    return ManagedPredictor(
        model_dir, registry=Path(os.getenv('PRODUCTION_MODEL_DIR', str(model_dir.parent))),
        pointer=Path(os.getenv('MODEL_ACTIVE_POINTER', 'logs/model-active.json')),
        status_path=Path('logs')/f'model-status-{service}.json',
    )
