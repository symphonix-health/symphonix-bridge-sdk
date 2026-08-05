"""Shared observability primitives for Symphonix Health services."""

from __future__ import annotations

import importlib.util
import warnings

# Emit a deprecation warning so callers know these deps leave core in the next
# major release.  Install `symphonix-bridge-sdk[observability]` to silence.
warnings.warn(
    "The OpenTelemetry/Sentry/Prometheus stack will be removed from "
    "symphonix-bridge-sdk's core dependencies in the next major release. "
    "Add `symphonix-bridge-sdk[observability]` to your requirements to keep "
    "this import working after the upgrade.",
    DeprecationWarning,
    stacklevel=2,
)

# Fail loudly (not with a cryptic AttributeError/ModuleNotFoundError deep in a
# sub-module) if the observability stack is not installed at all.
_REQUIRED = [
    "opentelemetry.sdk.trace",
    "opentelemetry.exporter.otlp",
    "sentry_sdk",
    "prometheus_client",
]


def _is_missing(module: str) -> bool:
    """Report whether *module* can be located, without leaking import errors.

    ``find_spec`` only returns ``None`` for a top-level module that is absent.
    For a dotted name it imports the parent package first, so an absent
    ``opentelemetry`` raises ``ModuleNotFoundError`` instead of returning
    ``None`` -- which is exactly the cryptic failure this guard exists to
    replace.  A stale ``sys.modules`` entry with ``__spec__`` set to ``None``
    raises ``ValueError`` for the same practical reason.  Both mean "missing".
    """
    try:
        return importlib.util.find_spec(module) is None
    except (ImportError, ValueError):
        return True


_missing = [m for m in _REQUIRED if _is_missing(m)]
if _missing:
    raise ImportError(
        "symphonix_bridge_sdk.observability requires the OpenTelemetry/Sentry/"
        "Prometheus stack, which is not installed.  "
        "Run: pip install 'symphonix-bridge-sdk[observability]'  "
        f"(missing: {', '.join(_missing)})"
    )

from .audit import AuditLogger
from .correlation import CorrelationIdMiddleware, get_correlation_id, set_correlation_id
from .health import HealthResponse, make_health_router
from .logging import configure_logging, get_logger
from .metrics import PrometheusMetrics
from .sentry import init_sentry
from .tracing import init_tracer, traced

__all__ = [
    "AuditLogger",
    "CorrelationIdMiddleware",
    "HealthResponse",
    "PrometheusMetrics",
    "configure_logging",
    "get_correlation_id",
    "get_logger",
    "init_sentry",
    "init_tracer",
    "make_health_router",
    "set_correlation_id",
    "traced",
]
