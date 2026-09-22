"""Logging configuration for the application."""
from __future__ import annotations

import logging
import sys
from typing import Any

JSON_FORMAT = "{asctime} | {levelname} | {name} | {message}"


class _RequestIdFilter(logging.Filter):
    """Attach a request-id to log records when present on the contextvar."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from contextvars import copy_context  # noqa: F401

            rid = _current_request_id.get("unknown")
            record.request_id = rid
        except Exception:
            record.request_id = "unknown"
        return True


from contextvars import ContextVar  # noqa: E402

_current_request_id: ContextVar[str] = ContextVar("request_id", default="unknown")

_loggers_configured: bool = False


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured JSON-ish logging for the whole application."""
    global _loggers_configured
    if _loggers_configured:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(JSON_FORMAT, style="{"))
    handler.setLevel(level)
    handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)

    # Silence overly chatty libraries
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _loggers_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    return logging.getLogger(name)


def set_request_id(rid: str) -> None:
    _current_request_id.set(rid)


def get_request_id() -> str:
    return _current_request_id.get("unknown")


class StructuredLogger:
    """Helper for structured logging with provider observability."""

    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def _emit(
        self,
        level: int,
        message: str,
        *,
        provider: str | None = None,
        endpoint: str | None = None,
        request_id: str | None = None,
        duration_ms: float | None = None,
        status: str | None = None,
        **extra: Any,
    ) -> None:
        fields: dict[str, Any] = {
            "provider": provider,
            "endpoint": endpoint,
            "request_id": request_id or get_request_id(),
            "duration_ms": duration_ms,
            "status": status,
        }
        fields.update(extra)
        self._log.log(level, message, extra=fields)

    def info(self, message: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, message, **kwargs)
