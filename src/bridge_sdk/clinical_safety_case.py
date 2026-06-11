"""Clinical safety case per persona + MCP transport lockdown.

Workstream 10. Treats clinical agent behaviour as a release blocker governed by a
formal safety case. Depends on WS3-4 and WS9.

Design decision: EXTEND, don't duplicate. Verified prior art:
- GHARRA `core/clinical_safety.py` `ClinicalSafetyGuard` already does RUNTIME
  output safety: contraindication detection, scope enforcement, confidence
  scoring, with `SafetyCheckResult.severity` in {info, warning, critical}. WS10
  REUSES that severity vocabulary and does NOT re-implement runtime guarding.
- citizen-portal ships a DCB0129 clinical risk register (verified).

What is genuinely NEW (FR-CS-*, verified ABSENT):
- a per-PERSONA safety CASE (hazard log + unsafe-action analysis + override rules
  + contraindicated behaviours + rollout constraints) that gates PROMOTION: a
  persona without an approved safety case cannot go past shadow mode (FR-CS-001).
- break-glass paired with MANDATORY post-event review.
- MCP transport lockdown: per-client consent, NO token passthrough, SSRF
  controls, session isolation, scope minimisation (FR-CS-003) -- there was zero
  SSRF/token-passthrough/session-isolation code in signalbox-mcp.

Requirements: FR-CS-001..003, NFR-CS-001..002
(``BulletTrain/docs/CLINICAL_SAFETY_REQUIREMENTS.md``).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

__all__ = [
    "AutonomyStage",
    "ClinicalSafetyCase",
    "Hazard",
    "HazardSeverity",
    "McpTransportError",
    "McpTransportGuard",
    "SafetyCaseError",
]


class SafetyCaseError(Exception):
    """Raised on an invalid safety case or a blocked promotion."""


class McpTransportError(Exception):
    """Raised (fail-closed) when an MCP transport rule is violated."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(detail or reason)


class HazardSeverity(str, Enum):
    """Reuses GHARRA ClinicalSafetyGuard's severity vocabulary."""

    info = "info"
    warning = "warning"
    critical = "critical"


class AutonomyStage(str, Enum):
    """The governance ladder a persona climbs (shadow earned, not launched)."""

    shadow = "shadow"
    advisory = "advisory"
    bounded_auto = "bounded_auto"


# Ordering for promotion checks.
_STAGE_ORDER = {
    AutonomyStage.shadow: 0,
    AutonomyStage.advisory: 1,
    AutonomyStage.bounded_auto: 2,
}


@dataclass(frozen=True)
class Hazard:
    """One entry in a persona's hazard log (DCB0129-style)."""

    hazard_id: str
    description: str
    severity: HazardSeverity
    mitigation: str
    controlled: bool = False  # True once the mitigation is implemented + verified


@dataclass
class ClinicalSafetyCase:
    """A per-persona clinical safety case that gates promotion (FR-CS-001/002).

    A persona may run in ``shadow`` always. Promotion to ``advisory`` or
    ``bounded_auto`` requires an APPROVED case: every critical hazard controlled,
    contraindicated behaviours and override rules declared, and an approver named.
    """

    persona: str
    hazards: list[Hazard] = field(default_factory=list)
    contraindicated_behaviours: list[str] = field(default_factory=list)
    override_rules: list[str] = field(default_factory=list)
    rollout_constraints: list[str] = field(default_factory=list)
    approved_by: str | None = None  # named approver; None => not approved

    def uncontrolled_critical_hazards(self) -> list[Hazard]:
        return [
            h
            for h in self.hazards
            if h.severity is HazardSeverity.critical and not h.controlled
        ]

    def is_approved(self) -> bool:
        """A case is approved only with a named approver and no open criticals."""
        return bool(self.approved_by) and not self.uncontrolled_critical_hazards()

    def can_promote_to(self, stage: AutonomyStage) -> bool:
        """Whether the persona may run at ``stage`` (FR-CS-001-AC01)."""
        if stage is AutonomyStage.shadow:
            return True  # shadow never requires an approved case
        return self.is_approved()

    def assert_promotion(self, stage: AutonomyStage) -> None:
        """Raise ``SafetyCaseError`` if promotion past shadow lacks approval."""
        if self.can_promote_to(stage):
            return
        if not self.approved_by:
            raise SafetyCaseError(
                f"persona '{self.persona}' has no approved safety case; "
                f"cannot promote past shadow"
            )
        open_crit = [h.hazard_id for h in self.uncontrolled_critical_hazards()]
        raise SafetyCaseError(
            f"persona '{self.persona}' has uncontrolled critical hazards: {open_crit}"
        )


@dataclass
class BreakGlassReview:
    """A break-glass invocation requires mandatory post-event review (FR-CS-002)."""

    event_id: str
    reason: str
    reviewed: bool = False
    reviewer: str | None = None

    def complete_review(self, reviewer: str) -> None:
        if not reviewer:
            raise SafetyCaseError("post-event review requires a named reviewer")
        self.reviewed = True
        self.reviewer = reviewer

    def is_outstanding(self) -> bool:
        """True while the mandatory review is still pending."""
        return not self.reviewed


# Hosts/networks a patient-data MCP transport must never reach (SSRF guard).
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "localhost"}


class McpTransportGuard:
    """Lock down MCP transport per official MCP security guidance (FR-CS-003).

    - per-client consent: a call must present a consent token bound to the client
    - NO token passthrough: an upstream token must never be forwarded downstream
    - SSRF controls: outbound targets must be public, non-loopback, non-metadata
    - session isolation: a session id must match the calling client
    - scope minimisation: requested scopes must be a subset of granted scopes
    """

    def __init__(self, *, granted_scopes: frozenset[str]) -> None:
        self._granted = granted_scopes

    def check_consent(self, *, client_id: str, consent_client_id: str | None) -> None:
        if consent_client_id is None:
            raise McpTransportError("missing_consent", "no per-client consent token")
        if consent_client_id != client_id:
            raise McpTransportError(
                "consent_client_mismatch",
                f"consent bound to '{consent_client_id}', not '{client_id}'",
            )

    def reject_token_passthrough(self, *, downstream_headers: dict[str, str]) -> None:
        """Fail closed if an inbound bearer/authorization is being forwarded."""
        lowered = {k.lower() for k in downstream_headers}
        if "authorization" in lowered or "x-upstream-token" in lowered:
            raise McpTransportError(
                "token_passthrough",
                "upstream auth token must not be forwarded downstream",
            )

    def check_ssrf(self, url: str) -> None:
        """Reject loopback / link-local / private / metadata targets (SSRF)."""
        host = (urlparse(url).hostname or "").lower()
        if not host:
            raise McpTransportError("ssrf_blocked", "no host in target url")
        if host in _BLOCKED_HOSTS:
            raise McpTransportError("ssrf_blocked", f"blocked host '{host}'")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return  # a hostname (not a literal IP) -- DNS-pinning is a deploy concern
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
            raise McpTransportError("ssrf_blocked", f"non-public IP '{host}'")

    def check_session_isolation(
        self, *, session_client_id: str, calling_client_id: str
    ) -> None:
        if session_client_id != calling_client_id:
            raise McpTransportError(
                "session_isolation",
                f"session owned by '{session_client_id}', not '{calling_client_id}'",
            )

    def minimise_scopes(self, requested: frozenset[str]) -> None:
        """Fail closed if requested scopes exceed the granted set."""
        excess = requested - self._granted
        if excess:
            raise McpTransportError(
                "scope_escalation",
                f"requested scopes exceed grant: {sorted(excess)}",
            )
