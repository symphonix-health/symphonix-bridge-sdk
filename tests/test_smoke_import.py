from pathlib import Path
import sys


# Ensure src-layout package is importable in local repo test runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_bridge_sdk_importable() -> None:
    import bridge_sdk  # noqa: F401


def test_observability_importable() -> None:
    from symphonix_bridge_sdk.observability import (
        AuditLogger,
        CorrelationIdMiddleware,
        PrometheusMetrics,
        configure_logging,
        get_correlation_id,
        get_logger,
        init_sentry,
        init_tracer,
        make_health_router,
        traced,
    )

    assert AuditLogger
    assert CorrelationIdMiddleware
    assert PrometheusMetrics
    assert configure_logging
    assert get_correlation_id
    assert get_logger
    assert init_sentry
    assert init_tracer
    assert make_health_router
    assert traced


def test_observability_bridge_namespace_importable() -> None:
    from bridge_sdk.observability.metrics import PrometheusMetrics

    assert PrometheusMetrics("test-service").metrics_app()
