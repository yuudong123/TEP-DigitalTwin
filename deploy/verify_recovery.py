"""Read-only proof around an externally controlled TEP cold stop/start.

Capture while replay is idle and caught up, stop/start using the desktop scripts,
then verify all persisted prediction receipts and Kafka high-water marks.
This tool never starts or stops services itself.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from confluent_kafka import Consumer, TopicPartition
import httpx

from deploy.verify_soak import inspect_services


def compare(before, after):
    issues = []
    if before['predictions'] != after['predictions']:
        issues.append('Prediction snapshots or original receipt timestamps changed')
    if before['kafka_volume'] != 'tep-kafka-data' or after['kafka_volume'] != before['kafka_volume']:
        issues.append('Persistent Kafka volume changed')
    for key, watermark in before['watermarks'].items():
        if key not in after['watermarks'] or after['watermarks'][key]['high'] < watermark['high']:
            issues.append('Kafka history was lost: ' + key)
    if any(not row['running'] or row['health'] not in (None, 'healthy') for row in after['services'].values()):
        issues.append('A TEP service is not ready')
    return issues


def capture(api_url, bootstrap):
    with httpx.Client(base_url=api_url, timeout=15, trust_env=False) as client:
        client.get('/health/ready').raise_for_status()
        replay = client.get('/v1/replay')
        replay.raise_for_status()
        replay = replay.json()
        if replay['status'] in ('running', 'paused', 'stopping') or not replay['inference_caught_up']:
            raise RuntimeError('Recovery proof requires idle replay with no backlog')
        predictions = client.get('/v1/predictions')
        predictions.raise_for_status()
        snapshots = predictions.json()['items']
        if not snapshots:
            raise RuntimeError('No persisted predictions to verify')
    consumer = Consumer({'bootstrap.servers': bootstrap, 'group.id': 'recovery-observer-'+uuid4().hex,
                         'enable.auto.commit': False})
    watermarks = {}
    try:
        for topic in ('tep-sensor-data', 'tep-predictions', 'tep-drift-events'):
            metadata = consumer.list_topics(topic, timeout=10).topics[topic]
            if metadata.error:
                raise RuntimeError(metadata.error)
            for partition in metadata.partitions:
                low, high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=10)
                watermarks[f'{topic}:{partition}'] = {'low': low, 'high': high}
    finally:
        consumer.close()
    result = subprocess.run(['docker', 'inspect', 'tep-kafka'], check=True,
                            capture_output=True, text=True, timeout=30)
    kafka = json.loads(result.stdout)[0]
    mounts = [mount['Name'] for mount in kafka['Mounts'] if mount['Type'] == 'volume'
              and mount['Destination'] == '/tmp/kraft-combined-logs']
    return {'time': datetime.now(timezone.utc).isoformat(), 'predictions': snapshots,
            'watermarks': watermarks, 'kafka_volume': mounts[0] if len(mounts) == 1 else None,
            'services': inspect_services()}


def main(args):
    state = Path(args.state)
    current = capture(args.api_url, args.bootstrap)
    if args.mode == 'capture':
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'captured': True, 'prediction_snapshots': len(current['predictions']), 'state': str(state)}))
        return 0
    prior = json.loads(state.read_text(encoding='utf-8'))
    issues = compare(prior, current)
    report = {'passed': not issues, 'issues': issues, 'scope': 'controlled cold stop/start; not a new PC reboot',
              'before_time': prior['time'], 'after_time': current['time'],
              'prediction_snapshots_unchanged': prior['predictions'] == current['predictions'],
              'snapshot_count': len(current['predictions']), 'kafka_volume': current['kafka_volume'],
              'before_watermarks': prior['watermarks'], 'after_watermarks': current['watermarks'],
              'services': current['services']}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return int(bool(issues))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('capture', 'verify'), required=True)
    parser.add_argument('--api-url', default='http://127.0.0.1:8000')
    parser.add_argument('--bootstrap', default='localhost:9092')
    parser.add_argument('--state', required=True)
    parser.add_argument('--output', default='reports/26-final/cold-recovery.json')
    raise SystemExit(main(parser.parse_args()))
