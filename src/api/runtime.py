"""Kafka -> validated SQLite snapshots; HTTP never impersonates live data."""
import json
import logging
import threading
import time

from confluent_kafka import Consumer, KafkaError
from kafka.topic_admin import ensure_topic
from src.inference.prediction_schema import validate_prediction
from .store import SnapshotStore


class PredictionRuntime:
    def __init__(self, settings):
        self.settings = settings
        self.store = SnapshotStore(settings.store_path)
        self.stop_event = threading.Event()
        self.thread = None
        self.ready = False
        self.failed = False
        self.invalid_messages = 0
        self.predict_lock = threading.Lock()
        self.predictor = None
        self.assigned = False

    def start(self):
        # Lazy import keeps contract tests independent of native model binaries.
        from src.inference.managed_model import model_from_environment
        self.predictor = model_from_environment(self.settings.model_dir, 'api')
        for topic in (self.settings.prediction_topic, self.settings.monitor_topic):
            ensure_topic(self.settings.bootstrap, topic)
        self.thread = threading.Thread(target=self.consume, daemon=True, name='api-kafka')
        self.thread.start()

    def consume(self):
        consumer = Consumer({
            'bootstrap.servers': self.settings.bootstrap,
            'group.id': self.settings.consumer_group,
            'auto.offset.reset': 'earliest', 'enable.auto.commit': False,
        })
        consumer.subscribe([self.settings.prediction_topic, self.settings.monitor_topic],
                           on_assign=lambda _c, _p: setattr(self, 'assigned', True),
                           on_revoke=lambda _c, _p: self.revoked())
        last_probe = 0.0
        try:
            while not self.stop_event.is_set():
                if time.monotonic() - last_probe > 5:
                    last_probe = time.monotonic()
                    try:
                        consumer.list_topics(timeout=3)
                        self.ready = self.assigned
                    except Exception:
                        self.ready = False
                message = consumer.poll(1)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise RuntimeError(message.error())
                kind = 'prediction' if message.topic() == self.settings.prediction_topic else 'monitoring'
                try:
                    body = json.loads(message.value().decode())
                    if not isinstance(body, dict):
                        raise ValueError('Payload must be an object')
                    if kind == 'prediction':
                        validate_prediction(body)
                    else:
                        from src.monitoring.event_schema import validate_drift_event
                        validate_drift_event(body)
                    if message.key() is None or message.key().decode() != body['trajectory_key']:
                        raise ValueError('Kafka key mismatch')
                except (ValueError, TypeError, KeyError, AttributeError):
                    self.invalid_messages += 1
                    logging.warning('Rejected %s message at offset %s', kind, message.offset())
                    consumer.commit(message=message, asynchronous=False)
                    continue
                self.store.put(kind, message.topic(), message.partition(), message.offset(), body)
                consumer.commit(message=message, asynchronous=False)
        except Exception:
            self.failed = True
            logging.exception('API Kafka reader stopped')
        finally:
            self.ready = False
            consumer.close()

    def revoked(self):
        self.assigned = False
        self.ready = False

    def predict(self, history):
        from src.inference.temporal_features import TrajectoryFeatureBuffer
        buffer = TrajectoryFeatureBuffer(self.predictor.features)
        for sensor in history:
            latest = buffer.add(sensor)
        if not latest.ready:
            raise ValueError('A contiguous 60-minute history is required')
        with self.predict_lock:
            return self.predictor.predict(latest.features, latest.trajectory_key, latest.timestamp_hours)

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(15)
            if self.thread.is_alive():
                # Do not close SQLite while the worker can still write it.
                return
        self.store.close()
