"""Reject one real prediction on an isolated topic, then prove offset recovery.

Requires the isolated model-proof run after its first 30 real sensor rows.
Production topic/container names are intentionally refused.
"""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import time

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, AlterConfigOpType, ConfigEntry, ConfigResource, ConfigSource, ResourceType

from kafka.delivery import publish_json
from kafka.message_schema import build_sensor_message
from src.inference.prediction_schema import validate_prediction
from src.lifecycle.registry import atomic_json


def verify(args):
    prefix = args.container.removesuffix('-inference')
    if (not prefix.startswith('model-proof-') or args.container != prefix+'-inference'
        or args.sensor_topic != prefix+'-sensor' or args.prediction_topic != prefix+'-prediction'
        or args.group != prefix+'-infer'):
        raise ValueError('This destructive rejection test is restricted to one isolated proof namespace')
    history = []
    with (Path(args.raw_dir)/'case1.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if int(float(row['Id'])) == 1:
                history.append(build_sensor_message('case1', row, len(history)))
                if len(history) == 51:
                    break
    consumer = Consumer({'bootstrap.servers': args.bootstrap, 'group.id': args.group,
                         'enable.auto.commit': False})
    producer = Producer({'bootstrap.servers': args.bootstrap, 'acks': 'all',
                         'enable.idempotence': True, 'message.timeout.ms': 10000})
    admin = AdminClient({'bootstrap.servers': args.bootstrap})
    resource = ConfigResource(ResourceType.TOPIC, args.prediction_topic)
    original = admin.describe_configs([resource])[resource].result(15)['max.message.bytes']

    def configure(value, operation):
        updated = ConfigResource(ResourceType.TOPIC, args.prediction_topic, incremental_configs=[
            ConfigEntry('max.message.bytes', value, incremental_operation=operation)])
        admin.incremental_alter_configs([updated])[updated].result(15)

    def offset():
        return consumer.committed([TopicPartition(args.sensor_topic, 0)], timeout=10)[0].offset

    def state():
        result = subprocess.run([args.docker, 'inspect', '--format', '{{json .State}}', args.container],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    try:
        before = offset()
        assert before == 30
        configure('1', AlterConfigOpType.SET)
        try:
            publish_json(producer, args.sensor_topic, 'case1::1', history[30])
            deadline = time.monotonic()+30
            while state()['Running'] and time.monotonic() < deadline:
                time.sleep(.5)
            assert not state()['Running'] and state()['ExitCode'] != 0
            failed_offset = offset()
            assert failed_offset == before
        finally:
            if original.source == ConfigSource.DYNAMIC_TOPIC_CONFIG:
                configure(original.value, AlterConfigOpType.SET)
            else:
                configure(None, AlterConfigOpType.DELETE)
        output_before = consumer.get_watermark_offsets(TopicPartition(args.prediction_topic, 0), timeout=10)[1]
        subprocess.run([args.docker, 'restart', args.container], check=True, capture_output=True)
        time.sleep(3)
        consumer.assign([TopicPartition(args.prediction_topic, 0, output_before)])
        for sensor in history[31:51]:
            publish_json(producer, args.sensor_topic, 'case1::1', sensor)
        deadline = time.monotonic()+30
        recovered = None
        while time.monotonic() < deadline:
            message = consumer.poll(.5)
            if message and message.error():
                raise RuntimeError(message.error())
            if message:
                recovered = json.loads(message.value())
                validate_prediction(recovered)
                break
        assert recovered and recovered['timestamp_hours'] == 2.5
        deadline = time.monotonic()+10
        while offset() != 51 and time.monotonic() < deadline:
            time.sleep(.2)
        assert offset() == 51 and state()['Running']
        result = dict(scenario='actual_inference_delivery_rejection_and_restart', source='real_case1_csv',
                      committed_before=before, committed_after_failure=failed_offset,
                      committed_after_recovery=51, failed_input_offset=30,
                      output_before_recovery=output_before, recovered_timestamp=2.5,
                      warmup_after_restart_rows=21, failed_input_reread=True,
                      topic_configuration_restored=True, isolated_only=True)
        atomic_json(args.output, result)
        print(json.dumps(result))
    finally:
        consumer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('container', 'sensor-topic', 'prediction-topic', 'group', 'raw-dir', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--bootstrap', default='localhost:9092')
    parser.add_argument('--docker', default='docker')
    verify(parser.parse_args())
