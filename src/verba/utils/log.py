"""Logging helpers: consistent format, easy setup."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"verba.{name}")


def setup_logging(level: int = logging.INFO, stream: TextIO | None = None) -> None:
    """Configure the root logger once. Idempotent per stream handler."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
