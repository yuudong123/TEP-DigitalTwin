"""One explicit, cancellable replay run at a time, from whitelisted CSVs."""
import csv
import threading
import time
from uuid import uuid4

from confluent_kafka import Producer
from kafka.delivery import publish_json
from kafka.message_schema import build_sensor_message
from kafka.topic_admin import ensure_topic


class ReplayController:
    ACTIVE = {'running', 'paused', 'stopping'}

    def __init__(self, settings, catalog):
        self.settings = settings
        self.catalog = {row['trajectory_key']: row for row in catalog}
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.thread = None
        self.state = {'status': 'idle', 'sent': 0, 'run_id': None}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def start(self, key, interval):
        with self.lock:
            if self.state['status'] in self.ACTIVE:
                raise RuntimeError('A replay is already active')
            if key not in self.catalog:
                raise ValueError('Unknown trajectory')
            row = self.catalog[key]
            path = self.settings.raw_dir / (row['case'] + '.csv')
            if not path.is_file():
                raise FileNotFoundError('Raw CSV is not available on this host')
            self.state = dict(status='running', sent=0, run_id=str(uuid4()),
                              trajectory_key=key, total=int(row['row_count']), error=None)
            self.thread = threading.Thread(target=self.run, args=(row, path, interval), daemon=True)
            self.thread.start()
            return dict(self.state)

    def command(self, action):
        with self.condition:
            current = self.state['status']
            required = {'pause': 'running', 'resume': 'paused'}
            if action in required and current != required[action]:
                raise RuntimeError(f'Cannot {action} a {current} replay')
            if action == 'stop' and current not in self.ACTIVE:
                raise RuntimeError('No active replay')
            self.state['status'] = {'pause': 'paused', 'resume': 'running', 'stop': 'stopping'}[action]
            self.condition.notify_all()
            return dict(self.state)

    def wait_ready(self):
        with self.condition:
            while self.state['status'] == 'paused':
                self.condition.wait()
            return self.state['status'] != 'stopping'

    def run(self, row, path, interval):
        try:
            ensure_topic(self.settings.bootstrap, self.settings.sensor_topic)
            producer = Producer({'bootstrap.servers': self.settings.bootstrap, 'acks': 'all',
                                 'enable.idempotence': True, 'message.timeout.ms': 10000})
            with path.open(newline='', encoding='utf-8-sig') as stream:
                previous_time = None
                for sensor_row in csv.DictReader(stream):
                    if not self.wait_ready():
                        break
                    if int(float(sensor_row['Id'])) != int(row['Id']):
                        continue
                    with self.lock:
                        sequence = self.state['sent']
                    sensor = build_sensor_message(row['case'], sensor_row, sequence)
                    timestamp = sensor['timestamp_hours']
                    if previous_time is not None and abs(timestamp - previous_time - .05) > 1e-6:
                        raise ValueError('Raw trajectory is not contiguous')
                    publish_json(producer, self.settings.sensor_topic, sensor['trajectory_key'], sensor)
                    previous_time = timestamp
                    with self.condition:
                        self.state['sent'] += 1
                        # Interruptible pacing; a pause applies before the next publish.
                        deadline = time.monotonic() + interval
                        while self.state['status'] == 'running' and time.monotonic() < deadline:
                            self.condition.wait(deadline - time.monotonic())
            with self.lock:
                if self.state['status'] == 'stopping':
                    self.state['status'] = 'stopped'
                elif self.state['sent'] != self.state['total']:
                    raise ValueError('CSV row count differs from metadata')
                else:
                    self.state['status'] = 'completed'
        except Exception as error:
            with self.lock:
                self.state.update(status='failed', error=type(error).__name__)

    def close(self):
        with self.condition:
            if self.state['status'] in self.ACTIVE:
                self.state['status'] = 'stopping'
                self.condition.notify_all()
        if self.thread:
            self.thread.join(15)
