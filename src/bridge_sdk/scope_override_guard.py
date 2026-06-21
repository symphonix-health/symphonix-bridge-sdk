"""Safety-scope override guard with dual control, audit, and FP/FN metrics.

The guard is intentionally SDK-local and dependency-light. It does not decide
clinical policy by itself; callers configure which PersonaScope expansions are
eligible for override and provide a file-backed approval store for named
secondary approvers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter

from bridge_sdk.persona_delegation import DelegationError, PersonaScope, unify_scope

__all__ = [
    "FileDualControlApprovalStore",
    "FileScopeOverrideAuditSink",
    "ScopeOverrideDecision",
    "ScopeOverrideError",
    "ScopeOverrideGuard",
    "ScopeOverrideMetrics",
    "ScopeOverrideRequest",
    "make_scope_override_metrics_router",
    "token_sha256",
]


class ScopeOverrideError(Exception):
    """Raised when override guard configuration is invalid."""


def token_sha256(token: str) -> str:
    """Return the canonical digest stored for a secondary approval token."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _event_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalise_scope_set(raw_scopes: Iterable[str | PersonaScope]) -> frozenset[PersonaScope]:
    normalised: set[PersonaScope] = set()
    for raw in raw_scopes:
        if isinstance(raw, PersonaScope):
            normalised.add(raw)
            continue
        if not isinstance(raw, str):
            raise DelegationError(f"invalid scope value {raw!r}")
        normalised.add(unify_scope(raw))
    return frozenset(normalised)


def _scope_values(scopes: Iterable[PersonaScope]) -> list[str]:
    return sorted(scope.value for scope in scopes)


@dataclass(frozen=True)
class ScopeOverrideRequest:
    """One proposed scope expansion for an agent or bridge workflow."""

    persona: str
    primary_actor: str
    requested_scopes: tuple[str | PersonaScope, ...]
    granted_scopes: tuple[str | PersonaScope, ...]
    rationale: str
    secondary_actor: str | None
    secondary_approval_token: str | None
    safety_case_ref: str | None
    correlation_id: str
    action_path: str = ""
    clinical_context_ref: str | None = None
    trajectory_ref: str | None = None


@dataclass
class ScopeOverrideDecision:
    """Machine-readable guard result, suitable for audit and CAID replay."""

    permitted: bool
    reason: str
    correlation_id: str
    persona: str
    requested_scopes: list[str]
    granted_scopes: list[str]
    excess_scopes: list[str]
    latency_ms: float
    audit_hash: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "permitted": self.permitted,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "persona": self.persona,
            "requested_scopes": list(self.requested_scopes),
            "granted_scopes": list(self.granted_scopes),
            "excess_scopes": list(self.excess_scopes),
            "latency_ms": self.latency_ms,
            "audit_hash": self.audit_hash,
            "detail": self.detail,
        }


class FileDualControlApprovalStore:
    """File-backed secondary approval validation.

    Expected JSON shape:

    {
      "approvers": [
        {
          "actor_id": "clinical-safety-officer-1",
          "token_sha256": "...",
          "active": true,
          "allowed_personas": ["triage-intake-agent"],
          "allowed_scopes": ["api:write"]
        }
      ]
    }
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise ScopeOverrideError(f"approval store not found: {self.path}")

    def verify(
        self,
        *,
        approver_id: str,
        token: str,
        persona: str,
        excess_scopes: Iterable[PersonaScope],
    ) -> bool:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        excess = set(excess_scopes)
        for row in data.get("approvers", []):
            if row.get("actor_id") != approver_id:
                continue
            if row.get("active") is False:
                return False
            expected_digest = row.get("token_sha256", "")
            if not hmac.compare_digest(expected_digest, token_sha256(token)):
                return False

            allowed_personas = set(row.get("allowed_personas") or [])
            if allowed_personas and persona not in allowed_personas:
                return False

            try:
                allowed_scopes = _normalise_scope_set(row.get("allowed_scopes") or [])
            except DelegationError:
                return False
            return excess.issubset(allowed_scopes)
        return False


class FileScopeOverrideAuditSink:
    """Append-only JSONL audit sink with a hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return ""
        last_hash = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                last_hash = json.loads(line).get("event_hash", last_hash)
            except json.JSONDecodeError:
                return ""
        return last_hash

    def record(
        self, request: ScopeOverrideRequest, decision: ScopeOverrideDecision
    ) -> str:
        with self._lock:
            event = {
                "schema_version": "scope-override-guard.v1",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "previous_hash": self._last_hash,
                "decision": {
                    key: value
                    for key, value in decision.to_dict().items()
                    if key != "audit_hash"
                },
                "request": {
                    "persona": request.persona,
                    "primary_actor": request.primary_actor,
                    "secondary_actor": request.secondary_actor,
                    "safety_case_ref": request.safety_case_ref,
                    "action_path": request.action_path,
                    "clinical_context_ref": request.clinical_context_ref,
                    "trajectory_ref": request.trajectory_ref,
                    "rationale": request.rationale,
                    "rationale_sha256": token_sha256(request.rationale),
                    "secondary_approval_token_sha256": token_sha256(
                        request.secondary_approval_token or ""
                    ),
                },
            }
            event["event_hash"] = _event_hash(event)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")))
                fh.write("\n")
            self._last_hash = event["event_hash"]
            return event["event_hash"]

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def verify_chain(self) -> bool:
        previous_hash = ""
        for record in self.records():
            event_hash = record.get("event_hash", "")
            body = dict(record)
            body.pop("event_hash", None)
            if record.get("previous_hash") != previous_hash:
                return False
            if not hmac.compare_digest(event_hash, _event_hash(body)):
                return False
            previous_hash = event_hash
        return True


@dataclass
class ScopeOverrideMetrics:
    """Counters and validation labels for guard self-assessment."""

    permitted_total: int = 0
    rejected_total: int = 0
    labelled_total: int = 0
    false_positive_total: int = 0
    false_negative_total: int = 0
    reason_counts: dict[str, int] = field(default_factory=dict)
    latency_ms: list[float] = field(default_factory=list)

    def record_decision(
        self, decision: ScopeOverrideDecision, *, expected_permitted: bool | None = None
    ) -> None:
        if decision.permitted:
            self.permitted_total += 1
        else:
            self.rejected_total += 1
        self.reason_counts[decision.reason] = self.reason_counts.get(decision.reason, 0) + 1
        self.latency_ms.append(decision.latency_ms)

        if expected_permitted is not None:
            self.labelled_total += 1
        if expected_permitted is True and not decision.permitted:
            self.false_positive_total += 1
        if expected_permitted is False and decision.permitted:
            self.false_negative_total += 1

    def summary(self) -> dict[str, Any]:
        total = self.permitted_total + self.rejected_total
        latencies = sorted(self.latency_ms)
        if len(latencies) >= 2:
            p99 = statistics.quantiles(latencies, n=100, method="inclusive")[98]
        elif latencies:
            p99 = latencies[0]
        else:
            p99 = 0.0
        return {
            "total": total,
            "permitted_total": self.permitted_total,
            "rejected_total": self.rejected_total,
            "labelled_total": self.labelled_total,
            "false_positive_total": self.false_positive_total,
            "false_negative_total": self.false_negative_total,
            "false_positive_rate": (
                self.false_positive_total / self.labelled_total
                if self.labelled_total
                else 0.0
            ),
            "false_negative_rate": (
                self.false_negative_total / self.labelled_total
                if self.labelled_total
                else 0.0
            ),
            "labelled_error_total": self.false_positive_total + self.false_negative_total,
            "latency_p99_ms": p99,
            "reason_counts": dict(sorted(self.reason_counts.items())),
        }


class ScopeOverrideGuard:
    """Fail-closed guard for safety-scope expansion."""

    def __init__(
        self,
        *,
        approval_store: FileDualControlApprovalStore,
        audit_sink: FileScopeOverrideAuditSink,
        permitted_override_scopes: Iterable[str | PersonaScope],
        metrics: ScopeOverrideMetrics | None = None,
        min_rationale_chars: int = 20,
    ) -> None:
        self.approval_store = approval_store
        self.audit_sink = audit_sink
        self.permitted_override_scopes = _normalise_scope_set(permitted_override_scopes)
        self.metrics = metrics or ScopeOverrideMetrics()
        self.min_rationale_chars = min_rationale_chars

    def evaluate(
        self,
        request: ScopeOverrideRequest,
        *,
        expected_permitted: bool | None = None,
    ) -> ScopeOverrideDecision:
        start = time.perf_counter()
        try:
            requested = _normalise_scope_set(request.requested_scopes)
            granted = _normalise_scope_set(request.granted_scopes)
        except DelegationError as exc:
            return self._finish(
                request,
                permitted=False,
                reason="unknown_scope",
                requested=frozenset(),
                granted=frozenset(),
                excess=frozenset(),
                start=start,
                expected_permitted=expected_permitted,
                detail=str(exc),
            )

        excess = requested - granted
        if not excess:
            return self._finish(
                request,
                permitted=True,
                reason="no_override_required",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        if not excess.issubset(self.permitted_override_scopes):
            return self._finish(
                request,
                permitted=False,
                reason="scope_not_overrideable",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        rationale = request.rationale.strip()
        if len(rationale) < self.min_rationale_chars:
            return self._finish(
                request,
                permitted=False,
                reason="missing_rationale",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        if not request.safety_case_ref:
            return self._finish(
                request,
                permitted=False,
                reason="missing_safety_case",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        if not request.secondary_actor or not request.secondary_approval_token:
            return self._finish(
                request,
                permitted=False,
                reason="missing_secondary_approval",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        if request.primary_actor == request.secondary_actor:
            return self._finish(
                request,
                permitted=False,
                reason="dual_control_not_distinct",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        approved = self.approval_store.verify(
            approver_id=request.secondary_actor,
            token=request.secondary_approval_token,
            persona=request.persona,
            excess_scopes=excess,
        )
        if not approved:
            return self._finish(
                request,
                permitted=False,
                reason="secondary_approval_invalid",
                requested=requested,
                granted=granted,
                excess=excess,
                start=start,
                expected_permitted=expected_permitted,
            )

        return self._finish(
            request,
            permitted=True,
            reason="dual_control_confirmed",
            requested=requested,
            granted=granted,
            excess=excess,
            start=start,
            expected_permitted=expected_permitted,
        )

    def _finish(
        self,
        request: ScopeOverrideRequest,
        *,
        permitted: bool,
        reason: str,
        requested: Iterable[PersonaScope],
        granted: Iterable[PersonaScope],
        excess: Iterable[PersonaScope],
        start: float,
        expected_permitted: bool | None,
        detail: str = "",
    ) -> ScopeOverrideDecision:
        latency_ms = (time.perf_counter() - start) * 1000
        decision = ScopeOverrideDecision(
            permitted=permitted,
            reason=reason,
            correlation_id=request.correlation_id,
            persona=request.persona,
            requested_scopes=_scope_values(requested),
            granted_scopes=_scope_values(granted),
            excess_scopes=_scope_values(excess),
            latency_ms=latency_ms,
            detail=detail,
        )
        decision.audit_hash = self.audit_sink.record(request, decision)
        self.metrics.record_decision(decision, expected_permitted=expected_permitted)
        return decision


def make_scope_override_metrics_router(metrics: ScopeOverrideMetrics) -> APIRouter:
    """Expose guard counters as JSON for service metrics endpoints."""

    router = APIRouter()

    @router.get("/metrics/scope-override-guard")
    async def scope_override_guard_metrics() -> dict[str, Any]:
        return metrics.summary()

    return router
