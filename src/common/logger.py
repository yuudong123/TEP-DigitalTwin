from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.common.config import settings


_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(
    name: str,
    log_file: str | None = None,
) -> logging.Logger:
    """
    프로젝트 공통 Logger.

    사용 예:
        logger = get_logger(
            "inference",
            "inference.log",
        )

        logger.info("Inference service started")
    """

    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)

    level = getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO,
    )

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # File
    if log_file is not None:
        log_dir: Path = settings.log_dir

        log_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = RotatingFileHandler(
            log_dir / log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )

        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    _LOGGERS[name] = logger

    return logger