"""Timed acceptance using real CSV replays, read-only Kafka observers and runtime sampling."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import httpx
from confluent_kafka import Consumer, TopicPartition
from src.inference.prediction_schema import validate_prediction
from src.monitoring.event_schema import validate_drift_event


def inspect_services():
    result = subprocess.run(['docker', 'inspect', 'tep-kafka', 'tep-api', 'tep-inference', 'tep-monitor'],
                            check=True, capture_output=True, text=True)
    return {item['Name'].removeprefix('/'): {'running': item['State']['Running'],
            'health': item['State'].get('Health', {}).get('Status'), 'restarts': item['RestartCount']}
            for item in json.loads(result.stdout)}


def assign_latest(consumer, topics):
    partitions = []
    for topic in topics:
        info = consumer.list_topics(topic, timeout=10).topics[topic]
        if info.error:
            raise RuntimeError(info.error)
        for partition in info.partitions:
            high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=10)[1]
            partitions.append(TopicPartition(topic, partition, high))
    consumer.assign(partitions)


def verify(args):
    if args.seconds <= 0 or not .01 <= args.interval <= 10:
        raise ValueError('A positive duration and .01..10 second interval are required')
    started = time.monotonic()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), source='real_test_split_csv',
                  requested_seconds=args.seconds, interval_seconds=args.interval, passed=False,
                  runs=[], samples=[], predictions=0, monitor_events=0, calibrated_events=0, errors=[])
    expected_hash = args.calibration_sha256
    consumer = Consumer({'bootstrap.servers': args.bootstrap, 'group.id': 'soak-observer-'+uuid4().hex,
                         'enable.auto.commit': False})
    owns_replay = False
    with httpx.Client(base_url=args.api_url, timeout=15, trust_env=False) as client:
        initial_services = inspect_services()
        if not all(value['running'] for value in initial_services.values()):
            raise RuntimeError('All four TEP services must be running')
        catalog = client.get('/v1/trajectories').json()['items']
        with Path(args.split_manifest).open(encoding='utf-8-sig', newline='') as stream:
            test_keys = {row['trajectory_key'] for row in csv.DictReader(stream) if row['split'] == 'test'}
        candidates = [row for row in catalog if row['raw_available'] and row['trajectory_key'] in test_keys]
        selected = [next(row for row in candidates if row['case'] == 'case'+str(number)) for number in range(1, 7)]
        try:
            assign_latest(consumer, [args.prediction_topic, args.monitor_topic])
            index = 0
            while time.monotonic()-started < args.seconds:
                previous = client.get('/v1/replay').json()
                if previous['status'] in ('running', 'paused', 'stopping') or previous.get('inference_caught_up') is False:
                    raise RuntimeError('A replay or its backlog is active; soak will not interrupt it')
                row = selected[index % len(selected)]
                current = {'trajectory': row['trajectory_key'], 'predictions': 0, 'last_timestamp': None,
                           'total_sensors': int(row['row_count']), 'complete': False}
                response = client.post('/v1/replay/start', json={'trajectory_key': current['trajectory'], 'interval_seconds': args.interval})
                response.raise_for_status()
                owns_replay = True
                report['runs'].append(current)
                last_sample = 0
                while True:
                    message = consumer.poll(.1)
                    if message and message.error():
                        raise RuntimeError(message.error())
                    if message:
                        payload = json.loads(message.value())
                        if message.topic() == args.prediction_topic:
                            validate_prediction(payload)
                            if payload['trajectory_key'] != current['trajectory']:
                                raise RuntimeError('Foreign prediction arrived during controlled soak')
                            expected_time = round((current['predictions']+20)*.05, 6)
                            if abs(payload['timestamp_hours']-expected_time) > 1e-6:
                                raise RuntimeError('Prediction gap, duplicate, or ordering error')
                            current['predictions'] += 1
                            current['last_timestamp'] = payload['timestamp_hours']
                            report['predictions'] += 1
                        else:
                            validate_drift_event(payload)
                            report['monitor_events'] += 1
                            if payload['retraining_requested']:
                                raise RuntimeError('Unexpected automatic retraining request')
                            if payload.get('calibration_sha256') != expected_hash:
                                raise RuntimeError('Monitor is not using the selected calibration')
                            if payload['status'] != 'INSUFFICIENT_DATA':
                                report['calibrated_events'] += 1
                    elapsed = time.monotonic()-started
                    if elapsed-last_sample >= 30 or last_sample == 0:
                        state = client.get('/v1/replay').json()
                        ready = client.get('/health/ready')
                        ready.raise_for_status()
                        services = inspect_services()
                        if any(not value['running'] or value['restarts'] != initial_services[name]['restarts']
                               or value['health'] not in (None, 'healthy') for name, value in services.items()):
                            raise RuntimeError('Container stopped, became unhealthy or restarted during soak')
                        if ready.json()['reader_failed'] or ready.json()['invalid_messages']:
                            raise RuntimeError('API reader failed or received invalid messages')
                        stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}',
                                                'tep-kafka','tep-api','tep-inference','tep-monitor'], check=True, capture_output=True, text=True)
                        sample = {'elapsed_seconds': round(elapsed, 1), 'trajectory': current['trajectory'],
                                  'sent': state['sent'], 'predictions': current['predictions'],
                                  'services': services, 'resources': [json.loads(line) for line in stats.stdout.splitlines() if line]}
                        report['samples'].append(sample)
                        last_sample = elapsed
                        output.with_suffix('.progress.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                        print(json.dumps({key: sample[key] for key in ('elapsed_seconds','trajectory','sent','predictions')}, ensure_ascii=False), flush=True)
                    if current['predictions'] == current['total_sensors']-20:
                        final = client.get('/v1/replay').json()
                        if final['status'] == 'completed' and final['inference_caught_up']:
                            current['complete'] = True
                            current['sent'] = final['sent']
                            owns_replay = False
                            break
                    if elapsed >= args.seconds and owns_replay:
                        state = client.get('/v1/replay').json()
                        if state['status'] in ('running', 'paused'):
                            client.post('/v1/replay/stop').raise_for_status()
                        finish_deadline = time.monotonic()+180
                        while time.monotonic() < finish_deadline:
                            message = consumer.poll(.2)
                            if message and message.error():
                                raise RuntimeError(message.error())
                            if message and message.topic() == args.prediction_topic:
                                payload = json.loads(message.value())
                                validate_prediction(payload)
                                if payload['trajectory_key'] != current['trajectory'] or abs(payload['timestamp_hours']-(current['predictions']+20)*.05) > 1e-6:
                                    raise RuntimeError('Final drain ordering error')
                                current['predictions'] += 1
                                report['predictions'] += 1
                                current['last_timestamp'] = payload['timestamp_hours']
                            elif message:
                                payload = json.loads(message.value()); validate_drift_event(payload)
                                report['monitor_events'] += 1
                                if payload.get('calibration_sha256') != expected_hash or payload['retraining_requested']:
                                    raise RuntimeError('Final drain monitoring error')
                            final = client.get('/v1/replay').json()
                            if final['status'] in ('completed','stopped') and final['inference_caught_up'] and current['predictions'] == max(0,final['sent']-20):
                                current['sent'] = final['sent']; current['complete'] = final['status'] == 'completed'; owns_replay = False; break
                        if owns_replay:
                            raise TimeoutError('Backlog failed to drain after timed replay stop')
                        break
                index += 1
            report['elapsed_seconds'] = round(time.monotonic()-started, 1)
            report['calibration_sha256'] = expected_hash
            report['final_services'] = inspect_services()
            report['passed'] = report['elapsed_seconds'] >= args.seconds and report['predictions'] > 0 and report['calibrated_events'] > 0
            if not report['passed']:
                raise AssertionError('Soak acceptance conditions were not all demonstrated')
        except Exception as error:
            report['errors'].append(str(error))
            report['elapsed_seconds'] = round(time.monotonic()-started, 1)
            raise
        finally:
            if owns_replay:
                try: client.post('/v1/replay/stop')
                except Exception: pass
            consumer.close()
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('passed','elapsed_seconds','predictions','monitor_events','calibrated_events')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', default='http://127.0.0.1:8000')
    parser.add_argument('--bootstrap', default='localhost:9092')
    parser.add_argument('--prediction-topic', default='tep-predictions')
    parser.add_argument('--monitor-topic', default='tep-drift-events')
    parser.add_argument('--split-manifest', default='data/metadata/split_manifest.csv')
    parser.add_argument('--seconds', type=float, default=3600)
    parser.add_argument('--interval', type=float, default=.1)
    parser.add_argument('--calibration-sha256', default='5e99120bdaf854e703c98ff8fca54f59e38544c3d57f818ef912d47713e600b1')
    parser.add_argument('--output', required=True)
    verify(parser.parse_args())
