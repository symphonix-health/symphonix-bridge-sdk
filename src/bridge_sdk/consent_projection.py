"""Consent projection: a compact, workflow-specific policy artefact.

Workstream 9. Binds every patient-data action to active consent and jurisdiction
rules. Depends on WS3-4; gates patient-facing rollout.

Design decision: EXTEND, don't duplicate. Verified prior art:
- `bullettrain/security/consent.py` already has the CONSENT STORE: `Consent`,
  `ConsentStatus` (active/inactive), `ConsentScope`, `ConsentProvision`,
  `ConsentDirective.matches`, `ConsentRegistry` with versioned withdraw +
  `Consent.is_active()`. WS9 does NOT re-implement consent storage.
- GHARRA has a PHI scanner / zero-PHI registry posture.
- WS3 `PersonaTokenClaims.consent_artefact` and WS4's `consent_artefact`
  provenance field already RESERVE a slot for a consent reference.

What is genuinely NEW (FR-PC-*): a compact PROJECTION of an active FHIR Consent
into a workflow-specific policy artefact that (a) travels on the persona token +
every task, (b) is references-only (no clinical content in GHARRA / task
metadata), (c) fails closed on purpose-of-use mismatch, non-approved
jurisdiction, withheld data, or mid-task revocation.

The projection is computed BEFORE SignalBox executes, then attached. It carries
only: the consent reference, the permitted purposes, the permitted FHIR resource
types, the patient reference, an approved-jurisdiction list, and an issued
version stamp (so a later revocation invalidates it).

Requirements: FR-PC-001..003, NFR-PC-001..002
(``BulletTrain/docs/CONSENT_PROJECTION_REQUIREMENTS.md``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "ConsentDenied",
    "ConsentProjection",
    "ConsentProjectionError",
    "project_consent",
]


class ConsentProjectionError(Exception):
    """Raised when a projection is built from an inconsistent/empty consent."""


class ConsentDenied(Exception):
    """Raised (fail-closed) when an action is not permitted by the projection.

    Carries a machine-readable ``reason`` for the privacy metrics (NFR-PC-002):
    one of ``purpose_mismatch`` / ``resource_not_permitted`` /
    ``jurisdiction_not_approved`` / ``consent_revoked`` / ``no_active_consent``.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(detail or reason)


@dataclass(frozen=True)
class ConsentProjection:
    """Compact, workflow-specific projection of an active consent (FR-PC-001).

    References-only: ``consent_reference`` and ``patient_reference`` are FHIR
    references, never clinical content (FR-PC-002).
    """

    consent_reference: str            # e.g. "Consent/abc" -- a reference, not content
    patient_reference: str            # e.g. "Patient/123"
    permitted_purposes: frozenset[str]
    permitted_resource_types: frozenset[str]
    approved_jurisdictions: frozenset[str]
    consent_version: int              # bumps on withdraw; stale version => revoked
    active: bool = True

    def to_token_claim(self) -> dict[str, Any]:
        """Compact claim attached to the persona token + every task (FR-PC-001).

        Carries references + permissions only -- no clinical payload.
        """
        return {
            "consent_reference": self.consent_reference,
            "patient_reference": self.patient_reference,
            "purposes": sorted(self.permitted_purposes),
            "resource_types": sorted(self.permitted_resource_types),
            "jurisdictions": sorted(self.approved_jurisdictions),
            "consent_version": self.consent_version,
        }

    def authorise(
        self,
        *,
        purpose_of_use: str,
        resource_type: str,
        target_jurisdiction: str,
        current_consent_version: int,
    ) -> None:
        """Fail-closed gate for one patient-data action (FR-PC-001/003).

        Raises ``ConsentDenied`` (with a reason) on: an inactive projection,
        a purpose mismatch, a resource type not covered, a non-approved target
        jurisdiction, or a stale consent version (mid-task revocation).
        """
        if not self.active:
            raise ConsentDenied("consent_revoked", "projection marked inactive")
        # Mid-task revocation: the live consent version moved past the projection.
        if current_consent_version != self.consent_version:
            raise ConsentDenied(
                "consent_revoked",
                f"consent version {current_consent_version} != projected "
                f"{self.consent_version}",
            )
        if purpose_of_use not in self.permitted_purposes:
            raise ConsentDenied(
                "purpose_mismatch",
                f"purpose '{purpose_of_use}' not in {sorted(self.permitted_purposes)}",
            )
        if resource_type not in self.permitted_resource_types:
            raise ConsentDenied(
                "resource_not_permitted",
                f"resource '{resource_type}' not permitted",
            )
        if target_jurisdiction not in self.approved_jurisdictions:
            # FR-PC-003: patient-data tasks route only to approved jurisdictions.
            raise ConsentDenied(
                "jurisdiction_not_approved",
                f"jurisdiction '{target_jurisdiction}' not approved",
            )

    def permits(self, **kw: Any) -> bool:
        """Non-raising form of :meth:`authorise`."""
        try:
            self.authorise(**kw)
            return True
        except ConsentDenied:
            return False


def project_consent(
    *,
    consent_reference: str,
    patient_reference: str,
    is_active: bool,
    permitted_purposes: list[str],
    permitted_resource_types: list[str],
    approved_jurisdictions: list[str],
    consent_version: int,
) -> ConsentProjection:
    """Project an active consent into a compact workflow artefact (FR-PC-001).

    Inputs come from the real ``bullettrain.security.consent`` store at the
    BulletTrain boundary (``Consent.is_active()``, scopes, purposes). Raises
    ``ConsentDenied('no_active_consent')`` if the source consent is not active --
    a withdrawn/absent consent can never yield a usable projection (fail-closed).
    """
    if not is_active:
        raise ConsentDenied("no_active_consent", consent_reference)
    if not permitted_purposes:
        raise ConsentProjectionError("a projection must permit >=1 purpose")
    if consent_version < 0:
        raise ConsentProjectionError("consent_version must be >= 0")
    return ConsentProjection(
        consent_reference=consent_reference,
        patient_reference=patient_reference,
        permitted_purposes=frozenset(permitted_purposes),
        permitted_resource_types=frozenset(permitted_resource_types),
        approved_jurisdictions=frozenset(approved_jurisdictions),
        consent_version=consent_version,
        active=True,
    )


# Convenience: scan a projected token-claim for PHI leakage (FR-PC-002 guard).
# The projection must carry references only; this asserts no obvious clinical
# content keys slipped in.
_CLINICAL_CONTENT_KEYS: frozenset[str] = frozenset(
    {"diagnosis", "medication", "observation", "note", "result", "condition"}
)


def claim_is_references_only(claim: dict[str, Any]) -> bool:
    """True iff a token claim carries no obvious clinical-content keys (FR-PC-002)."""
    flat = _flatten_keys(claim)
    return not (flat & _CLINICAL_CONTENT_KEYS)


def _flatten_keys(obj: Any, acc: set[str] | None = None) -> set[str]:
    acc = acc if acc is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(str(k).lower())
            _flatten_keys(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_keys(v, acc)
    return acc
