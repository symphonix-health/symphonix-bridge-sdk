"""Structured JSON logging setup."""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone

try:
    from pythonjsonlogger import jsonlogger
except ModuleNotFoundError:
    jsonlogger = None


class _FallbackJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "service": getattr(record, "service", ""),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ""),
            "span_id": getattr(record, "span_id", ""),
            "correlation_id": getattr(record, "correlation_id", ""),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


class _ObservabilityFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = getattr(record, "service", self.service_name)
        record.correlation_id = getattr(record, "correlation_id", "")
        try:
            from .correlation import get_correlation_id

            record.correlation_id = record.correlation_id or get_correlation_id()
        except Exception:
            pass

        record.trace_id = getattr(record, "trace_id", "")
        record.span_id = getattr(record, "span_id", "")
        try:
            from opentelemetry import trace

            span_context = trace.get_current_span().get_span_context()
            if span_context.is_valid:
                record.trace_id = record.trace_id or format(span_context.trace_id, "032x")
                record.span_id = record.span_id or format(span_context.span_id, "016x")
        except Exception:
            pass
        return True


def configure_logging(service_name: str, level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_ObservabilityFilter(service_name))
    if jsonlogger is None:
        formatter = _FallbackJsonFormatter()
    else:
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(service)s %(name)s %(levelname)s %(message)s %(trace_id)s %(span_id)s %(correlation_id)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger(__name__).info("Logging configured")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
