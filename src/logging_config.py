from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_BACKUP_COUNT, LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, SERVICE_NAME


def get_logger() -> logging.Logger:
    logger = logging.getLogger(SERVICE_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
