"""Explicit real CSV replay acceptance. Never fabricates sensors/predictions.

Run only against an idle development replay, not a concurrent production feed.
Topic arguments must refer to the services' matching configured topics.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

import httpx
from confluent_kafka import Consumer
from kafka.message_schema import build_sensor_message
from src.inference.prediction_schema import validate_prediction


def verify(args):
    started = time.monotonic()
    with httpx.Client(base_url=args.api_url, timeout=15, trust_env=False) as client:
        client.get('/health/ready').raise_for_status()
        catalog = client.get('/v1/trajectories').json()['items']
        row = next(item for item in catalog if item['trajectory_key'] == args.trajectory)
        if not row['raw_available']:
            raise RuntimeError('API does not have the raw CSV')
        response = client.get('/')
        response.raise_for_status()
        if '<div id="root">' not in response.text:
            raise RuntimeError('Web was not served by the API')
        consumer = Consumer({'bootstrap.servers': args.bootstrap, 'group.id': 'live-proof-'+uuid4().hex,
                             'auto.offset.reset': 'earliest', 'enable.auto.commit': False})
        consumer.subscribe([args.prediction_topic])
        predictions = []
        history = []
        with (Path(args.raw_dir)/(row['case']+'.csv')).open(encoding='utf-8-sig', newline='') as stream:
            for record in csv.DictReader(stream):
                if int(float(record['Id'])) == int(row['Id']):
                    history.append(build_sensor_message(row['case'], record, len(history)))
                    if len(history) == 21:
                        break
        direct = client.post('/v1/predict', json={'history': history})
        direct.raise_for_status()
        validate_prediction(direct.json())
        run = client.post('/v1/replay/start', json={'trajectory_key': args.trajectory, 'interval_seconds': .01})
        run.raise_for_status()
        # Control-plane assertions on real replay. Already-in-flight one row may finish.
        client.post('/v1/replay/pause').raise_for_status()
        assert client.get('/v1/replay').json()['status'] == 'paused'
        conflict = client.post('/v1/replay/start', json={'trajectory_key': args.trajectory})
        assert conflict.status_code == 409
        client.post('/v1/replay/resume').raise_for_status()
        expected = int(row['row_count']) - 20
        try:
            while time.monotonic() - started < args.timeout:
                message = consumer.poll(.1)
                if message and message.error():
                    raise RuntimeError(message.error())
                if message:
                    payload = json.loads(message.value())
                    validate_prediction(payload)
                    assert message.key().decode() == payload['trajectory_key'] == args.trajectory
                    predictions.append(payload)
                    if len(predictions) > expected:
                        raise RuntimeError('Unexpected duplicate/foreign predictions; use isolated topics')
                if len(predictions) == expected:
                    final = client.get('/v1/replay').json()
                    latest = client.get('/api/predictions/latest', params={'trajectory_key': args.trajectory})
                    if final['status'] == 'completed' and latest.json().get('timestamp_hours') == float(row['end_time']):
                        break
            else:
                raise TimeoutError(f'Only {len(predictions)}/{expected} predictions')
        finally:
            consumer.close()
        assert final['sent'] == int(row['row_count'])
        expected_times = [round((index+20)*.05, 6) for index in range(expected)]
        assert [round(item['timestamp_hours'], 6) for item in predictions] == expected_times
        assert direct.json() == predictions[0]
        validate_prediction(latest.json())
        monitor = client.get('/v1/monitoring/latest', params={'trajectory_key': args.trajectory})
        monitor.raise_for_status()
        assert monitor.json()['event']['retraining_requested'] is False
        report = dict(time=datetime.now(timezone.utc).isoformat(), trajectory=args.trajectory,
                      source='real_raw_csv', sensors=final['sent'], predictions=len(predictions),
                      first_timestamp=predictions[0]['timestamp_hours'], last_timestamp=predictions[-1]['timestamp_hours'],
                      synchronous_matches_first_kafka_prediction=True, replay_pause_resume_conflict=True,
                      web_http=True, monitoring_event=True, retraining_requested=False,
                      latest=latest.json(), received_at=latest.headers['x-prediction-received-at'],
                      elapsed_seconds=round(time.monotonic()-started, 3))
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k not in ('latest',)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', required=True)
    parser.add_argument('--bootstrap', default='localhost:9092')
    parser.add_argument('--prediction-topic', required=True)
    parser.add_argument('--trajectory', default='case1::1')
    parser.add_argument('--raw-dir', default='data/raw/TEP')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--output', required=True)
    verify(parser.parse_args())
