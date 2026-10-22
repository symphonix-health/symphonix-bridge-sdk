"""Canonical Clinical Decision Record (CDR) builder, validator, and role masker (W-03).

Implements the single estate-wide Clinical Decision Record contract defined in
``schemas/clinical-decision-record.schema.json`` (version ``1.0.0``), grounded in
source-verified published frameworks:
- FUTURE-AI (Lekadir et al., BMJ 2025;388:e081554, doi:10.1136/bmj-2024-081554)
- WHO Ethics and governance of AI for health (2021, ISBN 9789240029200)
- TRIPOD+AI (Collins et al., BMJ 2024;385:e078378, doi:10.1136/bmj-2023-078378)
- DECIDE-AI (Vasey et al., BMJ 2022;377:e070904, doi:10.1136/bmj-2022-070904;
  Nat Med 2022;28(5):924-933, doi:10.1038/s41591-022-01772-9)

Every GHARRA-registered clinical-inference agent must emit a conformant CDR via this
builder rather than hand-rolling repository-local explanation formats.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CDR_SCHEMA_VERSION = "1.0.0"
CDR_SCHEMA_ID = (
    "https://gharra.symphonix.health/schemas/clinical-decision-record.schema.json"
)

RECORD_ID_RE = re.compile(r"^cdr_[a-z0-9-]{8,64}$")
FACT_ID_RE = re.compile(r"^F[0-9]{1,6}$")
EVIDENCE_ID_RE = re.compile(r"^E[0-9]{1,6}$")
ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)

CLINICAL_DOMAINS = frozenset(
    {
        "diagnostics",
        "treatment",
        "prescribing",
        "triage",
        "referral",
        "care_planning",
        "risk_assessment",
        "interpretation",
        "monitoring",
        "mental_health",
        "maternal_health",
        "nutrition",
        "oncology",
        "other",
    }
)

OUTPUT_ROLES = frozenset(
    {
        "primary",
        "differential",
        "recommended",
        "alternative",
        "excluded",
        "escalation",
        "information",
    }
)

FACT_KINDS = frozenset(
    {
        "symptom",
        "sign",
        "vital",
        "laboratory",
        "imaging",
        "medication",
        "allergy",
        "history",
        "demographic",
        "social",
        "screening",
        "genomics",
        "other",
    }
)

FACT_STRENGTHS = frozenset({"primary", "supporting", "weak", "contradictory"})

EVIDENCE_KINDS = frozenset(
    {
        "clinical_guideline",
        "systematic_review",
        "primary_study",
        "terminology_release",
        "drug_information",
        "regulatory_standard",
        "internal_safety_rule",
        "service_response",
        "research_framework",
    }
)

FRAMEWORKS = frozenset(
    {
        "FUTURE-AI",
        "WHO-AI-ETHICS",
        "TRIPOD+AI",
        "DECIDE-AI",
        "EQUATOR",
        "INTERNAL-SAFETY",
    }
)

CALIBRATION_METHODS = frozenset(
    {
        "identity",
        "temperature_scaling",
        "isotonic_lookup_table",
        "empirical_calibration_logged",
    }
)

CALCULATION_METHODS = frozenset(
    {
        "deterministic_rule_set",
        "scored_rule_set",
        "bayesian_posterior",
        "retrieved_llm",
        "ensemble_vote",
        "calibrated_heuristic",
        "hybrid",
    }
)

CONFLICT_DIRECTIONS = frozenset({"supports", "contradicts", "neutral"})

ALERT_SEVERITIES = frozenset({"critical", "high", "moderate", "low", "info"})

DECISION_STATUSES = frozenset(
    {"approved", "requires_human_review", "abstained", "blocked"}
)

PROVENANCE_INPUT_TYPES = frozenset(
    {
        "clinical_record",
        "terminology_service",
        "guideline_store",
        "prescribing_check",
        "imaging_service",
        "laboratory_service",
        "llm_prompt",
        "retrieval",
        "policy_engine",
        "other_service",
    }
)

REVISION_KINDS = frozenset({"commit_sha", "release_tag", "content_hash"})

CLINICIAN_ACTIONS = frozenset(
    {"accepted", "rejected", "modified", "deferred", "not_yet_reviewed"}
)


class ClinicalDecisionRecordError(ValueError):
    """Raised when a Clinical Decision Record fails schema or semantic validation."""


def default_cdr_schema_path() -> Path:
    """Return the path to the bundled or workspace CDR JSON Schema."""
    bundled = (
        Path(__file__).resolve().parent
        / "schemas"
        / "clinical-decision-record.schema.json"
    )
    if bundled.is_file():
        return bundled
    workspace = os.environ.get("SYMPHONIX_WORKSPACE_ROOT")
    if workspace:
        candidate = (
            Path(workspace)
            / "symphonix-assurance"
            / "schemas"
            / "clinical-decision-record.schema.json"
        )
        if candidate.is_file():
            return candidate
    raise ClinicalDecisionRecordError(
        f"Clinical Decision Record schema file not found at {bundled}"
    )


def load_cdr_schema() -> dict[str, Any]:
    """Load and parse the canonical CDR JSON Schema."""
    path = default_cdr_schema_path()
    return json.loads(path.read_text(encoding="utf-8"))


def default_mask_pii(text: str) -> str:
    """Mask digits in free-text clinical strings to prevent raw identifier leakage."""
    return re.sub(r"\d", "X", text)


def deterministic_cdr_id(*parts: str) -> str:
    """Build a deterministic record_id matching ``^cdr_[a-z0-9-]{8,64}$``."""
    material = "|".join(str(p or "").strip() for p in parts if p)
    if not material:
        material = datetime.now(UTC).isoformat()
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"cdr_{digest}"


def resolve_repo_code_change(
    repository: str,
    repo_dir: str | Path | None = None,
) -> CdrCodeChange:
    """Resolve and verify the current git commit SHA for ``repository``."""
    candidates: list[Path] = []
    if repo_dir is not None:
        candidates.append(Path(repo_dir))
    workspace = os.environ.get("SYMPHONIX_WORKSPACE_ROOT")
    if workspace:
        candidates.append(Path(workspace) / repository)
    candidates.append(Path(__file__).resolve().parents[2])

    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
            done = subprocess.run(
                ["git", "-C", str(candidate), "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            sha = (done.stdout or "").strip()
            if done.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha):
                return CdrCodeChange(
                    repository=repository,
                    revision=sha,
                    revision_kind="commit_sha",
                    revision_verified=True,
                )
        except (OSError, subprocess.TimeoutExpired):
            continue

    digest = hashlib.sha256(f"{repository}:{CDR_SCHEMA_VERSION}".encode("utf-8")).hexdigest()[:16]
    return CdrCodeChange(
        repository=repository,
        revision=f"sha256:{digest}",
        revision_kind="content_hash",
        revision_verified=False,
    )


def _strip_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in mapping.items() if v is not None}


@dataclass(frozen=True)
class CdrAgent:
    gharra_agent_id: str
    display_name: str
    version: str
    clinical_domain: str
    repository: str | None = None
    responsible_owner_org_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "gharra_agent_id": self.gharra_agent_id,
                "display_name": self.display_name,
                "version": self.version,
                "clinical_domain": self.clinical_domain,
                "repository": self.repository,
                "responsible_owner_org_id": self.responsible_owner_org_id,
            }
        )


@dataclass(frozen=True)
class CdrFactSource:
    source_system: str | None = None
    source_record_id: str | None = None
    resolved: bool = False
    observed_at: str | None = None
    jurisdiction: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "source_system": self.source_system,
                "source_record_id": self.source_record_id,
                "resolved": self.resolved,
                "observed_at": self.observed_at,
                "jurisdiction": self.jurisdiction,
            }
        )


@dataclass(frozen=True)
class CdrSupportingFact:
    fact_id: str
    kind: str
    value: str | int | float | bool
    source: CdrFactSource | Mapping[str, Any] | None = None
    negated: bool | None = None
    temporal_note: str | None = None
    identifier_scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        src = (
            self.source.to_dict()
            if isinstance(self.source, CdrFactSource)
            else (dict(self.source) if isinstance(self.source, Mapping) else None)
        )
        return _strip_none(
            {
                "fact_id": self.fact_id,
                "kind": self.kind,
                "value": self.value,
                "source": src,
                "negated": self.negated,
                "temporal_note": self.temporal_note,
                "identifier_scope": self.identifier_scope,
            }
        )


@dataclass(frozen=True)
class CdrFactReference:
    fact_id: str
    how_it_contributed: str
    strength: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "fact_id": self.fact_id,
                "how_it_contributed": self.how_it_contributed,
                "strength": self.strength,
            }
        )


@dataclass(frozen=True)
class CdrCalibration:
    raw_confidence: float | None = None
    calibrated_confidence: float | None = None
    method: str | None = None
    calibration_table_version: str | None = None
    drift_check: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "raw_confidence": self.raw_confidence,
                "calibrated_confidence": self.calibrated_confidence,
                "method": self.method,
                "calibration_table_version": self.calibration_table_version,
                "drift_check": self.drift_check,
            }
        )


@dataclass(frozen=True)
class CdrDecisionOutput:
    label: str
    code_system: str
    role: str
    facts_relied_upon: Sequence[CdrFactReference | Mapping[str, Any]]
    confidence: float
    code: str | None = None
    calibration: CdrCalibration | Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        refs = [
            r.to_dict() if isinstance(r, CdrFactReference) else dict(r)
            for r in self.facts_relied_upon
        ]
        cal = (
            self.calibration.to_dict()
            if isinstance(self.calibration, CdrCalibration)
            else (
                dict(self.calibration)
                if isinstance(self.calibration, Mapping)
                else None
            )
        )
        return _strip_none(
            {
                "label": self.label,
                "code_system": self.code_system,
                "code": self.code,
                "role": self.role,
                "facts_relied_upon": refs,
                "confidence": float(self.confidence),
                "calibration": cal,
            }
        )


@dataclass(frozen=True)
class CdrDecision:
    kind: str
    summary: str
    outputs: Sequence[CdrDecisionOutput | Mapping[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "outputs": [
                o.to_dict() if isinstance(o, CdrDecisionOutput) else dict(o)
                for o in self.outputs
            ],
        }


@dataclass(frozen=True)
class CdrFrameworkBasis:
    framework: str
    principle: str

    def to_dict(self) -> dict[str, Any]:
        return {"framework": self.framework, "principle": self.principle}


@dataclass(frozen=True)
class CdrEvidenceItem:
    evidence_id: str
    kind: str
    identifier: str
    version_or_release: str
    jurisdiction: str | None = None
    retrieved_at: str | None = None
    supports: Sequence[str] | None = None
    research_framework_basis: Sequence[CdrFrameworkBasis | Mapping[str, Any]] | None = (
        None
    )

    def to_dict(self) -> dict[str, Any]:
        basis = (
            [
                b.to_dict() if isinstance(b, CdrFrameworkBasis) else dict(b)
                for b in self.research_framework_basis
            ]
            if self.research_framework_basis is not None
            else None
        )
        return _strip_none(
            {
                "evidence_id": self.evidence_id,
                "kind": self.kind,
                "identifier": self.identifier,
                "version_or_release": self.version_or_release,
                "jurisdiction": self.jurisdiction,
                "retrieved_at": self.retrieved_at,
                "supports": list(self.supports) if self.supports is not None else None,
                "research_framework_basis": basis,
            }
        )


@dataclass(frozen=True)
class CdrMissingInfo:
    what: str
    why_it_matters: str
    requested_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "what": self.what,
                "why_it_matters": self.why_it_matters,
                "requested_from": self.requested_from,
            }
        )


@dataclass(frozen=True)
class CdrConflictingFinding:
    description: str
    direction: str
    fact_or_evidence_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "description": self.description,
                "direction": self.direction,
                "fact_or_evidence_ref": self.fact_or_evidence_ref,
            }
        )


@dataclass(frozen=True)
class CdrCalculationInput:
    name: str
    value: str | int | float | bool
    derived_from: Sequence[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "name": self.name,
                "value": self.value,
                "derived_from": (
                    list(self.derived_from)
                    if self.derived_from is not None
                    else None
                ),
            }
        )


@dataclass(frozen=True)
class CdrCalculationThreshold:
    name: str
    value: float
    resulting_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "name": self.name,
                "value": float(self.value),
                "resulting_status": self.resulting_status,
            }
        )


@dataclass(frozen=True)
class CdrCalculation:
    method: str
    inputs_used: Sequence[CdrCalculationInput | Mapping[str, Any]]
    thresholds_applied: Sequence[CdrCalculationThreshold | Mapping[str, Any]] | None = (
        None
    )
    reproducible: bool = False
    verification_command: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "method": self.method,
                "inputs_used": [
                    i.to_dict() if isinstance(i, CdrCalculationInput) else dict(i)
                    for i in self.inputs_used
                ],
                "thresholds_applied": (
                    [
                        t.to_dict()
                        if isinstance(t, CdrCalculationThreshold)
                        else dict(t)
                        for t in self.thresholds_applied
                    ]
                    if self.thresholds_applied is not None
                    else None
                ),
                "reproducible": self.reproducible,
                "verification_command": self.verification_command,
            }
        )


@dataclass(frozen=True)
class CdrUncertainty:
    statement: str
    missing_information: Sequence[CdrMissingInfo | Mapping[str, Any]]
    calibrated_confidence: float
    calibration_method: str
    conflicting_findings: Sequence[CdrConflictingFinding | Mapping[str, Any]] | None = (
        None
    )
    calculation: CdrCalculation | Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        calc = (
            self.calculation.to_dict()
            if isinstance(self.calculation, CdrCalculation)
            else (
                dict(self.calculation)
                if isinstance(self.calculation, Mapping)
                else None
            )
        )
        return _strip_none(
            {
                "statement": self.statement,
                "missing_information": [
                    m.to_dict() if isinstance(m, CdrMissingInfo) else dict(m)
                    for m in self.missing_information
                ],
                "conflicting_findings": (
                    [
                        c.to_dict()
                        if isinstance(c, CdrConflictingFinding)
                        else dict(c)
                        for c in self.conflicting_findings
                    ]
                    if self.conflicting_findings is not None
                    else None
                ),
                "calibrated_confidence": float(self.calibrated_confidence),
                "calibration_method": self.calibration_method,
                "calculation": calc,
            }
        )


@dataclass(frozen=True)
class CdrSafetyAlert:
    severity: str
    message: str
    rule_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "severity": self.severity,
                "message": self.message,
                "rule_id": self.rule_id,
            }
        )


@dataclass(frozen=True)
class CdrAbstention:
    abstained: bool
    reason_code: str | None
    minimum_confidence_threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "abstained": bool(self.abstained),
            "reason_code": self.reason_code,
        }
        if self.minimum_confidence_threshold is not None:
            res["minimum_confidence_threshold"] = float(
                self.minimum_confidence_threshold
            )
        return res


@dataclass(frozen=True)
class CdrSafety:
    contraindications_checked: bool
    alerts: Sequence[CdrSafetyAlert | Mapping[str, Any]]
    requires_human_review: bool
    review_role: str | None
    abstention: CdrAbstention | Mapping[str, Any]
    decision_status: str | None = None
    safety_rule_hits: Sequence[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        abst = (
            self.abstention.to_dict()
            if isinstance(self.abstention, CdrAbstention)
            else dict(self.abstention)
        )
        res: dict[str, Any] = {
            "contraindications_checked": bool(self.contraindications_checked),
            "alerts": [
                a.to_dict() if isinstance(a, CdrSafetyAlert) else dict(a)
                for a in self.alerts
            ],
            "requires_human_review": bool(self.requires_human_review),
            "review_role": self.review_role,
            "abstention": abst,
        }
        if self.decision_status is not None:
            res["decision_status"] = self.decision_status
        if self.safety_rule_hits is not None:
            res["safety_rule_hits"] = list(self.safety_rule_hits)
        return res


@dataclass(frozen=True)
class CdrModelOrComponent:
    identifier: str
    version: str
    provider: str | None = None
    deployment_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "identifier": self.identifier,
                "version": self.version,
                "provider": self.provider,
                "deployment_fingerprint": self.deployment_fingerprint,
            }
        )


@dataclass(frozen=True)
class CdrProvenanceInput:
    type: str
    identifier: str
    version_or_release: str | None = None
    tool: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "type": self.type,
                "identifier": self.identifier,
                "version_or_release": self.version_or_release,
                "tool": self.tool,
            }
        )


@dataclass(frozen=True)
class CdrCodeChange:
    repository: str
    revision: str
    revision_kind: str = "commit_sha"
    revision_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "revision": self.revision,
            "revision_kind": self.revision_kind,
            "revision_verified": bool(self.revision_verified),
        }


@dataclass(frozen=True)
class CdrProvenance:
    model_or_component: CdrModelOrComponent | Mapping[str, Any]
    inputs: Sequence[CdrProvenanceInput | Mapping[str, Any]]
    prompt_identifier: str | None = None
    prompt_version: str | None = None
    code_change: CdrCodeChange | Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        mc = (
            self.model_or_component.to_dict()
            if isinstance(self.model_or_component, CdrModelOrComponent)
            else dict(self.model_or_component)
        )
        cc = (
            self.code_change.to_dict()
            if isinstance(self.code_change, CdrCodeChange)
            else (
                dict(self.code_change)
                if isinstance(self.code_change, Mapping)
                else None
            )
        )
        return _strip_none(
            {
                "model_or_component": mc,
                "inputs": [
                    i.to_dict() if isinstance(i, CdrProvenanceInput) else dict(i)
                    for i in self.inputs
                ],
                "prompt_identifier": self.prompt_identifier,
                "prompt_version": self.prompt_version,
                "code_change": cc,
            }
        )


@dataclass(frozen=True)
class CdrTenantScope:
    patient_scope: str
    facility_scope: str
    purpose_of_use: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "patient_scope": self.patient_scope,
                "facility_scope": self.facility_scope,
                "purpose_of_use": self.purpose_of_use,
            }
        )


@dataclass(frozen=True)
class CdrClinicianAction:
    action: str = "not_yet_reviewed"
    acted_at: str | None = None
    accountable_clinician: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _strip_none(
            {
                "action": self.action,
                "acted_at": self.acted_at,
                "accountable_clinician": self.accountable_clinician,
            }
        )


@dataclass(frozen=True)
class CdrAudit:
    audit_reference: str
    persisted: bool
    tenant_scope: CdrTenantScope | Mapping[str, Any]
    resolved_in_audit_store: bool = False
    clinician_action: CdrClinicianAction | Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        ts = (
            self.tenant_scope.to_dict()
            if isinstance(self.tenant_scope, CdrTenantScope)
            else dict(self.tenant_scope)
        )
        ca = (
            self.clinician_action.to_dict()
            if isinstance(self.clinician_action, CdrClinicianAction)
            else (
                dict(self.clinician_action)
                if isinstance(self.clinician_action, Mapping)
                else None
            )
        )
        return _strip_none(
            {
                "audit_reference": self.audit_reference,
                "persisted": bool(self.persisted),
                "resolved_in_audit_store": bool(self.resolved_in_audit_store),
                "tenant_scope": ts,
                "clinician_action": ca,
            }
        )


def _is_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _is_resolvable_identifier(identifier: str) -> bool:
    """True when an evidence identifier has an explicit authority/namespace or URI/DOI."""
    text = (identifier or "").strip()
    if len(text) < 4:
        return False
    # Must contain an authority separator (: or /) and must not contain spaces-only prose
    if ":" not in text and "/" not in text:
        return False
    return True


def validate_clinical_decision_record(record: Mapping[str, Any]) -> list[str]:
    """Validate ``record`` against the canonical CDR contract and semantic safety rules.

    Returns a list of human-readable problem strings; an empty list means valid.
    """
    if not isinstance(record, Mapping):
        return ["CDR root must be a JSON object"]

    problems: list[str] = []

    required_top = {
        "schema_version",
        "record_id",
        "agent",
        "decision",
        "supporting_facts",
        "evidence",
        "uncertainty",
        "safety",
        "provenance",
        "audit",
    }
    allowed_top = required_top | {"recorded_at"}
    for req in sorted(required_top):
        if req not in record:
            problems.append(f"missing required top-level field '{req}'")
    extra_top = set(record.keys()) - allowed_top
    if extra_top:
        problems.append(f"unexpected top-level field(s): {sorted(extra_top)}")

    if record.get("schema_version") != CDR_SCHEMA_VERSION:
        problems.append(
            f"schema_version must equal '{CDR_SCHEMA_VERSION}', got {record.get('schema_version')!r}"
        )

    rec_id = str(record.get("record_id") or "")
    if not RECORD_ID_RE.fullmatch(rec_id):
        problems.append(
            f"record_id {rec_id!r} does not match pattern {RECORD_ID_RE.pattern}"
        )

    recorded_at = record.get("recorded_at")
    if recorded_at is not None and (
        not isinstance(recorded_at, str) or not ISO_DATETIME_RE.fullmatch(recorded_at)
    ):
        problems.append(f"recorded_at {recorded_at!r} is not a valid ISO-8601 date-time")

    # 1. agent
    agent = record.get("agent")
    if not isinstance(agent, Mapping):
        problems.append("agent must be an object")
    else:
        req_agent = {"gharra_agent_id", "display_name", "version", "clinical_domain"}
        allow_agent = req_agent | {"repository", "responsible_owner_org_id"}
        for k in sorted(req_agent):
            if not isinstance(agent.get(k), str) or not str(agent.get(k)).strip():
                problems.append(f"agent.{k} must be a non-empty string")
        if set(agent.keys()) - allow_agent:
            problems.append(
                f"agent has unexpected field(s): {sorted(set(agent.keys()) - allow_agent)}"
            )
        domain = agent.get("clinical_domain")
        if domain not in CLINICAL_DOMAINS:
            problems.append(f"agent.clinical_domain {domain!r} not in {sorted(CLINICAL_DOMAINS)}")

    # 2. supporting_facts
    facts = record.get("supporting_facts")
    known_fact_ids: set[str] = set()
    if not isinstance(facts, Sequence) or isinstance(facts, (str, bytes)) or len(facts) < 1:
        problems.append("supporting_facts must be a non-empty array")
    else:
        allow_fact = {
            "fact_id",
            "kind",
            "value",
            "source",
            "negated",
            "temporal_note",
            "identifier_scope",
        }
        allow_source = {
            "source_system",
            "source_record_id",
            "resolved",
            "observed_at",
            "jurisdiction",
        }
        for idx, fact in enumerate(facts):
            if not isinstance(fact, Mapping):
                problems.append(f"supporting_facts[{idx}] must be an object")
                continue
            if set(fact.keys()) - allow_fact:
                problems.append(
                    f"supporting_facts[{idx}] has unexpected field(s): {sorted(set(fact.keys()) - allow_fact)}"
                )
            fid = str(fact.get("fact_id") or "")
            if not FACT_ID_RE.fullmatch(fid):
                problems.append(
                    f"supporting_facts[{idx}].fact_id {fid!r} must match {FACT_ID_RE.pattern}"
                )
            elif fid in known_fact_ids:
                problems.append(f"duplicate supporting_facts fact_id {fid!r}")
            else:
                known_fact_ids.add(fid)

            fkind = fact.get("kind")
            if fkind not in FACT_KINDS:
                problems.append(
                    f"supporting_facts[{idx}].kind {fkind!r} not in {sorted(FACT_KINDS)}"
                )
            fval = fact.get("value")
            if not isinstance(fval, (str, int, float, bool)) or (
                isinstance(fval, str) and not fval.strip()
            ):
                problems.append(
                    f"supporting_facts[{idx}].value must be a non-empty string, number, or boolean"
                )
            src = fact.get("source")
            if src is not None:
                if not isinstance(src, Mapping):
                    problems.append(f"supporting_facts[{idx}].source must be an object")
                elif set(src.keys()) - allow_source:
                    problems.append(
                        f"supporting_facts[{idx}].source has unexpected field(s): {sorted(set(src.keys()) - allow_source)}"
                    )

    # 3. decision
    decision = record.get("decision")
    if not isinstance(decision, Mapping):
        problems.append("decision must be an object")
    else:
        allow_decision = {"kind", "summary", "outputs"}
        if set(decision.keys()) - allow_decision:
            problems.append(
                f"decision has unexpected field(s): {sorted(set(decision.keys()) - allow_decision)}"
            )
        if not isinstance(decision.get("kind"), str) or not decision["kind"].strip():
            problems.append("decision.kind must be a non-empty string")
        summary = decision.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 2000:
            problems.append("decision.summary must be a non-empty string <= 2000 chars")
        outputs = decision.get("outputs")
        if (
            not isinstance(outputs, Sequence)
            or isinstance(outputs, (str, bytes))
            or len(outputs) < 1
        ):
            problems.append("decision.outputs must be a non-empty array")
        else:
            allow_output = {
                "label",
                "code_system",
                "code",
                "role",
                "facts_relied_upon",
                "confidence",
                "calibration",
            }
            allow_fref = {"fact_id", "how_it_contributed", "strength"}
            allow_cal = {
                "raw_confidence",
                "calibrated_confidence",
                "method",
                "calibration_table_version",
                "drift_check",
            }
            for oidx, out in enumerate(outputs):
                if not isinstance(out, Mapping):
                    problems.append(f"decision.outputs[{oidx}] must be an object")
                    continue
                if set(out.keys()) - allow_output:
                    problems.append(
                        f"decision.outputs[{oidx}] has unexpected field(s): {sorted(set(out.keys()) - allow_output)}"
                    )
                label = out.get("label")
                if not isinstance(label, str) or not label.strip():
                    problems.append(f"decision.outputs[{oidx}].label must be a non-empty string")
                cs = out.get("code_system")
                if not isinstance(cs, str) or not cs.strip():
                    problems.append(
                        f"decision.outputs[{oidx}].code_system must be a non-empty string"
                    )
                role = out.get("role")
                if role not in OUTPUT_ROLES:
                    problems.append(
                        f"decision.outputs[{oidx}].role {role!r} not in {sorted(OUTPUT_ROLES)}"
                    )
                conf = out.get("confidence")
                if not _is_number(conf) or not (0.0 <= float(conf) <= 1.0):
                    problems.append(
                        f"decision.outputs[{oidx}].confidence must be a number in [0, 1]"
                    )
                cal = out.get("calibration")
                if cal is not None:
                    if not isinstance(cal, Mapping):
                        problems.append(
                            f"decision.outputs[{oidx}].calibration must be an object"
                        )
                    elif set(cal.keys()) - allow_cal:
                        problems.append(
                            f"decision.outputs[{oidx}].calibration has unexpected field(s)"
                        )
                frefs = out.get("facts_relied_upon")
                if (
                    not isinstance(frefs, Sequence)
                    or isinstance(frefs, (str, bytes))
                    or len(frefs) < 1
                ):
                    problems.append(
                        f"decision.outputs[{oidx}].facts_relied_upon must be a non-empty array"
                    )
                else:
                    for ridx, ref in enumerate(frefs):
                        if not isinstance(ref, Mapping):
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}] must be an object"
                            )
                            continue
                        if set(ref.keys()) - allow_fref:
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}] has unexpected field(s)"
                            )
                        rfid = str(ref.get("fact_id") or "")
                        if not FACT_ID_RE.fullmatch(rfid):
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}].fact_id {rfid!r} invalid"
                            )
                        elif rfid not in known_fact_ids:
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}].fact_id {rfid!r} not present in supporting_facts"
                            )
                        how = ref.get("how_it_contributed")
                        if not isinstance(how, str) or len(how.strip()) < 10:
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}].how_it_contributed must be >= 10 chars"
                            )
                        elif isinstance(label, str) and how.strip().lower() == label.strip().lower():
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}].how_it_contributed merely restates output label"
                            )
                        strength = ref.get("strength")
                        if strength is not None and strength not in FACT_STRENGTHS:
                            problems.append(
                                f"decision.outputs[{oidx}].facts_relied_upon[{ridx}].strength {strength!r} invalid"
                            )

    # 4. evidence
    evidence = record.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)) or len(evidence) < 1:
        problems.append("evidence must be a non-empty array of resolvable versioned citations")
    else:
        allow_ev = {
            "evidence_id",
            "kind",
            "identifier",
            "version_or_release",
            "jurisdiction",
            "retrieved_at",
            "supports",
            "research_framework_basis",
        }
        seen_ev_ids: set[str] = set()
        for eidx, ev in enumerate(evidence):
            if not isinstance(ev, Mapping):
                problems.append(f"evidence[{eidx}] must be an object")
                continue
            if set(ev.keys()) - allow_ev:
                problems.append(
                    f"evidence[{eidx}] has unexpected field(s): {sorted(set(ev.keys()) - allow_ev)}"
                )
            eid = str(ev.get("evidence_id") or "")
            if not EVIDENCE_ID_RE.fullmatch(eid):
                problems.append(
                    f"evidence[{eidx}].evidence_id {eid!r} must match {EVIDENCE_ID_RE.pattern}"
                )
            elif eid in seen_ev_ids:
                problems.append(f"duplicate evidence_id {eid!r}")
            else:
                seen_ev_ids.add(eid)
            ekind = ev.get("kind")
            if ekind not in EVIDENCE_KINDS:
                problems.append(
                    f"evidence[{eidx}].kind {ekind!r} not in {sorted(EVIDENCE_KINDS)}"
                )
            ident = str(ev.get("identifier") or "")
            if not _is_resolvable_identifier(ident):
                problems.append(
                    f"evidence[{eidx}].identifier {ident!r} is not a resolvable namespace/URI/DOI identifier"
                )
            ver = str(ev.get("version_or_release") or "").strip()
            if not ver:
                problems.append(
                    f"evidence[{eidx}].version_or_release must be a non-empty string"
                )
            basis = ev.get("research_framework_basis")
            if basis is not None:
                if not isinstance(basis, Sequence) or isinstance(basis, (str, bytes)):
                    problems.append(
                        f"evidence[{eidx}].research_framework_basis must be an array"
                    )
                else:
                    for bidx, item in enumerate(basis):
                        if not isinstance(item, Mapping):
                            problems.append(
                                f"evidence[{eidx}].research_framework_basis[{bidx}] must be an object"
                            )
                            continue
                        if item.get("framework") not in FRAMEWORKS:
                            problems.append(
                                f"evidence[{eidx}].research_framework_basis[{bidx}].framework invalid"
                            )
                        if not isinstance(item.get("principle"), str) or not item["principle"].strip():
                            problems.append(
                                f"evidence[{eidx}].research_framework_basis[{bidx}].principle required"
                            )

    # 5. uncertainty
    uncertainty = record.get("uncertainty")
    if not isinstance(uncertainty, Mapping):
        problems.append("uncertainty must be an object")
    else:
        allow_unc = {
            "statement",
            "missing_information",
            "conflicting_findings",
            "calibrated_confidence",
            "calibration_method",
            "calculation",
        }
        if set(uncertainty.keys()) - allow_unc:
            problems.append(
                f"uncertainty has unexpected field(s): {sorted(set(uncertainty.keys()) - allow_unc)}"
            )
        stmt = uncertainty.get("statement")
        if not isinstance(stmt, str) or not stmt.strip() or len(stmt) > 2000:
            problems.append("uncertainty.statement must be a non-empty string <= 2000 chars")
        missing_info = uncertainty.get("missing_information")
        if not isinstance(missing_info, Sequence) or isinstance(missing_info, (str, bytes)):
            problems.append("uncertainty.missing_information must be an array")
        else:
            allow_mi = {"what", "why_it_matters", "requested_from"}
            for midx, mi in enumerate(missing_info):
                if not isinstance(mi, Mapping):
                    problems.append(f"uncertainty.missing_information[{midx}] must be an object")
                    continue
                if set(mi.keys()) - allow_mi:
                    problems.append(
                        f"uncertainty.missing_information[{midx}] has unexpected field(s)"
                    )
                if not isinstance(mi.get("what"), str) or not mi["what"].strip():
                    problems.append(
                        f"uncertainty.missing_information[{midx}].what must be a non-empty string"
                    )
                if not isinstance(mi.get("why_it_matters"), str) or not mi["why_it_matters"].strip():
                    problems.append(
                        f"uncertainty.missing_information[{midx}].why_it_matters must be a non-empty string"
                    )
        conflicts = uncertainty.get("conflicting_findings")
        if conflicts is not None:
            if not isinstance(conflicts, Sequence) or isinstance(conflicts, (str, bytes)):
                problems.append("uncertainty.conflicting_findings must be an array")
            else:
                allow_cf = {"description", "direction", "fact_or_evidence_ref"}
                for cidx, cf in enumerate(conflicts):
                    if not isinstance(cf, Mapping):
                        problems.append(
                            f"uncertainty.conflicting_findings[{cidx}] must be an object"
                        )
                        continue
                    if set(cf.keys()) - allow_cf:
                        problems.append(
                            f"uncertainty.conflicting_findings[{cidx}] has unexpected field(s)"
                        )
                    if not isinstance(cf.get("description"), str) or not cf["description"].strip():
                        problems.append(
                            f"uncertainty.conflicting_findings[{cidx}].description required"
                        )
                    if cf.get("direction") not in CONFLICT_DIRECTIONS:
                        problems.append(
                            f"uncertainty.conflicting_findings[{cidx}].direction invalid"
                        )
        cconf = uncertainty.get("calibrated_confidence")
        if not _is_number(cconf) or not (0.0 <= float(cconf) <= 1.0):
            problems.append("uncertainty.calibrated_confidence must be a number in [0, 1]")
        cmethod = uncertainty.get("calibration_method")
        if cmethod not in CALIBRATION_METHODS:
            problems.append(
                f"uncertainty.calibration_method {cmethod!r} not in {sorted(CALIBRATION_METHODS)}"
            )
        calc = uncertainty.get("calculation")
        if calc is not None:
            if not isinstance(calc, Mapping):
                problems.append("uncertainty.calculation must be an object")
            else:
                allow_calc = {
                    "method",
                    "inputs_used",
                    "thresholds_applied",
                    "reproducible",
                    "verification_command",
                }
                if set(calc.keys()) - allow_calc:
                    problems.append("uncertainty.calculation has unexpected field(s)")
                if calc.get("method") not in CALCULATION_METHODS:
                    problems.append(
                        f"uncertainty.calculation.method {calc.get('method')!r} invalid"
                    )
                inputs_used = calc.get("inputs_used")
                if (
                    not isinstance(inputs_used, Sequence)
                    or isinstance(inputs_used, (str, bytes))
                    or len(inputs_used) < 1
                ):
                    problems.append(
                        "uncertainty.calculation.inputs_used must be a non-empty array"
                    )

    # 6. safety
    safety = record.get("safety")
    if not isinstance(safety, Mapping):
        problems.append("safety must be an object")
    else:
        allow_safety = {
            "contraindications_checked",
            "alerts",
            "requires_human_review",
            "review_role",
            "decision_status",
            "abstention",
            "safety_rule_hits",
        }
        if set(safety.keys()) - allow_safety:
            problems.append(
                f"safety has unexpected field(s): {sorted(set(safety.keys()) - allow_safety)}"
            )
        if not isinstance(safety.get("contraindications_checked"), bool):
            problems.append("safety.contraindications_checked must be a boolean")
        if not isinstance(safety.get("requires_human_review"), bool):
            problems.append("safety.requires_human_review must be a boolean")
        if "review_role" not in safety or (
            safety["review_role"] is not None
            and not isinstance(safety["review_role"], str)
        ):
            problems.append("safety.review_role must be a string or null")
        dstatus = safety.get("decision_status")
        if dstatus is not None and dstatus not in DECISION_STATUSES:
            problems.append(f"safety.decision_status {dstatus!r} invalid")
        alerts = safety.get("alerts")
        if not isinstance(alerts, Sequence) or isinstance(alerts, (str, bytes)):
            problems.append("safety.alerts must be an array")
        else:
            allow_alert = {"severity", "message", "rule_id"}
            for aidx, alert in enumerate(alerts):
                if not isinstance(alert, Mapping):
                    problems.append(f"safety.alerts[{aidx}] must be an object")
                    continue
                if set(alert.keys()) - allow_alert:
                    problems.append(f"safety.alerts[{aidx}] has unexpected field(s)")
                if alert.get("severity") not in ALERT_SEVERITIES:
                    problems.append(f"safety.alerts[{aidx}].severity invalid")
                if not isinstance(alert.get("message"), str) or not alert["message"].strip():
                    problems.append(f"safety.alerts[{aidx}].message required")
        abst = safety.get("abstention")
        if not isinstance(abst, Mapping):
            problems.append("safety.abstention must be an object")
        else:
            allow_abst = {"abstained", "reason_code", "minimum_confidence_threshold"}
            if set(abst.keys()) - allow_abst:
                problems.append("safety.abstention has unexpected field(s)")
            if not isinstance(abst.get("abstained"), bool):
                problems.append("safety.abstention.abstained must be a boolean")
            if "reason_code" not in abst or (
                abst["reason_code"] is not None
                and not isinstance(abst["reason_code"], str)
            ):
                problems.append("safety.abstention.reason_code must be string or null")

    # 7. provenance
    prov = record.get("provenance")
    if not isinstance(prov, Mapping):
        problems.append("provenance must be an object")
    else:
        allow_prov = {
            "model_or_component",
            "inputs",
            "prompt_identifier",
            "prompt_version",
            "code_change",
        }
        if set(prov.keys()) - allow_prov:
            problems.append(
                f"provenance has unexpected field(s): {sorted(set(prov.keys()) - allow_prov)}"
            )
        mc = prov.get("model_or_component")
        if not isinstance(mc, Mapping):
            problems.append("provenance.model_or_component must be an object")
        else:
            allow_mc = {"identifier", "version", "provider", "deployment_fingerprint"}
            if set(mc.keys()) - allow_mc:
                problems.append("provenance.model_or_component has unexpected field(s)")
            if not isinstance(mc.get("identifier"), str) or not mc["identifier"].strip():
                problems.append("provenance.model_or_component.identifier required")
            if not isinstance(mc.get("version"), str) or not mc["version"].strip():
                problems.append("provenance.model_or_component.version required")
        pinputs = prov.get("inputs")
        if (
            not isinstance(pinputs, Sequence)
            or isinstance(pinputs, (str, bytes))
            or len(pinputs) < 1
        ):
            problems.append("provenance.inputs must be a non-empty array")
        else:
            allow_pin = {"type", "identifier", "version_or_release", "tool"}
            for pidx, pin in enumerate(pinputs):
                if not isinstance(pin, Mapping):
                    problems.append(f"provenance.inputs[{pidx}] must be an object")
                    continue
                if set(pin.keys()) - allow_pin:
                    problems.append(f"provenance.inputs[{pidx}] has unexpected field(s)")
                if pin.get("type") not in PROVENANCE_INPUT_TYPES:
                    problems.append(f"provenance.inputs[{pidx}].type invalid")
                if not isinstance(pin.get("identifier"), str) or not pin["identifier"].strip():
                    problems.append(f"provenance.inputs[{pidx}].identifier required")
        cc = prov.get("code_change")
        if cc is not None:
            if not isinstance(cc, Mapping):
                problems.append("provenance.code_change must be an object")
            else:
                allow_cc = {
                    "repository",
                    "revision",
                    "revision_kind",
                    "revision_verified",
                }
                if set(cc.keys()) - allow_cc:
                    problems.append("provenance.code_change has unexpected field(s)")
                if not isinstance(cc.get("repository"), str) or not cc["repository"].strip():
                    problems.append("provenance.code_change.repository required")
                if not isinstance(cc.get("revision"), str) or not cc["revision"].strip():
                    problems.append("provenance.code_change.revision required")
                rk = cc.get("revision_kind")
                if rk is not None and rk not in REVISION_KINDS:
                    problems.append("provenance.code_change.revision_kind invalid")

    # 8. audit
    audit = record.get("audit")
    if not isinstance(audit, Mapping):
        problems.append("audit must be an object")
    else:
        allow_audit = {
            "audit_reference",
            "persisted",
            "resolved_in_audit_store",
            "tenant_scope",
            "clinician_action",
        }
        if set(audit.keys()) - allow_audit:
            problems.append(
                f"audit has unexpected field(s): {sorted(set(audit.keys()) - allow_audit)}"
            )
        if not isinstance(audit.get("audit_reference"), str) or not audit["audit_reference"].strip():
            problems.append("audit.audit_reference must be a non-empty string")
        if not isinstance(audit.get("persisted"), bool):
            problems.append("audit.persisted must be a boolean")
        ts = audit.get("tenant_scope")
        if not isinstance(ts, Mapping):
            problems.append("audit.tenant_scope must be an object")
        else:
            allow_ts = {"patient_scope", "facility_scope", "purpose_of_use"}
            if set(ts.keys()) - allow_ts:
                problems.append("audit.tenant_scope has unexpected field(s)")
            if not isinstance(ts.get("patient_scope"), str) or not ts["patient_scope"].strip():
                problems.append("audit.tenant_scope.patient_scope required")
            if not isinstance(ts.get("facility_scope"), str) or not ts["facility_scope"].strip():
                problems.append("audit.tenant_scope.facility_scope required")
        ca = audit.get("clinician_action")
        if ca is not None:
            if not isinstance(ca, Mapping):
                problems.append("audit.clinician_action must be an object")
            else:
                allow_ca = {"action", "acted_at", "accountable_clinician"}
                if set(ca.keys()) - allow_ca:
                    problems.append("audit.clinician_action has unexpected field(s)")
                act = ca.get("action")
                if act is not None and act not in CLINICIAN_ACTIONS:
                    problems.append(f"audit.clinician_action.action {act!r} invalid")

    return problems


def assert_valid_clinical_decision_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate ``record`` and raise ``ClinicalDecisionRecordError`` if any check fails."""
    problems = validate_clinical_decision_record(record)
    if problems:
        raise ClinicalDecisionRecordError(
            "Invalid Clinical Decision Record:\n- " + "\n- ".join(problems)
        )
    return dict(record)


class ClinicalDecisionRecordBuilder:
    """Fluent and functional builder for a schema-valid Clinical Decision Record."""

    def __init__(
        self,
        *,
        agent: CdrAgent | Mapping[str, Any],
        decision: CdrDecision | Mapping[str, Any],
        supporting_facts: Sequence[CdrSupportingFact | Mapping[str, Any]],
        evidence: Sequence[CdrEvidenceItem | Mapping[str, Any]],
        uncertainty: CdrUncertainty | Mapping[str, Any],
        safety: CdrSafety | Mapping[str, Any],
        provenance: CdrProvenance | Mapping[str, Any],
        audit: CdrAudit | Mapping[str, Any],
        record_id: str | None = None,
        recorded_at: str | None = None,
    ) -> None:
        self.agent = agent
        self.decision = decision
        self.supporting_facts = supporting_facts
        self.evidence = evidence
        self.uncertainty = uncertainty
        self.safety = safety
        self.provenance = provenance
        self.audit = audit
        self.record_id = record_id
        self.recorded_at = recorded_at

    def build(self) -> dict[str, Any]:
        agent_dict = (
            self.agent.to_dict()
            if isinstance(self.agent, CdrAgent)
            else dict(self.agent)
        )
        decision_dict = (
            self.decision.to_dict()
            if isinstance(self.decision, CdrDecision)
            else dict(self.decision)
        )
        facts_list = [
            f.to_dict() if isinstance(f, CdrSupportingFact) else dict(f)
            for f in self.supporting_facts
        ]
        evidence_list = [
            e.to_dict() if isinstance(e, CdrEvidenceItem) else dict(e)
            for e in self.evidence
        ]
        uncertainty_dict = (
            self.uncertainty.to_dict()
            if isinstance(self.uncertainty, CdrUncertainty)
            else dict(self.uncertainty)
        )
        safety_dict = (
            self.safety.to_dict()
            if isinstance(self.safety, CdrSafety)
            else dict(self.safety)
        )
        prov_dict = (
            self.provenance.to_dict()
            if isinstance(self.provenance, CdrProvenance)
            else dict(self.provenance)
        )
        audit_dict = (
            self.audit.to_dict()
            if isinstance(self.audit, CdrAudit)
            else dict(self.audit)
        )

        rec_id = self.record_id or deterministic_cdr_id(
            agent_dict.get("gharra_agent_id", ""),
            decision_dict.get("kind", ""),
            audit_dict.get("audit_reference", ""),
            decision_dict.get("summary", ""),
        )
        rec_at = self.recorded_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")

        record: dict[str, Any] = {
            "schema_version": CDR_SCHEMA_VERSION,
            "record_id": rec_id,
            "recorded_at": rec_at,
            "agent": agent_dict,
            "decision": decision_dict,
            "supporting_facts": facts_list,
            "evidence": evidence_list,
            "uncertainty": uncertainty_dict,
            "safety": safety_dict,
            "provenance": prov_dict,
            "audit": audit_dict,
        }
        return assert_valid_clinical_decision_record(record)


def build_clinical_decision_record(
    *,
    agent: CdrAgent | Mapping[str, Any],
    decision: CdrDecision | Mapping[str, Any],
    supporting_facts: Sequence[CdrSupportingFact | Mapping[str, Any]],
    evidence: Sequence[CdrEvidenceItem | Mapping[str, Any]],
    uncertainty: CdrUncertainty | Mapping[str, Any],
    safety: CdrSafety | Mapping[str, Any],
    provenance: CdrProvenance | Mapping[str, Any],
    audit: CdrAudit | Mapping[str, Any],
    record_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build and validate a canonical Clinical Decision Record."""
    return ClinicalDecisionRecordBuilder(
        agent=agent,
        decision=decision,
        supporting_facts=supporting_facts,
        evidence=evidence,
        uncertainty=uncertainty,
        safety=safety,
        provenance=provenance,
        audit=audit,
        record_id=record_id,
        recorded_at=recorded_at,
    ).build()


def mask_clinical_decision_record(
    record: Mapping[str, Any],
    *,
    role_profile: str = "clinician",
    mask_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Return a role-masked copy of ``record`` that remains schema-conformant.

    - ``clinician`` and ``admin`` receive the curated record with free-text patient
      identifiers masked via ``mask_fn`` (defaulting to ``default_mask_pii``).
    - ``clinician`` omits internal deployment fingerprints while retaining model,
      prompt, and code revision provenance.
    - ``developer`` preserves full provenance metadata (with free-text identifiers
      still masked by default).
    - Structural IDs (`record_id`, `fact_id`, `evidence_id`, `schema_version`,
      timestamps, and citation DOIs/URIs) remain intact so the masked record
      validates cleanly against ``clinical-decision-record.schema.json``.
    """
    masker = mask_fn or default_mask_pii
    cloned = copy.deepcopy(dict(record))

    decision = cloned.get("decision")
    if isinstance(decision, dict):
        if isinstance(decision.get("summary"), str):
            decision["summary"] = masker(decision["summary"])
        for out in decision.get("outputs", []):
            if isinstance(out, dict):
                if isinstance(out.get("label"), str):
                    out["label"] = masker(out["label"])
                for ref in out.get("facts_relied_upon", []):
                    if isinstance(ref, dict) and isinstance(
                        ref.get("how_it_contributed"), str
                    ):
                        ref["how_it_contributed"] = masker(ref["how_it_contributed"])

    for fact in cloned.get("supporting_facts", []):
        if isinstance(fact, dict):
            if isinstance(fact.get("value"), str):
                fact["value"] = masker(fact["value"])
            src = fact.get("source")
            if isinstance(src, dict) and isinstance(src.get("source_record_id"), str):
                src["source_record_id"] = masker(src["source_record_id"])

    uncertainty = cloned.get("uncertainty")
    if isinstance(uncertainty, dict):
        if isinstance(uncertainty.get("statement"), str):
            uncertainty["statement"] = masker(uncertainty["statement"])
        for mi in uncertainty.get("missing_information", []):
            if isinstance(mi, dict):
                if isinstance(mi.get("what"), str):
                    mi["what"] = masker(mi["what"])
                if isinstance(mi.get("why_it_matters"), str):
                    mi["why_it_matters"] = masker(mi["why_it_matters"])
        for cf in uncertainty.get("conflicting_findings", []) or []:
            if isinstance(cf, dict) and isinstance(cf.get("description"), str):
                cf["description"] = masker(cf["description"])

    safety = cloned.get("safety")
    if isinstance(safety, dict):
        for alert in safety.get("alerts", []):
            if isinstance(alert, dict) and isinstance(alert.get("message"), str):
                alert["message"] = masker(alert["message"])

    audit = cloned.get("audit")
    if isinstance(audit, dict):
        ts = audit.get("tenant_scope")
        if isinstance(ts, dict) and isinstance(ts.get("patient_scope"), str):
            ts["patient_scope"] = masker(ts["patient_scope"])

    prov = cloned.get("provenance")
    if isinstance(prov, dict) and role_profile in {"clinician", "patient"}:
        mc = prov.get("model_or_component")
        if isinstance(mc, dict):
            mc.pop("deployment_fingerprint", None)

    return assert_valid_clinical_decision_record(cloned)


__all__ = [
    "CDR_SCHEMA_ID",
    "CDR_SCHEMA_VERSION",
    "CdrAbstention",
    "CdrAgent",
    "CdrAudit",
    "CdrCalculation",
    "CdrCalculationInput",
    "CdrCalculationThreshold",
    "CdrCalibration",
    "CdrClinicianAction",
    "CdrCodeChange",
    "CdrConflictingFinding",
    "CdrDecision",
    "CdrDecisionOutput",
    "CdrEvidenceItem",
    "CdrFactReference",
    "CdrFactSource",
    "CdrFrameworkBasis",
    "CdrMissingInfo",
    "CdrModelOrComponent",
    "CdrProvenance",
    "CdrProvenanceInput",
    "CdrSafety",
    "CdrSafetyAlert",
    "CdrSupportingFact",
    "CdrTenantScope",
    "CdrUncertainty",
    "ClinicalDecisionRecordBuilder",
    "ClinicalDecisionRecordError",
    "assert_valid_clinical_decision_record",
    "build_clinical_decision_record",
    "default_cdr_schema_path",
    "default_mask_pii",
    "deterministic_cdr_id",
    "load_cdr_schema",
    "mask_clinical_decision_record",
    "resolve_repo_code_change",
    "validate_clinical_decision_record",
]
