from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from config import (
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    PERFORMANCE_LOG_FILE,
    SERVICE_NAME,
)

PERFORMANCE_LOGGER_NAME = f"{SERVICE_NAME}.performance"


def get_performance_logger() -> logging.Logger:
    """Return the dedicated backend performance logger."""
    logger = logging.getLogger(PERFORMANCE_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        PERFORMANCE_LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_performance_event(event: str, **fields: Any) -> None:
    """Append one structured performance event to ``performance.log``."""
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    get_performance_logger().info(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    )
