"""Structured logging with redaction for Foundry Router."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

import structlog

if TYPE_CHECKING:
    from structlog.types import EventDict, WrappedLogger

# Fields that should never appear in logs
SENSITIVE_FIELDS = {
    "authorization",
    "api_key",
    "api-key",
    "x-api-key",
    "apikey",
    "credential",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "prompt",
    "completion",
    "response",
    "output",
    "text",
    "content",
    "message",
    "choices",
    "embeddings",
    "data",
}

# Regex patterns for sensitive data in log messages
SENSITIVE_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-_]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*[A-Za-z0-9\-_]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{32,}", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", re.IGNORECASE),
]


def redact_dict(data: dict[str, Any], path: str = "") -> dict[str, Any]:
    """Recursively redact sensitive fields from a dictionary."""
    if not isinstance(data, dict):
        return data

    result: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        full_path = f"{path}.{key}" if path else key

        # Check if key is sensitive (exact match or normalized)
        if key_lower in SENSITIVE_FIELDS:
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact_value(value, full_path)
    return result


def _redact_value(value: Any, path: str) -> Any:
    if isinstance(value, Mapping):
        return redact_dict(dict(value), path)
    if isinstance(value, list):
        return [_redact_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, str):
        for pattern in SENSITIVE_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
    return value


def redact_processor(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Structlog processor to redact sensitive data from log events."""
    # Redact top-level sensitive fields
    return redact_dict(dict(event_dict))


def add_correlation_id(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Add correlation ID from context if available."""
    # structlog contextvars will handle this automatically if configured
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured JSON logging with redaction."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_correlation_id,
            redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return cast("structlog.BoundLogger", structlog.get_logger(name))
