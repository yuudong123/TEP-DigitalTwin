from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def project_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    # Application
    app_env: str = env_str(
        "APP_ENV",
        "development",
    )

    log_level: str = env_str(
        "LOG_LEVEL",
        "INFO",
    )

    # Kafka
    kafka_bootstrap_servers: str = env_str(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    kafka_sensor_topic: str = env_str(
        "KAFKA_SENSOR_TOPIC",
        "tep-sensor-data",
    )

    kafka_prediction_topic: str = env_str(
        "KAFKA_PREDICTION_TOPIC",
        "tep-predictions",
    )

    kafka_drift_topic: str = env_str(
        "KAFKA_DRIFT_TOPIC",
        "tep-drift-events",
    )

    kafka_consumer_group: str = env_str(
        "KAFKA_CONSUMER_GROUP",
        "inference-service",
    )

    # TEP Replay
    tep_replay_speed: float = env_float(
        "TEP_REPLAY_SPEED",
        1.0,
    )

    tep_replay_interval_seconds: float = env_float(
        "TEP_REPLAY_INTERVAL_SECONDS",
        0.1,
    )

    # Model
    model_version: str = env_str(
        "MODEL_VERSION",
        "v1.0.0",
    )

    temporal_warmup_minutes: int = env_int(
        "TEMPORAL_WARMUP_MINUTES",
        60,
    )

    # API
    api_host: str = env_str(
        "API_HOST",
        "0.0.0.0",
    )

    api_port: int = env_int(
        "API_PORT",
        8000,
    )

    # Drift
    drift_check_enabled: bool = env_bool(
        "DRIFT_CHECK_ENABLED",
        True,
    )

    drift_check_interval_seconds: int = env_int(
        "DRIFT_CHECK_INTERVAL_SECONDS",
        60,
    )

    # Retraining
    retrain_enabled: bool = env_bool(
        "RETRAIN_ENABLED",
        False,
    )

    # Paths
    model_dir: Path = project_path(
        env_str(
            "MODEL_DIR",
            "models/production/v1.0.0",
        )
    )

    candidate_model_dir: Path = project_path(
        env_str(
            "CANDIDATE_MODEL_DIR",
            "models/candidates",
        )
    )

    production_model_dir: Path = project_path(
        env_str(
            "PRODUCTION_MODEL_DIR",
            "models/production",
        )
    )

    data_raw_dir: Path = project_path(
        env_str(
            "DATA_RAW_DIR",
            "data/raw",
        )
    )

    data_processed_dir: Path = project_path(
        env_str(
            "DATA_PROCESSED_DIR",
            "data/processed",
        )
    )

    data_metadata_dir: Path = project_path(
        env_str(
            "DATA_METADATA_DIR",
            "data/metadata",
        )
    )

    report_dir: Path = project_path(
        env_str(
            "REPORT_DIR",
            "reports",
        )
    )

    log_dir: Path = project_path(
        env_str(
            "LOG_DIR",
            "logs",
        )
    )


settings = Settings()
