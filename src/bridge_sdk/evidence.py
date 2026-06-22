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
    "is_seeded_simulation_grounded",
    "seeded_simulation_grounding_failures",
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
    source_span_ref: str = ""
    target_evidence_ref: str = ""
    seeded_dataset_id: str = ""
    persona_id: str = ""
    scenario_id: str = ""
    service_route: str = ""
    permission_scope: str = ""
    telemetry_ref: str = ""
    synthetic_telemetry: bool = False
    live_production_evidence: bool = False


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
    if (
        resolved is None
        or resolved.tamper == "altered"
        or seeded_simulation_grounding_failures(resolved)
    ):
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


def is_seeded_simulation_grounded(resolved: ResolvedEvidence) -> bool:
    """Return whether evidence can support accepted seeded-simulation claims."""

    return not seeded_simulation_grounding_failures(resolved)


def seeded_simulation_grounding_failures(resolved: ResolvedEvidence) -> list[str]:
    """Explain why evidence cannot yet be treated as accepted implementation proof.

    The bridge SDK may resolve signed evidence before live production. For mined
    research findings, signature is not enough: the evidence must also bind the
    source claim to target-repo evidence, a realistic seeded dataset, an agent
    persona, a scenario, the exercised service route, permission scope, and
    emitted telemetry. Any missing or synthetic/live-only component fails closed.
    """

    failures: list[str] = []
    required = {
        "source_span_ref": resolved.source_span_ref,
        "target_evidence_ref": resolved.target_evidence_ref,
        "seeded_dataset_id": resolved.seeded_dataset_id,
        "persona_id": resolved.persona_id,
        "scenario_id": resolved.scenario_id,
        "service_route": resolved.service_route,
        "permission_scope": resolved.permission_scope,
        "telemetry_ref": resolved.telemetry_ref,
    }
    for field_name, value in required.items():
        if not value.strip():
            failures.append(f"missing_{field_name}")
    if resolved.synthetic_telemetry:
        failures.append("synthetic_telemetry")
    if resolved.live_production_evidence:
        failures.append("live_production_evidence")
    return failures
