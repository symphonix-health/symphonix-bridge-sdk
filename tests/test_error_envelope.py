"""Tests for the error envelope + preconditions (Workstream 5, FR-ER-*/NFR-ER-*)."""
from __future__ import annotations

import importlib.util

import pytest

from bridge_sdk.error_envelope import (
    AgentErrorEnvelope,
    ClinicianSafetySeverity,
    EnvelopeError,
    Precondition,
    PreconditionFailed,
    backoff_after,
    compensation_for,
)


# ---- FR-ER-001: standard envelope shape --------------------------------

def test_envelope_carries_all_standard_fields() -> None:
    env = AgentErrorEnvelope(
        code="downstream_unavailable",
        message="appointment-system 503",
        retryable=True,
        clinician_safety_severity=ClinicianSafetySeverity.low,
        retry_after_ms=200,
    )
    d = env.to_dict()
    assert d["code"] == "downstream_unavailable"
    assert d["retryable"] is True
    assert d["retry_after_ms"] == 200
    assert d["clinician_safety_severity"] == "low"


def test_envelope_requires_stable_code() -> None:
    with pytest.raises(EnvelopeError):
        AgentErrorEnvelope(
            code="",
            message="x",
            retryable=False,
            clinician_safety_severity=ClinicianSafetySeverity.none,
        )


def test_retryable_must_carry_retry_after_ms() -> None:
    with pytest.raises(EnvelopeError):
        AgentErrorEnvelope(
            code="c", message="m", retryable=True,
            clinician_safety_severity=ClinicianSafetySeverity.low,
        )  # missing retry_after_ms


def test_non_retryable_must_not_carry_retry_after_ms() -> None:
    with pytest.raises(EnvelopeError):
        AgentErrorEnvelope(
            code="c", message="m", retryable=False,
            clinician_safety_severity=ClinicianSafetySeverity.low,
            retry_after_ms=100,
        )


def test_retryable_failure_factory_sets_backoff() -> None:
    env = AgentErrorEnvelope.retryable_failure("e", "m", attempt=2)
    assert env.retryable is True
    assert env.retry_after_ms == 400  # 100 * 2^2


# ---- FR-ER-003: compensation pairs -------------------------------------

@pytest.mark.parametrize(
    "forward,expected",
    [
        ("book", "cancel"),
        ("create", "update"),
        ("reserve", "release"),
        ("claim", "void"),
        ("order", "retract"),
    ],
)
def test_compensation_pairs(forward, expected) -> None:
    assert compensation_for(forward).compensation == expected


def test_unknown_forward_action_has_no_silent_compensation() -> None:
    with pytest.raises(EnvelopeError):
        compensation_for("frobnicate")


def test_terminal_failure_attaches_compensation() -> None:
    env = AgentErrorEnvelope.terminal_failure(
        "booking_rejected", "slot gone", forward_action="book",
    )
    assert env.retryable is False
    assert env.compensating_action == "cancel"
    assert env.retry_after_ms is None


def test_terminal_failure_without_forward_action_has_no_compensation() -> None:
    env = AgentErrorEnvelope.terminal_failure("bad_request", "schema invalid")
    assert env.compensating_action is None


# ---- backoff matches RetryPolicy semantics -----------------------------

def test_backoff_is_exponential_and_capped() -> None:
    assert backoff_after(0) == 100
    assert backoff_after(1) == 200
    assert backoff_after(2) == 400
    assert backoff_after(3) == 800
    assert backoff_after(50) == 30000  # capped at max_ms


def test_backoff_rejects_negative_attempt() -> None:
    with pytest.raises(EnvelopeError):
        backoff_after(-1)


@pytest.mark.skipif(
    importlib.util.find_spec("bullettrain") is None,
    reason="BulletTrain not importable in this interpreter",
)
def test_backoff_defaults_match_real_retrypolicy() -> None:
    # The envelope's backoff floor must match the REAL RetryPolicy defaults so
    # advertised retry_after_ms agrees with what execute_with_retry waits.
    from bullettrain.resilience import RetryPolicy  # type: ignore

    rp = RetryPolicy()
    assert backoff_after(0, base_ms=rp.backoff_base_ms, max_ms=rp.backoff_max_ms,
                         multiplier=rp.backoff_multiplier) == rp.backoff_base_ms
    # Cap matches.
    assert backoff_after(99, base_ms=rp.backoff_base_ms, max_ms=rp.backoff_max_ms,
                         multiplier=rp.backoff_multiplier) == rp.backoff_max_ms


# ---- FR-ER-002: ETag / If-Match optimistic concurrency -----------------

def test_precondition_passes_on_matching_etag() -> None:
    pre = Precondition(current_etag="v3")
    assert pre.passes("v3") is True
    pre.check("v3")  # does not raise


def test_precondition_fails_on_stale_etag() -> None:
    # Stale If-Match => 412 conflict, no mutation (FR-ER-002-AC01).
    pre = Precondition(current_etag="v3")
    assert pre.passes("v2") is False
    with pytest.raises(PreconditionFailed):
        pre.check("v2")


def test_precondition_requires_if_match_for_mutable_resource() -> None:
    pre = Precondition(current_etag="v3")
    with pytest.raises(PreconditionFailed):
        pre.check(None)
