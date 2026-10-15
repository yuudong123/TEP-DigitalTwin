from copy import deepcopy

from deploy.verify_recovery import compare


def snapshot():
    return {'predictions': [{'prediction': {'trajectory_key': 'case1::1'}, 'received_at': 'original'}],
            'watermarks': {'tep-predictions:0': {'low': 0, 'high': 123}},
            'kafka_volume': 'tep-kafka-data',
            'services': {'tep-api': {'running': True, 'health': 'healthy'}}}


def test_receipt_timestamp_must_survive_cold_restart():
    before = snapshot()
    after = deepcopy(before)
    after['predictions'][0]['received_at'] = 'refreshed'
    assert compare(before, after) == ['Prediction snapshots or original receipt timestamps changed']


def test_kafka_history_and_volume_cannot_be_reset():
    before = snapshot()
    after = deepcopy(before)
    after['watermarks']['tep-predictions:0']['high'] = 100
    after['kafka_volume'] = 'temporary'
    assert len(compare(before, after)) == 2


def test_no_data_loss_and_healthy_services_pass():
    before = snapshot()
    after = deepcopy(before)
    after['watermarks']['tep-predictions:0']['high'] += 1
    assert compare(before, after) == []


def test_unhealthy_service_is_not_a_recovery_pass():
    before = snapshot()
    after = deepcopy(before)
    after['services']['tep-api']['health'] = 'unhealthy'
    assert compare(before, after) == ['A TEP service is not ready']
