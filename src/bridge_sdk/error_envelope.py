"""Standard agent error envelope + optimistic-concurrency preconditions.

Workstream 5. Makes idempotency, optimistic concurrency, and compensating
actions standard behaviour for all domain actions. Depends on WS2.

Design decision: EXTEND, don't duplicate. BulletTrain already ships a production
resilience stack -- WS5 adds ONLY the two pieces verified ABSENT:

EXISTS (reused, NOT reimplemented):
- `bullettrain/resilience/__init__.py:79` ``RetryPolicy`` (max_retries,
  backoff_base_ms, backoff_max_ms, backoff_multiplier, jitter) + ``execute_with_retry``
  -> the envelope's ``retry_after_ms`` is computed by the SAME backoff formula
  (``backoff_after`` here mirrors it) so envelope and executor never disagree.
- `bullettrain/resilience/saga.py:27` ``CompensationAction`` + ``SagaCompensator``
  (LIFO compensation) -> the envelope NAMES a compensating action; the existing
  SagaCompensator executes it. This module does not re-implement saga orchestration.
- idempotency stores (`mcp_care/idempotency.py`, `make_idempotency_key`).

ABSENT (the genuine WS5 build, verified by grep):
- a canonical error envelope (stable code, retryable, retry_after_ms,
  compensating action, clinician-safety severity) -- FR-ER-001/003.
- ETag / If-Match optimistic concurrency (zero hits in bullettrain/) -- FR-ER-002.

Requirements: FR-ER-001..003, NFR-ER-001..002
(``BulletTrain/docs/ERROR_ENVELOPE_REQUIREMENTS.md``).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "AgentErrorEnvelope",
    "CompensationPair",
    "ClinicianSafetySeverity",
    "EnvelopeError",
    "Precondition",
    "PreconditionFailed",
    "backoff_after",
    "compensation_for",
]


class EnvelopeError(Exception):
    """Raised when an error envelope is constructed inconsistently."""


class PreconditionFailed(Exception):
    """Raised when an If-Match precondition fails (maps to HTTP 412)."""


class ClinicianSafetySeverity(str, Enum):
    """Clinician-facing severity carried on every domain error (FR-ER-001)."""

    none = "none"            # operational only, no clinical bearing
    low = "low"             # minor; clinician informed, no action needed
    moderate = "moderate"   # clinician review advised
    high = "high"           # clinician action required before proceeding
    critical = "critical"   # patient-safety relevant; escalate immediately


# Forward action -> registered compensation (FR-ER-003). Mirrors the plan's
# encoded pairs. The actual undo is executed by the existing
# bullettrain.resilience.saga.SagaCompensator; this is the vocabulary.
_COMPENSATIONS: dict[str, str] = {
    "book": "cancel",
    "create": "update",          # forward create compensated by a corrective update
    "reserve": "release",
    "claim": "void",
    "order": "retract",
}


@dataclass(frozen=True)
class CompensationPair:
    """A forward action and its registered compensating action."""

    forward: str
    compensation: str


def compensation_for(forward_action: str) -> CompensationPair:
    """Return the registered compensation for a forward action (FR-ER-003).

    Raises ``EnvelopeError`` for an action with no registered compensation, so a
    mutating action can never silently lack an undo path.
    """
    if forward_action not in _COMPENSATIONS:
        raise EnvelopeError(
            f"no registered compensation for forward action '{forward_action}'; "
            f"known: {sorted(_COMPENSATIONS)}"
        )
    return CompensationPair(forward_action, _COMPENSATIONS[forward_action])


def backoff_after(
    attempt: int,
    *,
    base_ms: int = 100,
    max_ms: int = 30000,
    multiplier: float = 2.0,
) -> int:
    """Exponential backoff delay for ``attempt`` (0-based), capped at ``max_ms``.

    Defaults match ``bullettrain.resilience.RetryPolicy`` so the envelope's
    ``retry_after_ms`` agrees with what ``execute_with_retry`` actually waits.
    Jitter is intentionally NOT applied here: the envelope advertises a stable
    floor; the executor adds jitter on top.
    """
    if attempt < 0:
        raise EnvelopeError("attempt must be >= 0")
    delay = base_ms * (multiplier**attempt)
    return int(min(delay, max_ms))


@dataclass(frozen=True)
class AgentErrorEnvelope:
    """The standard error shape every domain action returns (FR-ER-001).

    Fields: a stable ``code`` (machine-routable, never localised), a ``retryable``
    flag, ``retry_after_ms`` (when retryable), an optional ``compensating_action``,
    and a ``clinician_safety_severity``.
    """

    code: str
    message: str
    retryable: bool
    clinician_safety_severity: ClinicianSafetySeverity
    retry_after_ms: int | None = None
    compensating_action: str | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise EnvelopeError("error envelope requires a stable code")
        if self.retryable and self.retry_after_ms is None:
            raise EnvelopeError("retryable error must carry retry_after_ms")
        if not self.retryable and self.retry_after_ms is not None:
            raise EnvelopeError("non-retryable error must not carry retry_after_ms")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "clinician_safety_severity": self.clinician_safety_severity.value,
        }
        if self.retry_after_ms is not None:
            out["retry_after_ms"] = self.retry_after_ms
        if self.compensating_action is not None:
            out["compensating_action"] = self.compensating_action
        if self.details is not None:
            out["details"] = self.details
        return out

    @classmethod
    def retryable_failure(
        cls,
        code: str,
        message: str,
        *,
        attempt: int = 0,
        severity: ClinicianSafetySeverity = ClinicianSafetySeverity.low,
        details: dict[str, Any] | None = None,
    ) -> AgentErrorEnvelope:
        """Build a retryable envelope with backoff matching ``RetryPolicy``."""
        return cls(
            code=code,
            message=message,
            retryable=True,
            clinician_safety_severity=severity,
            retry_after_ms=backoff_after(attempt),
            details=details,
        )

    @classmethod
    def terminal_failure(
        cls,
        code: str,
        message: str,
        *,
        forward_action: str | None = None,
        severity: ClinicianSafetySeverity = ClinicianSafetySeverity.moderate,
        details: dict[str, Any] | None = None,
    ) -> AgentErrorEnvelope:
        """Build a non-retryable envelope, naming a compensation if applicable.

        When ``forward_action`` is given, its registered compensation is attached
        so the caller knows how to undo a partially-applied mutation (FR-ER-003).
        """
        compensation = (
            compensation_for(forward_action).compensation
            if forward_action is not None
            else None
        )
        return cls(
            code=code,
            message=message,
            retryable=False,
            clinician_safety_severity=severity,
            compensating_action=compensation,
            details=details,
        )


@dataclass(frozen=True)
class Precondition:
    """ETag / If-Match optimistic-concurrency check (FR-ER-002).

    A mutable resource carries an ETag (its current version). A write supplies
    ``If-Match``; if it does not equal the current ETag, the write conflicts
    (HTTP 412) and is rejected without mutation.
    """

    current_etag: str

    def check(self, if_match: str | None) -> None:
        """Raise ``PreconditionFailed`` if ``if_match`` is missing or stale."""
        if if_match is None:
            raise PreconditionFailed("If-Match header required for mutable resource")
        if if_match != self.current_etag:
            raise PreconditionFailed(
                f"If-Match '{if_match}' does not match current ETag "
                f"'{self.current_etag}' (concurrent modification)"
            )

    def passes(self, if_match: str | None) -> bool:
        """Non-raising form: True iff the precondition is satisfied."""
        try:
            self.check(if_match)
            return True
        except PreconditionFailed:
            return False
