from pathlib import Path
import pytest
from src.inference.model_loader import ProductionPredictor


@pytest.mark.parametrize('value', [0, -1, True, 1.5])
def test_unsafe_thread_configuration_is_rejected_before_loading_models(value):
    with pytest.raises(ValueError, match='positive integer'):
        ProductionPredictor(Path('unused'), threads=value)


def test_environment_cannot_enable_unrestricted_inference(monkeypatch):
    monkeypatch.setenv('INFERENCE_THREADS', '0')
    with pytest.raises(ValueError, match='positive integer'):
        ProductionPredictor(Path('unused'))
