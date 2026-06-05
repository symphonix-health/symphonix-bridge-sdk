"""Canonical agent-native telemetry schema (frozen) + emitter-status audit.

This is the measurement counterpart to the twelve implementation workstreams.
The post-implementation measurement framework
(``BulletTrain/docs/AGENT_NATIVE_MEASUREMENT_AND_EVALUATION.md``) cannot be built
coherently unless the fields it joins on are FROZEN and their real emitters are
ground-truthed. This module is that frozen schema.

First principle (carried in from the programme handoff): the source analysis is a
document-to-implementation map with ASSUMPTIONS, not a code audit. A prior session
proved an assumed-"DONE" subsystem (the WS11 handoff inbox) was a client-side mock.
So every field below records whether a REAL subsystem emits it today
(``EmitterStatus``), with the SDK symbol that backs the claim
(``sdk_anchor``). "Verified emitting in a live request path" is kept strictly
separate from "exists as an SDK contract" and from "needs wiring". Each status
was established by reading the executable code, not the docstrings.

The schema is declarative on purpose: it is a contract every emitter must
conform to, not behaviour. ``tests/test_telemetry_schema.py`` ground-truths the
``sdk_anchor`` / ``status`` of each field against the real SDK classes by
introspection, so the verified-vs-assumed split cannot silently rot.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "CANONICAL_TELEMETRY_FIELDS",
    "EmitterStatus",
    "SCHEMA_VERSION",
    "TelemetryField",
    "fields_by_status",
    "freeze_fingerprint",
    "needs_wiring",
    "verified_live",
]

SCHEMA_VERSION = "1.3.0-frozen-2026-06-05"


class EmitterStatus(str, Enum):
    """How real the emission of a canonical field is, established by code review.

    Ordered most-real to least-real. The measurement framework treats only
    ``live`` as "verified emitting"; everything below it is a wiring backlog
    item that must be closed before a KPI built on the field is trustworthy.
    """

    live = "live"
    """A running service emits this field in a real request/execution path."""

    tested_helper = "tested_helper"
    """Emitted only via a tested integration helper, not wired to a live route."""

    sdk_contract = "sdk_contract"
    """Exists as an SDK dataclass field with unit tests; no service emits it."""

    partial = "partial"
    """An adjacent field is emitted, but not the canonical field as named."""

    needs_wiring = "needs_wiring"
    """No emitter exists anywhere; the field must be added or derived."""


@dataclass(frozen=True)
class TelemetryField:
    """One field in the frozen canonical telemetry schema."""

    canonical_name: str
    value_type: str                 # "string" | "enum:a|b" | "object" | "int"
    source_subsystem: str           # which subsystem owns the emission
    status: EmitterStatus
    sdk_anchor: str | None          # real SDK symbol backing the claim, or None
    in_handoff_eight: bool          # one of the eight fields the handoff froze
    normalization: str = ""         # how to derive the canonical field, if needed
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_name": self.canonical_name,
            "value_type": self.value_type,
            "source_subsystem": self.source_subsystem,
            "status": self.status.value,
            "sdk_anchor": self.sdk_anchor,
            "in_handoff_eight": self.in_handoff_eight,
            "normalization": self.normalization,
            "notes": self.notes,
        }


# The frozen canonical schema. Statuses were established by reading the code on
# 2026-06-05 (see the measurement doc for the file:line evidence behind each).
CANONICAL_TELEMETRY_FIELDS: tuple[TelemetryField, ...] = (
    TelemetryField(
        canonical_name="correlation_id",
        value_type="string",
        source_subsystem="bullettrain.security.audit / agent_audit",
        status=EmitterStatus.tested_helper,
        sdk_anchor="bridge_sdk.agent_audit.StepAuditRecords.correlation_id",
        in_handoff_eight=False,
        notes=(
            "The join key for every other field. The HTTP X-Correlation-ID "
            "middleware is live platform-wide. The AGENT-STEP triple is bound by "
            "correlation_id in the emit_step_audit helper, now reachable via the "
            "live POST /agent/step/audit route (audit_route.py, mounted on "
            "agent_manager); the route takes the correlation id from the request. "
            "Kept tested_helper until a production agent flow calls that route."
        ),
    ),
    TelemetryField(
        canonical_name="execution_mode",
        value_type="enum:typed_api|semantic_ui|browser",
        source_subsystem="agent_contract resolver / signalbox-mcp",
        status=EmitterStatus.sdk_contract,
        sdk_anchor="bridge_sdk.agent_contract.ResolverDecision.execution_mode",
        in_handoff_eight=True,
        normalization=(
            "codified once in agent_contract.EXECUTION_MODE_BY_PATH: api,nexus -> "
            "typed_api; ui_fallback -> semantic_ui; browser -> browser"
        ),
        notes=(
            "WIRED 2026-06-05 at the contract layer: ResolverDecision.execution_mode "
            "is a computed_field that normalises ResolverPath to the 3-valued mode, "
            "so model_dump() carries it and every face shares one normalisation "
            "(EXECUTION_MODE_BY_PATH). compose_step_audit now threads it onto the "
            "task reference. What remains for `live`: a running service must persist "
            "decision.execution_mode on each action (signalbox-mcp invoke_intent and "
            "the live audit path). Until then the API-first / browser-fallback KPIs "
            "are computable from contract-level data but not yet from production."
        ),
    ),
    TelemetryField(
        canonical_name="intent",
        value_type="string",
        source_subsystem="agent_contract resolver",
        status=EmitterStatus.sdk_contract,
        sdk_anchor="bridge_sdk.agent_contract.ResolverDecision.intent",
        in_handoff_eight=True,
        notes=(
            "Dotted intent name (e.g. claim.submit). Present in the resolver "
            "decision, the FHIR Task code, and the action_path; returned by "
            "signalbox invoke_intent. Not persisted to a telemetry sink per task."
        ),
    ),
    TelemetryField(
        canonical_name="prompt_variant",
        value_type="string",
        source_subsystem="prompt-engine -> agent_audit provenance",
        status=EmitterStatus.sdk_contract,
        sdk_anchor="bridge_sdk.agent_audit.ProvenanceFields.prompt_variant",
        in_handoff_eight=True,
        notes=(
            "WIRED 2026-06-05: ProvenanceFields now has a standalone prompt_variant "
            "(additive, optional), emitted in the provenance extension, and "
            "audit_route accepts it. The upstream source to populate it is "
            "prompt-engine healthcare RenderResult.variant (emitted to a metrics "
            "hook per render). Kept sdk_contract: no production prompt path yet "
            "joins the variant onto the agent action. Was needs_wiring (no field)."
        ),
    ),
    TelemetryField(
        canonical_name="policy_version",
        value_type="string",
        source_subsystem="agent_audit provenance",
        status=EmitterStatus.sdk_contract,
        sdk_anchor="bridge_sdk.agent_audit.ProvenanceFields.policy_version",
        in_handoff_eight=True,
        normalization=(
            "standalone policy_version now exists alongside the legacy combined "
            "prompt_policy_version surrogate; populate it to attribute policy "
            "changes apart from prompt variants"
        ),
        notes=(
            "WIRED 2026-06-05: ProvenanceFields gained a standalone policy_version "
            "(additive, optional), emitted in the provenance extension; the legacy "
            "prompt_policy_version is retained as the combined surrogate so no "
            "consumer breaks. Kept sdk_contract: no production caller populates the "
            "split fields yet. Was partial (only the conflated field existed)."
        ),
    ),
    TelemetryField(
        canonical_name="consent_projection_id",
        value_type="string",
        source_subsystem="consent_projection (WS9)",
        status=EmitterStatus.needs_wiring,
        sdk_anchor="bridge_sdk.consent_projection.ConsentProjection.to_token_claim",
        in_handoff_eight=True,
        normalization="derive id = f'{consent_reference}@v{consent_version}'",
        notes=(
            "to_token_claim() emits consent_reference + consent_version, never a "
            "consent_projection_id. A stable id must be derived from the pair so "
            "consent-denial-correctness can be joined to the projection that "
            "decided it. WS4 provenance carries consent_artefact (the reference) "
            "but not the versioned projection id."
        ),
    ),
    TelemetryField(
        canonical_name="audit_triple",
        value_type="object",  # {task_ref, provenance, audit_event, link_hash}
        source_subsystem="agent_audit (WS4)",
        status=EmitterStatus.tested_helper,
        sdk_anchor="bridge_sdk.agent_audit.StepAuditRecords",
        in_handoff_eight=True,
        notes=(
            "compose_step_audit() builds the linked Task+Provenance+AuditEvent with "
            "a shared correlation_id and a tamper-evident link_hash, and "
            "emit_step_audit() lands it in the real hash-chained AuditLogger. A LIVE "
            "route now exists (wired 2026-06-05): POST /agent/step/audit "
            "(bullettrain/agent_native/audit_route.py, mounted on the agent_manager "
            "service), proven by a real-ASGI test against the production AuditLogger. "
            "Kept tested_helper, not live, because no production agent flow CALLS it "
            "yet -- auto-emission per /v1/workflow step is the remaining adoption. "
            "Separately, bullettrain_fhir/audit.py still builds Provenance and "
            "AuditEvent with INDEPENDENT uuids (not linked). Audit completeness "
            "reaches the >99.5% KPI target once production callers emit the triple "
            "per action."
        ),
    ),
    TelemetryField(
        canonical_name="handoff_trigger",
        value_type=(
            "enum:triage_edge_case|consent_conflict|contradictory_records|"
            "booking_failure|low_confidence|policy_block"
        ),
        source_subsystem="human_handoff (WS11)",
        status=EmitterStatus.tested_helper,
        sdk_anchor="bridge_sdk.human_handoff.HandoffTrigger",
        in_handoff_eight=True,
        notes=(
            "HandoffPackage.trigger carries one of six deterministic triggers. "
            "provider-portal was wired to the real bridge_sdk ledger+inbox on "
            "2026-06-04 (caid-agent L-357), so this is the closest of the agent "
            "fields to a live emitter -- but it is one portal, not platform-wide."
        ),
    ),
    TelemetryField(
        canonical_name="reviewer_outcome",
        value_type="enum:unsafe|incorrect_harmless|correct_suboptimal|correct",
        source_subsystem="human_handoff inbox + reviewer rubric",
        status=EmitterStatus.sdk_contract,
        sdk_anchor="bridge_sdk.human_handoff.ReviewerOutcome",
        in_handoff_eight=True,
        normalization=(
            "the four-class grade is recorded alongside (not as) the resume|amend|"
            "cancel disposition; summarise_outcomes() rolls grades into the rates"
        ),
        notes=(
            "WIRED 2026-06-05 at the contract layer: ReviewerOutcome (unsafe / "
            "incorrect_harmless / correct_suboptimal / correct) + HandoffInbox.grade/"
            "outcome_of record the rubric grade distinct from the disposition; "
            "summarise_outcomes() yields unsafe_rate / correct_rate / error_rate for "
            "the scorecard. A live route also exists: POST /agent/step/review "
            "(bullettrain/agent_native/audit_route.py, mounted on agent_manager) "
            "lands the grade in the production audit trail joined by correlation_id, "
            "real-ASGI tested. Kept sdk_contract, not live: no production reviewer "
            "surface calls the route yet. Was needs_wiring (the field did not exist)."
        ),
    ),
    TelemetryField(
        canonical_name="evidence_bundle_id",
        value_type="string",
        source_subsystem="signalbox-mcp attestation",
        status=EmitterStatus.live,
        sdk_anchor=None,  # lives in signalbox-mcp, not bridge_sdk
        in_handoff_eight=False,
        notes=(
            "signalbox-mcp persists a capture manifest keyed by capture_id (uuid4) "
            "with screenshot_sha256, dom_sha256, FHIR fragments, an Ed25519 "
            "signature, and a GHARRA anchor (ledger_seq, entry_hash); capture is "
            "REJECTED if anchoring or signing fails. This is the one agent-native "
            "evidence field verified emitting in a live path today."
        ),
    ),
    TelemetryField(
        canonical_name="autonomy_level",
        value_type="enum:shadow|advisory|auto_with_threshold_hitl",
        source_subsystem="agent_contract / clinical_safety_case",
        status=EmitterStatus.sdk_contract,
        sdk_anchor="bridge_sdk.agent_contract.AutonomyLevel",
        in_handoff_eight=False,
        notes=(
            "Each intent carries an autonomy_default and to_fhir_task() writes the "
            "level into a FHIR Task extension. The promotion ladder (WS12) reads "
            "ClinicalSafetyCase AutonomyStage. Needed on every record so KPIs can "
            "be sliced by the rung the action ran at."
        ),
    ),
)


def fields_by_status(status: EmitterStatus) -> tuple[TelemetryField, ...]:
    """All canonical fields at a given emitter status."""
    return tuple(f for f in CANONICAL_TELEMETRY_FIELDS if f.status is status)


def verified_live() -> tuple[TelemetryField, ...]:
    """Fields a real subsystem emits in a live path today (verified emitting)."""
    return fields_by_status(EmitterStatus.live)


def needs_wiring() -> tuple[TelemetryField, ...]:
    """Fields that are not yet trustworthy telemetry (gap + partial + contract).

    Everything that is not ``live`` is, for measurement purposes, a wiring
    backlog item: a KPI built on it inherits an unverified assumption.
    """
    return tuple(
        f for f in CANONICAL_TELEMETRY_FIELDS if f.status is not EmitterStatus.live
    )


def freeze_fingerprint() -> str:
    """Stable sha256 over the frozen (name, status) pairs.

    The measurement doc cites this so a silent change to the schema -- a renamed
    field or a status quietly upgraded from needs_wiring to live without the
    wiring -- is detectable. Recompute and compare to catch drift.
    """
    payload = [
        {"name": f.canonical_name, "status": f.status.value}
        for f in CANONICAL_TELEMETRY_FIELDS
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
