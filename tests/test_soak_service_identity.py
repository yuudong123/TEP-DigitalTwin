from copy import deepcopy

import pytest

from deploy.verify_soak import services_unchanged


def service():
    return {'tep-api': {'id': 'original', 'image': 'original-image', 'started_at': 'original-start',
                        'running': True, 'health': 'healthy', 'restarts': 0}}


@pytest.mark.parametrize('field,value', [
    ('id', 'replacement'), ('image', 'different-image'), ('started_at', 'later-start'),
    ('restarts', 1), ('health', 'unhealthy'),
])
def test_replacement_or_restart_is_not_silently_accepted(field, value):
    before = service()
    after = deepcopy(before)
    after['tep-api'][field] = value
    assert not services_unchanged(before, after)


def test_steady_services_are_accepted():
    assert services_unchanged(service(), service())


def test_empty_inventory_is_not_a_pass():
    assert not services_unchanged({}, {})
