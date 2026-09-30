import json
from pathlib import Path
import csv

from fastapi.testclient import TestClient
import pytest

from kafka.delivery import publish_json
from src.api.main import Settings, create_app
from src.api.replay import ReplayController
from src.api.store import SnapshotStore


def prediction(key='case1::1', timestamp=1):
    return dict(schema_version='1.0', model_version='v1.0.0', trajectory_key=key,
                timestamp_hours=timestamp, rul={'hours': 3}, status='NORMAL',
                explanation_model='failure_within_4h', top_risk_factors=[],
                risk={f'failure_within_{h}h': dict(score=.1, threshold=.5, alert=False) for h in (4, 2, 1)})


class FakeRuntime:
    def __init__(self, settings):
        self.store = SnapshotStore(settings.store_path)
        self.ready = True
        self.failed = False
        self.invalid_messages = 0
        self.predictor = object()

    def start(self):
        pass

    def close(self):
        self.store.close()

    def predict(self, history):
        return prediction(history[-1]['trajectory_key'], history[-1]['timestamp_hours'])


@pytest.fixture
def api(tmp_path):
    settings = Settings(store_path=tmp_path/'snapshots.db', raw_dir=tmp_path/'raw', web_dir=tmp_path/'dist')
    runtime = FakeRuntime(settings)
    app = create_app(settings, runtime)
    with TestClient(app) as client:
        yield client, runtime, settings


def test_empty_api_never_returns_mock(api):
    client, runtime, _ = api
    assert client.get('/api/predictions/latest').status_code == 404
    assert client.get('/health/ready').status_code == 200
    runtime.ready = False
    assert client.get('/health/ready').status_code == 503
    assert client.post('/v1/replay/start', json={'trajectory_key': 'case1::1'}).status_code == 503


def test_latest_persists_receipt_and_deduplicates(tmp_path):
    path = tmp_path/'snapshots.db'
    store = SnapshotStore(path)
    assert store.put('prediction', 'topic', 0, 11, prediction(timestamp=100))
    receipt = store.latest('prediction')[1]
    assert not store.put('prediction', 'topic', 0, 11, prediction(timestamp=101))
    assert store.latest('prediction')[1] == receipt
    store.close()
    store = SnapshotStore(path)
    assert store.latest('prediction')[0]['timestamp_hours'] == 100
    # New replay has a smaller simulated timestamp but a newer Kafka offset.
    assert store.put('prediction', 'topic', 0, 12, prediction(timestamp=1))
    assert store.latest('prediction')[0]['timestamp_hours'] == 1
    store.close()


def test_api_contract_and_cache_headers(api):
    client, runtime, _ = api
    runtime.store.put('prediction', 'topic', 0, 0, prediction())
    for url in ('/api/predictions/latest', '/v1/predictions/latest?trajectory_key=case1::1'):
        result = client.get(url)
        assert result.json() == prediction()
        assert result.headers['cache-control'] == 'no-store'
        assert result.headers['x-prediction-received-at'] == runtime.store.latest('prediction')[1]
    assert len(client.get('/v1/predictions').json()['items']) == 1
    assert client.get('/v1/monitoring/latest').status_code == 404
    assert client.get('/v1/trajectories').json()['items'][0]['raw_available'] is False


def history():
    from kafka.message_schema import build_sensor_message
    with (Path(__file__).resolve().parents[1]/'data/metadata/feature_schema.csv').open(encoding='utf-8-sig') as stream:
        columns = [row['column'] for row in csv.DictReader(stream) if row['column'] not in ('Id', 'Time')]
    return [build_sensor_message('case1', dict(Id=1, Time=i*.05, **{name: 1 for name in columns}), i)
            for i in range(21)]


def test_sync_predict_requires_contiguous_history(api):
    client, _, _ = api
    sensors = history()
    assert client.post('/v1/predict', json={'history': sensors}).status_code == 200
    sensors[5]['sequence'] = 99
    assert client.post('/v1/predict', json={'history': sensors}).status_code == 422
    assert client.post('/v1/predict', json={'history': sensors[:20]}).status_code == 422


def test_replay_whitelist_and_cross_origin_writes(api):
    client, _, _ = api
    assert client.post('/v1/replay/start', json={'trajectory_key': '../../secret'}).status_code == 422
    assert client.post('/v1/replay/start', json={'trajectory_key': 'case1::1'}).status_code == 503
    assert client.post('/v1/replay/start', json={'trajectory_key': 'case1::1', 'interval_seconds': 0}).status_code == 422
    assert client.post('/v1/replay/stop', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/v1/replay/stop', headers={'Origin': 'http://testserver'}).status_code == 409


def test_replay_state_commands(tmp_path):
    controller = ReplayController(Settings(), [])
    controller.state = dict(status='running', sent=1)
    assert controller.command('pause')['status'] == 'paused'
    with pytest.raises(RuntimeError):
        controller.command('pause')
    assert controller.command('resume')['status'] == 'running'
    assert controller.command('stop')['status'] == 'stopping'
    assert controller.wait_ready() is False
    controller.close()


class FakeProducer:
    def __init__(self, error=None, acknowledge=True):
        self.error, self.acknowledge = error, acknowledge

    def produce(self, **kwargs):
        self.callback = kwargs['on_delivery']

    def flush(self, timeout):
        if self.acknowledge:
            self.callback(self.error, None)
        return 0


def test_delivery_requires_ack_not_just_empty_queue():
    publish_json(FakeProducer(), 'topic', 'key', {})
    with pytest.raises(RuntimeError, match='failed'):
        publish_json(FakeProducer(error='rejected'), 'topic', 'key', {})
    with pytest.raises(RuntimeError, match='acknowledged'):
        publish_json(FakeProducer(acknowledge=False), 'topic', 'key', {})


@pytest.mark.parametrize('store_fails', [False, True])
def test_reader_commits_only_after_durable_write(tmp_path, monkeypatch, store_fails):
    import src.api.runtime as module
    runtime = module.PredictionRuntime(Settings(store_path=tmp_path/'reader.db'))

    class Message:
        def error(self): return None
        def topic(self): return 'tep-predictions'
        def partition(self): return 0
        def offset(self): return 10
        def key(self): return b'case1::1'
        def value(self): return json.dumps(prediction()).encode()

    class Reader:
        def __init__(self, config): self.committed = []
        def subscribe(self, topics, on_assign, on_revoke): on_assign(self, [])
        def list_topics(self, timeout): return None
        def poll(self, timeout):
            if getattr(self, 'sent', False):
                runtime.stop_event.set()
                return None
            self.sent = True
            return Message()
        def commit(self, message, asynchronous):
            assert runtime.store.latest('prediction') is not None
            self.committed.append(message.offset())
        def close(self): pass

    reader = Reader({})
    monkeypatch.setattr(module, 'Consumer', lambda config: reader)
    if store_fails:
        def fail(*args): raise RuntimeError('Disk write failure')
        monkeypatch.setattr(runtime.store, 'put', fail)
    runtime.consume()
    assert reader.committed == ([] if store_fails else [10])
    assert runtime.failed is store_fails
    assert runtime.ready is False
    runtime.close()


def test_completed_sensor_replay_is_not_completed_inference(api):
    client, runtime, _ = api
    replay = client.app.state.replay
    replay.state = dict(status='completed', sent=100, run_id='run', trajectory_key='case1::1',
                        started_at='2000-01-01T00:00:00+00:00', last_sent_timestamp_hours=4.95)
    runtime.store.put('prediction', 'topic', 0, 0, prediction(timestamp=1))
    assert client.get('/v1/replay').json()['inference_caught_up'] is False
    assert client.post('/v1/replay/start', json={'trajectory_key': 'case1::1'}).status_code == 409
    runtime.store.put('prediction', 'topic', 0, 1, prediction(timestamp=4.95))
    assert client.get('/v1/replay').json()['inference_caught_up'] is True


def test_existing_raw_parent_environment_finds_nested_tep(api):
    client, _, settings = api
    nested = settings.raw_dir/'TEP'
    nested.mkdir(parents=True)
    (nested/'case1.csv').touch()
    items = client.get('/v1/trajectories').json()['items']
    assert next(row for row in items if row['trajectory_key'] == 'case1::1')['raw_available']
    assert not next(row for row in items if row['trajectory_key'] == 'case2::1')['raw_available']
