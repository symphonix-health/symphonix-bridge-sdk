"""Evidence resolution -- populate a PerceivedSignal from canonical signed evidence.

Rank B of the agent-tooltip programme. The DOM carries only a NON-PHI pointer
(``evidence_ref``); the canonical evidence (provenance + attestation + coded
semantics + confidence) lives behind a governed boundary. An
:class:`EvidenceResolver` turns an ``evidence_ref`` into :class:`ResolvedEvidence`,
from which a :class:`PerceivedSignal` is enriched with REAL ``attested`` /
``confidence`` hints -- which is what lets the governance core reach
``auto_on_loop`` instead of always escalating (fail-closed) on unknown hints.

This module is the INTERFACE + a fail-closed default + a reference resolver. A
PRODUCTION resolver fetches signed FHIR evidence (Provenance/AuditEvent) via the
governed API, verifies the signature + registry anchor, redacts per persona, and
emits an AuditEvent on access -- that live service is the remaining rank-B work.
The seam here is what makes ``auto_on_loop`` reachable and testable today, and it
fails closed: unresolved or tampered evidence is NOT trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from bridge_sdk.signal_governance import PerceivedSignal

__all__ = [
    "ResolvedEvidence",
    "EvidenceResolver",
    "NullEvidenceResolver",
    "StaticEvidenceResolver",
    "signal_from_evidence",
]


@dataclass(frozen=True)
class ResolvedEvidence:
    """Canonical evidence resolved from an ``evidence_ref`` (rank B)."""

    evidence_ref: str
    attested: bool = False  # signature + registry anchor verified
    confidence: float | None = None
    origin: str = ""  # ai | human | device
    reversible: bool | None = None
    coding: dict[str, str] = field(default_factory=dict)  # {"system":..,"code":..}
    provenance_ref: str = ""
    tamper: str = "unknown"  # ok | altered | unknown


@runtime_checkable
class EvidenceResolver(Protocol):
    """Resolve an ``evidence_ref`` to :class:`ResolvedEvidence`, or ``None``."""

    def resolve(self, evidence_ref: str) -> ResolvedEvidence | None: ...


class NullEvidenceResolver:
    """Fail-closed default: resolves nothing, so signals stay unattested."""

    def resolve(self, evidence_ref: str) -> ResolvedEvidence | None:
        return None


class StaticEvidenceResolver:
    """Reference resolver backed by an in-memory map (dev / test).

    A production resolver replaces this with a governed fetch + signature/anchor
    verification + per-persona redaction + an AuditEvent on access. The interface
    is identical, so callers do not change when the production resolver lands.
    """

    def __init__(self, store: dict[str, ResolvedEvidence] | None = None) -> None:
        self._store: dict[str, ResolvedEvidence] = dict(store or {})

    def add(self, evidence: ResolvedEvidence) -> None:
        self._store[evidence.evidence_ref] = evidence

    def resolve(self, evidence_ref: str) -> ResolvedEvidence | None:
        return self._store.get(evidence_ref)


def signal_from_evidence(
    base: PerceivedSignal, resolved: ResolvedEvidence | None
) -> PerceivedSignal:
    """Return *base* enriched with resolved-evidence hints (fail-closed).

    When resolution returns ``None`` or the evidence is tampered, the
    attestation / confidence hints are NOT trusted -- the signal keeps its
    conservative defaults so the governance core escalates rather than
    auto-proceeds. Only verified, untampered evidence raises ``attested``.
    """
    if resolved is None or resolved.tamper == "altered":
        return base
    attested = (resolved.attested and resolved.tamper == "ok") or base.attested
    return replace(
        base,
        attested=attested,
        confidence=resolved.confidence
        if resolved.confidence is not None
        else base.confidence,
        origin=resolved.origin or base.origin,
        reversible=resolved.reversible
        if resolved.reversible is not None
        else base.reversible,
    )
