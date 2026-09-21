from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from kafka.producer import PROJECT_ROOT, get_data_raw_dir, resolve_case_csv_path
from kafka.topic_admin import ensure_topic


def test_data_raw_dir_defaults_to_tep_directory():
    with patch.dict("os.environ", {}, clear=True):
        assert get_data_raw_dir() == PROJECT_ROOT / "data" / "raw" / "TEP"


def test_case_path_supports_existing_nested_tep_layout(tmp_path):
    case_path = tmp_path / "TEP" / "case1.csv"
    case_path.parent.mkdir()
    case_path.touch()

    with patch.dict("os.environ", {"DATA_RAW_DIR": str(tmp_path)}):
        assert resolve_case_csv_path("case1") == case_path


def test_absolute_data_raw_dir_is_preserved(tmp_path):
    with patch.dict("os.environ", {"DATA_RAW_DIR": str(tmp_path)}):
        assert get_data_raw_dir() == Path(tmp_path)


@patch("kafka.topic_admin.AdminClient")
def test_existing_topic_is_reused(admin_client_class):
    admin = admin_client_class.return_value
    admin.list_topics.return_value = SimpleNamespace(
        topics={"tep-sensor-data": SimpleNamespace(error=None)}
    )

    assert ensure_topic("localhost:9092", "tep-sensor-data") is False
    admin.create_topics.assert_not_called()


@patch("kafka.topic_admin.AdminClient")
def test_missing_topic_is_created(admin_client_class):
    admin = admin_client_class.return_value
    admin.list_topics.return_value = SimpleNamespace(topics={})
    future = Mock()
    admin.create_topics.return_value = {"tep-sensor-data": future}

    assert ensure_topic("localhost:9092", "tep-sensor-data") is True
    future.result.assert_called_once_with(timeout=10.0)
