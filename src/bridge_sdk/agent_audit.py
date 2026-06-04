"""Agent audit composer: three linked records per agent step + decision cards.

Workstream 4. Makes every agent action both security-auditable and clinically
explainable. Depends on WS2-3.

Design decision: EXTEND, don't rebuild (verified prior art + an explicit
"DO NOT rebuild" instruction in ``bullettrain/security/CLAUDE.md``):

- ``bullettrain/security/audit.py`` ``AuditLogger.log_event`` already emits a
  hash-chained ``AuditEvent`` with PHI redaction. The BulletTrain-side composer
  calls THAT for the security record -- this module never reimplements it.
- ``bullettrain_fhir/audit.py`` already builds FHIR ``AuditEvent`` + ``Provenance``
  dicts, but they are NOT linked to the WS2 Task and carry no shared
  correlation id. That linkage is the genuine gap.
- ``bullettrain/observability`` already provides OTel + a correlation id var.

What is genuinely NEW (FR-AU-*):
- ONE composer producing three records for a single agent step -- a Task-state
  update reference, a Provenance record, and an AuditEvent -- mutually
  cross-referenced by a single ``correlation_id`` (FR-AU-001).
- The mandated provenance fields: persona, sponsor, consent artefact,
  route-admission evidence, prompt/policy version, model version, action path
  (FR-AU-002); a missing required field fails validation.
- A decision-card projection: "why did the agent act + what evidence" (FR-AU-003).
- A tamper-evident link hash over the triple (NFR-AU-002), built with the exact
  construction WS2's ``ExecutionLedger`` / BulletTrain ``HashChain`` use.

Requirements: FR-AU-001..003, NFR-AU-001..002
(``BulletTrain/docs/AGENT_AUDIT_REQUIREMENTS.md``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AuditCompositionError",
    "DecisionCard",
    "ProvenanceFields",
    "StepAuditRecords",
    "compose_step_audit",
    "decision_card",
]

# The seven mandated provenance fields (FR-AU-002). A provenance record missing
# any of these fails validation.
REQUIRED_PROVENANCE_FIELDS: tuple[str, ...] = (
    "persona",
    "sponsor",
    "consent_artefact",
    "route_admission",
    "prompt_policy_version",
    "model_version",
    "action_path",
)


class AuditCompositionError(Exception):
    """Raised when an agent-step audit record is incomplete or inconsistent."""


@dataclass(frozen=True)
class ProvenanceFields:
    """The mandated authorship/derivation fields for a single agent step."""

    persona: str                  # acting persona key
    sponsor: str                  # user or organisation on whose behalf (act.sub)
    consent_artefact: str         # reference to the consent projection
    route_admission: str          # route-admission evidence id
    prompt_policy_version: str    # prompt/policy version used
    model_version: str            # model version that decided
    action_path: str              # resolved intent / UI action path

    def missing(self) -> list[str]:
        """Return the names of any required fields that are empty."""
        return [f for f in REQUIRED_PROVENANCE_FIELDS if not getattr(self, f)]


def _data_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StepAuditRecords:
    """The three linked records produced for one agent step (FR-AU-001)."""

    correlation_id: str
    task_ref: dict[str, Any]      # reference to the WS2 Task state update
    provenance: dict[str, Any]    # FHIR Provenance (who/what produced the change)
    audit_event: dict[str, Any]   # FHIR AuditEvent (the access/security event)
    link_hash: str                # tamper-evident hash over the triple

    def all_cross_referenced(self) -> bool:
        """True iff all three records carry the same correlation_id (FR-AU-001-AC01)."""
        cid = self.correlation_id
        return (
            self.task_ref.get("correlation_id") == cid
            and self.provenance.get("correlation_id") == cid
            and self.audit_event.get("correlation_id") == cid
        )

    def verify_link(self) -> bool:
        """Recompute the link hash and confirm it is intact (NFR-AU-002)."""
        return _compute_link_hash(
            self.correlation_id, self.task_ref, self.provenance, self.audit_event
        ) == self.link_hash


def _compute_link_hash(
    correlation_id: str,
    task_ref: dict[str, Any],
    provenance: dict[str, Any],
    audit_event: dict[str, Any],
) -> str:
    """Hash the whole triple -- altering any record breaks the hash (NFR-AU-002)."""
    payload = {
        "correlation_id": correlation_id,
        "task_ref": task_ref,
        "provenance": provenance,
        "audit_event": audit_event,
    }
    return _data_hash(payload)


def compose_step_audit(
    *,
    correlation_id: str,
    workflow_id: str,
    task_status: str,
    fields: ProvenanceFields,
    action: str,
    outcome: str,
    timestamp: str,
    resource_type: str = "Task",
    patient_reference: str | None = None,
) -> StepAuditRecords:
    """Compose the three linked audit records for a single agent step.

    Produces a Task-state-update reference, a FHIR ``Provenance`` record, and a
    FHIR ``AuditEvent`` -- all sharing ``correlation_id`` -- plus a tamper-evident
    link hash. Raises ``AuditCompositionError`` if any mandated provenance field
    is missing (FR-AU-002-AC01).
    """
    missing = fields.missing()
    if missing:
        raise AuditCompositionError(
            f"provenance record missing required field(s): {missing}"
        )

    target_ref = (
        patient_reference
        if patient_reference
        else f"{resource_type}/{workflow_id}"
    )

    task_ref = {
        "correlation_id": correlation_id,
        "resourceType": "TaskReference",
        "workflow_id": workflow_id,
        "status": task_status,
        "action_path": fields.action_path,
    }

    provenance = {
        "correlation_id": correlation_id,
        "resourceType": "Provenance",
        "recorded": timestamp,
        "target": [{"reference": f"{resource_type}/{workflow_id}"}],
        "agent": [
            {
                "who": {"identifier": {"value": fields.persona}},
                "onBehalfOf": {"identifier": {"value": fields.sponsor}},
            }
        ],
        "entity": [
            {"role": "source", "what": {"reference": fields.route_admission}},
        ],
        # Mandated derivation fields (FR-AU-002), kept explicit for the verifier.
        "extension": {
            "consent_artefact": fields.consent_artefact,
            "route_admission": fields.route_admission,
            "prompt_policy_version": fields.prompt_policy_version,
            "model_version": fields.model_version,
            "action_path": fields.action_path,
        },
    }

    audit_event = {
        "correlation_id": correlation_id,
        "resourceType": "AuditEvent",
        "recorded": timestamp,
        "action": action[:1].upper() if action else "E",
        "outcome": outcome,
        "agent": [
            {
                "who": {"identifier": {"value": fields.persona}},
                "requestor": True,
                "purposeOfEvent": [{"text": fields.sponsor}],
            }
        ],
        "source": {"observer": {"display": "Symphonix Agent Runtime"}},
        "entity": [{"what": {"reference": target_ref}}],
    }

    link_hash = _compute_link_hash(
        correlation_id, task_ref, provenance, audit_event
    )
    return StepAuditRecords(
        correlation_id=correlation_id,
        task_ref=task_ref,
        provenance=provenance,
        audit_event=audit_event,
        link_hash=link_hash,
    )


@dataclass(frozen=True)
class DecisionCard:
    """A human-facing "why did the agent act + what evidence" card (FR-AU-003)."""

    correlation_id: str
    persona: str
    action_path: str
    outcome: str
    rationale: str
    evidence_references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "persona": self.persona,
            "action_path": self.action_path,
            "outcome": self.outcome,
            "rationale": self.rationale,
            "evidence_references": list(self.evidence_references),
        }


def decision_card(
    records: StepAuditRecords,
    *,
    rationale: str,
    evidence_references: list[str] | None = None,
) -> DecisionCard:
    """Project a completed step's audit records into a decision card (FR-AU-003).

    The card cites the same correlation id, persona, action path and outcome as
    the underlying records, and lists the evidence references a reviewer needs.
    Defaults the evidence list to the route-admission + consent artefact already
    captured in provenance, so a card always carries review-grade evidence.
    """
    prov_ext = records.provenance.get("extension", {})
    default_evidence = [
        v
        for v in (
            prov_ext.get("route_admission"),
            prov_ext.get("consent_artefact"),
        )
        if v
    ]
    evidence = evidence_references if evidence_references is not None else default_evidence
    return DecisionCard(
        correlation_id=records.correlation_id,
        persona=records.provenance["agent"][0]["who"]["identifier"]["value"],
        action_path=records.task_ref["action_path"],
        outcome=records.audit_event["outcome"],
        rationale=rationale,
        evidence_references=evidence,
    )
