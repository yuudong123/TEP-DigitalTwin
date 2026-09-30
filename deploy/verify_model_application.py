"""Real CSV + real Kafka + HTTP hot application, rejection and rollback proof.

Requires isolated service topics, registry and logs. Never point at production.
The control candidate is the original model under a different metadata version,
not a newly trained or improved model.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

import httpx
from confluent_kafka import Consumer, Producer
from kafka.delivery import publish_json
from kafka.message_schema import build_sensor_message
from src.inference.prediction_schema import validate_prediction
from src.lifecycle.registry import atomic_json, file_sha256, promote, rollback


def verify(args):
    base = Path(args.runtime_dir)
    if 'logs' not in base.resolve().parts or not args.sensor_topic.startswith('model-proof-'):
        raise ValueError('Only explicitly isolated logs/model-proof-* settings are accepted')
    registry, candidate, report, pointer = base/'registry', base/'candidate', base/'evaluation.json', base/'model-active.json'
    if pointer.exists():
        raise ValueError('Use a fresh isolated pointer for this proof')
    history = []
    with (Path(args.raw_dir)/'case1.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if int(float(row['Id'])) == 1:
                history.append(build_sensor_message('case1', row, len(history)))
                if len(history) == 30:
                    break
    producer = Producer({'bootstrap.servers': args.bootstrap, 'acks': 'all',
                         'enable.idempotence': True, 'message.timeout.ms': 10000})
    consumer = Consumer({'bootstrap.servers': args.bootstrap, 'group.id': 'model-proof-check-'+uuid4().hex,
                         'auto.offset.reset': 'earliest', 'enable.auto.commit': False})
    consumer.subscribe([args.prediction_topic])
    events = []
    with httpx.Client(base_url=args.api_url, timeout=20, trust_env=False) as client:
        client.get('/health/ready').raise_for_status()

        def receive(first, last, version):
            for sensor in history[first:last]:
                publish_json(producer, args.sensor_topic, sensor['trajectory_key'], sensor)
            count = last-first if first >= 20 else last-20
            start = time.monotonic()
            current = []
            while len(current) < count and time.monotonic()-start < 60:
                message = consumer.poll(.5)
                if not message:
                    continue
                if message.error():
                    raise RuntimeError(message.error())
                body = json.loads(message.value())
                validate_prediction(body)
                assert body['model_version'] == version
                current.append(body)
                events.append({'model_version': body['model_version'], 'timestamp_hours': body['timestamp_hours']})
            assert len(current) == count
            return current[-1]

        def direct(version):
            response = client.post('/v1/predict', json={'history': history[:21]})
            response.raise_for_status()
            validate_prediction(response.json())
            assert response.json()['model_version'] == version

        try:
            baseline = receive(0, 21, 'v1.0.0')
            direct('v1.0.0')
            state = promote(candidate, report, file_sha256(report), registry, pointer, registry/'v1.0.0')
            time.sleep(1.2)  # Documented 1-second pointer refresh gate.
            applied = receive(21, 24, 'v1.0.0-control')
            direct('v1.0.0-control')
            corrupted = dict(state, generation='rejection-proof-'+uuid4().hex,
                             active=dict(state['active'], relative_dir='../candidate'))
            atomic_json(pointer, corrupted)
            time.sleep(1.2)
            retained = receive(24, 27, 'v1.0.0-control')
            direct('v1.0.0-control')
            acknowledgements = {name: json.loads((base/f'model-status-{name}.json').read_text(encoding='utf-8'))
                                for name in ('api', 'inference')}
            assert all(item['status'] == 'rejected_retaining_previous' for item in acknowledgements.values())
            # Restore only this proof's previously approved pointer, then test
            # the public rollback operation with its exact generation guard.
            atomic_json(pointer, state)
            restored = rollback(registry, pointer, state['generation'])
            time.sleep(1.2)
            after = receive(27, 30, 'v1.0.0')
            direct('v1.0.0')
            result = dict(time=datetime.now(timezone.utc).isoformat(), source='real_case1_csv',
                          sensors=30, predictions=len(events), versions=events,
                          api_synchronous_versions=['v1.0.0', 'v1.0.0-control', 'v1.0.0-control', 'v1.0.0'],
                          failed_application_retained_previous=True, rollback=True,
                          baseline_timestamp=baseline['timestamp_hours'], applied_timestamp=applied['timestamp_hours'],
                          retained_timestamp=retained['timestamp_hours'], rollback_timestamp=after['timestamp_hours'],
                          final_generation=restored['generation'], evaluation_report_sha256=file_sha256(report),
                          improved_model=False, isolated_only=True)
            atomic_json(base/'application-proof.json', result)
            print(json.dumps(result, ensure_ascii=False))
        finally:
            consumer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', required=True)
    parser.add_argument('--bootstrap', default='localhost:9092')
    parser.add_argument('--sensor-topic', required=True)
    parser.add_argument('--prediction-topic', required=True)
    parser.add_argument('--runtime-dir', required=True)
    parser.add_argument('--raw-dir', default='data/raw/TEP')
    verify(parser.parse_args())
