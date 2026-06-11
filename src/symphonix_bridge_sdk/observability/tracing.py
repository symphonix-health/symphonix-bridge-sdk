"""OpenTelemetry tracing setup and helpers."""

from __future__ import annotations

import functools
import inspect
import os
import socket
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

F = TypeVar("F", bound=Callable[..., Any])
_tracer_initialized = False


def _instrument_once() -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
    except Exception:
        pass
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:
        pass
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
    except Exception:
        pass


def _endpoint_is_usable(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    host = parsed.hostname
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        socket.getaddrinfo(host, parsed.port or 4318)
    except OSError:
        return False
    return True


def init_tracer(service_name: str, otlp_endpoint: str | None = None) -> trace.Tracer:
    """Initialize OpenTelemetry tracing and return a service tracer."""

    global _tracer_initialized
    if not _tracer_initialized:
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint and _endpoint_is_usable(endpoint):
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
                )
            except Exception:
                pass
        trace.set_tracer_provider(provider)
        _instrument_once()
        _tracer_initialized = True
    return trace.get_tracer(service_name)


def traced(name: str | None = None):
    """Decorate a sync or async function with an OpenTelemetry span."""

    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__name__}"
        tracer = trace.get_tracer(func.__module__)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with tracer.start_as_current_span(span_name):
                    return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
