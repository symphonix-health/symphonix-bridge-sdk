"""Prometheus metrics helpers."""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
)

_registry = CollectorRegistry(auto_describe=True)
_collectors: dict[tuple[str, str], object] = {}


def _get_collector(kind: str, name: str, factory):
    key = (kind, name)
    if key not in _collectors:
        _collectors[key] = factory()
    return _collectors[key]


def counter(name: str, description: str, labels: list[str] | tuple[str, ...] = ()):
    return _get_collector(
        "counter",
        name,
        lambda: Counter(name, description, labels, registry=_registry),
    )


def histogram(
    name: str,
    description: str,
    labels: list[str] | tuple[str, ...] = (),
    buckets=None,
):
    kwargs = {"registry": _registry}
    if buckets is not None:
        kwargs["buckets"] = buckets
    return _get_collector(
        "histogram",
        name,
        lambda: Histogram(name, description, labels, **kwargs),
    )


def gauge(name: str, description: str, labels: list[str] | tuple[str, ...] = ()):
    return _get_collector(
        "gauge",
        name,
        lambda: Gauge(name, description, labels, registry=_registry),
    )


class PrometheusMetrics:
    def __init__(self, service_name: str):
        self.service = service_name
        self.request_count = counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        self.request_latency = histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "endpoint"],
        )

    def metrics_app(self):
        """Mount at /metrics via `app.mount('/metrics', metrics.metrics_app())`."""

        return make_asgi_app(registry=_registry)
