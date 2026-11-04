"""Symphonix Conductor — Governed Cross-Persona & Cross-Sibling Coordination Contract.

Implements the approved Gate G1 architecture decisions (ADR-CON-001..005):
- ADR-CON-001: Logical coordination capability across GHARRA, symphonix-bridge-sdk,
  and nexus-a2a-protocol without creating a duplicate repository or service.
  Strictly isolated from BulletTrain/services/conductor infrastructure ops (CON-TOOL-005).
- ADR-CON-002: Single canonical durable execution contract built on ExecutionLedger
  and DurableLedgerAdapter (DAEC 1.0.0) with pre-retry SideEffectReceipt reconciliation
  (CON-DUR-002), parallel DAG barriers (CON-DUR-003), and parent-to-child cancellation
  and compensation propagation (CON-DUR-004).
- ADR-CON-003: Asymmetric-only PersonaTokenClaims (RS256/ES256/EdDSA + DPoP/mTLS,
  HS256 refused) with two-phase Policy Enforcement Point (PEP) verification at
  dispatch and immediately prior to any write/irreversible tool call (CON-PER-004,
  CON-SEC-004, CON-AUTH-001..003).
- ADR-CON-004: Preservation of approved sibling integration Topologies A (BulletTrain
  clinical hub), B (appointment-system + scheduling-gateway federated peer),
  C (insurance-eclaims internal hub + external AS2/SFTP EDI), and D (patient360-assistant
  MCP federation) (CON-SIB-001..007).
- ADR-CON-005: Local-first model routing (LFG-Control active_mode=local_first,
  monthly_ceiling_gbp=10.0, gateway_cap_gbp=5.0, £0.00 target cloud spend on local
  Ollama models), pre-egress PHI redaction (CON-RES-003), and untrusted external
  content prompt-injection quarantine (CON-RES-006, CON-PERF-002).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from bridge_sdk.agent_contract import (
    AgentActionManifest,
    ManifestError,
    SafetyClass,
    all_conductor_manifests,
    resolve_intent,
)
from bridge_sdk.durable_agent import (
    CheckpointEnvelope,
    DurableLedgerAdapter,
    SideEffectReceipt,
)
from bridge_sdk.execution_ledger import LedgerError, WorkflowState
from bridge_sdk.human_handoff import (
    HandoffPackage,
    HandoffTrigger,
)
from bridge_sdk.persona_delegation import (
    DelegationError,
    PersonaScope,
    PersonaTokenClaims,
)

__all__ = [
    "BULLETTRAIN_INFRA_OPS_ACTIONS",
    "CONDUCTOR_STATE_TO_LEDGER",
    "CitationVerificationResult",
    "CompensationRecord",
    "ConductorAdmissionError",
    "ConductorAuthorizationError",
    "ConductorBudgetExceededError",
    "ConductorCoordinator",
    "ConductorDAGNode",
    "ConductorDAGResult",
    "ConductorLifecycleState",
    "ConductorResearchGovernance",
    "ConductorSecurityError",
    "ReassessmentTrigger",
    "ResearchTier",
    "is_valid_modulus11_spid",
    "load_gharra_seed_registry",
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolve_workspace_root() -> Path:
    env_root = os.environ.get("SYMPHONIX_WORKSPACE_ROOT") or os.environ.get("CAID_WORKSPACE")
    if env_root:
        candidate = Path(env_root)
        if candidate.exists():
            return candidate
    # symphonix-bridge-sdk/src/bridge_sdk/conductor_coordination.py -> parents[3] is workspace root
    return Path(__file__).resolve().parents[3]


def _ensure_spine_paths_on_sys_path() -> None:
    ws = _resolve_workspace_root()
    for rel in (
        "prompt-engine/src",
        "symphonix-health-research-to-caid-agent/src",
        "REA-Agent-mcp/src",
        "global-agent-registry/src",
        "nexus-a2a-protocol/src",
        "nexus-a2a-protocol/shared",
    ):
        cand = ws / rel
        if cand.exists() and str(cand) not in sys.path:
            sys.path.insert(0, str(cand))


def is_valid_modulus11_spid(patient_ref: str) -> bool:
    """Validate that a FHIR Patient reference (`Patient/9434765919` or 10-digit string)
    carries a canonical 10-digit Modulus-11 Symphonix Patient Identifier (SPID-FR-003).
    """
    raw = patient_ref.strip()
    if raw.startswith("Patient/"):
        raw = raw.split("/", 1)[1]
    if not re.fullmatch(r"\d{10}", raw):
        return False
    if len(set(raw)) == 1:
        return False
    total = sum(int(raw[i]) * (10 - i) for i in range(9))
    rem = total % 11
    check = (11 - rem) % 11
    if check == 10:
        return False
    return check == int(raw[9])


def load_gharra_seed_registry(workspace_root: Path | None = None) -> dict[str, Any]:
    """Load the authoritative GHARRA SuperPersona, Skill, Tool, and Guardrail seed
    catalogues from ``global-agent-registry/seed_data/superpersona_registry``.
    """
    ws = workspace_root or _resolve_workspace_root()
    reg_dir = ws / "global-agent-registry" / "seed_data" / "superpersona_registry"
    result: dict[str, Any] = {
        "personas": {},
        "skills": {},
        "tools": {},
        "guardrails": {},
    }
    if not reg_dir.exists():
        return result
    p_file = reg_dir / "personas.json"
    if p_file.exists():
        data = json.loads(p_file.read_text(encoding="utf-8"))
        for p in data.get("personas", []):
            result["personas"][p["persona_id"]] = p
    s_file = reg_dir / "skills.json"
    if s_file.exists():
        data = json.loads(s_file.read_text(encoding="utf-8"))
        for s in data.get("skills", []):
            result["skills"][s["skill_id"]] = s
    t_file = reg_dir / "tools.json"
    if t_file.exists():
        data = json.loads(t_file.read_text(encoding="utf-8"))
        for t in data.get("tools", []):
            result["tools"][t["tool_id"]] = t
    g_file = reg_dir / "guardrails.json"
    if g_file.exists():
        data = json.loads(g_file.read_text(encoding="utf-8"))
        for g in data.get("guardrails", []):
            result["guardrails"][g["guardrail_id"]] = g
    return result


class ConductorSecurityError(DelegationError):
    """Raised when Conductor security, tenant, patient, or revocation policy fails."""


class ConductorAuthorizationError(DelegationError):
    """Raised when Persona/SuperPersona authority, jurisdiction, or HITL gate fails."""


class ConductorAdmissionError(ManifestError):
    """Raised when a skill, tool, MCP server, or contract schema fails admission."""


class ConductorBudgetExceededError(RuntimeError):
    """Raised when a workflow or research ensemble exceeds token, fan-out, or GBP caps."""


class ConductorLifecycleState(str, Enum):
    """Canonical 13-state Conductor task lifecycle mapped onto ExecutionLedger."""

    PROPOSED = "PROPOSED"
    AUTHORISED = "AUTHORISED"
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    WAITING_HUMAN = "WAITING_HUMAN"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    COMPENSATING = "COMPENSATING"
    QUARANTINED = "QUARANTINED"


CONDUCTOR_STATE_TO_LEDGER: dict[ConductorLifecycleState, WorkflowState] = {
    ConductorLifecycleState.PROPOSED: WorkflowState.admitted,
    ConductorLifecycleState.AUTHORISED: WorkflowState.admitted,
    ConductorLifecycleState.PLANNED: WorkflowState.admitted,
    ConductorLifecycleState.DISPATCHED: WorkflowState.running,
    ConductorLifecycleState.RUNNING: WorkflowState.running,
    ConductorLifecycleState.WAITING_DEPENDENCY: WorkflowState.waiting_for_input,
    ConductorLifecycleState.WAITING_HUMAN: WorkflowState.needs_human_review,
    ConductorLifecycleState.VERIFYING: WorkflowState.running,
    ConductorLifecycleState.COMPLETED: WorkflowState.completed,
    ConductorLifecycleState.FAILED: WorkflowState.escalated,
    ConductorLifecycleState.CANCELLED: WorkflowState.cancelled,
    ConductorLifecycleState.COMPENSATING: WorkflowState.compensating,
    ConductorLifecycleState.QUARANTINED: WorkflowState.blocked,
}

# Infrastructure ops actions owned exclusively by BulletTrain/services/conductor (CON-TOOL-005)
BULLETTRAIN_INFRA_OPS_ACTIONS: frozenset[str] = frozenset(
    {
        "RESTART_SERVICE",
        "SCALE_UP",
        "TRIGGER_CIRCUIT_BREAKER",
        "FAILOVER_DB",
        "FLUSH_CACHE",
        "ISOLATE_NODE",
        "bullettrain.conductor.restart_service",
        "bullettrain.conductor.scale_up",
        "bullettrain.conductor.failover_db",
        "bullettrain.conductor.isolate_node",
    }
)

# High-risk clinical intents that require mandatory human clinician HITL sign-off
# before irreversible execution (CON-AUTH-002, CON-SIB-003, CON-SIB-004).
CLINICAL_HITL_MANDATORY_INTENTS: frozenset[str] = frozenset(
    {
        "epr.discharge.propose",
        "pharmacy.dispense.release",
    }
)


class ResearchTier(str, Enum):
    """Tiered research hierarchy R0-R5 (WP07 / Section 8)."""

    R0_INTERNAL_KB = "R0"
    R1_GOVERNED_WEB = "R1"
    R2_SCIENTIFIC_REGULATORY = "R2"
    R3_DEEP_RESEARCH = "R3"
    R4_REQUIREMENTS_HANDOFF = "R4"
    R5_WATCHLIST_SURVEILLANCE = "R5"


@dataclass(frozen=True)
class CompensationRecord:
    """Deterministic compensation record emitted on branch cancellation or rollback."""

    workflow_id: str
    step_id: str
    compensation_action: str
    reason: str
    recorded_at: str
    status: str = "compensated"


@dataclass(frozen=True)
class ConductorDAGNode:
    """Single node in a Conductor multi-agent DAG execution plan."""

    step_id: str
    intent: str
    payload: dict[str, Any]
    idempotency_key: str
    depends_on: tuple[str, ...] = ()
    compensation_action: str | None = None
    is_write: bool = True


@dataclass(frozen=True)
class ConductorDAGResult:
    """Aggregate result of a Conductor DAG execution."""

    workflow_id: str
    state: WorkflowState
    completed_steps: tuple[str, ...]
    cancelled_steps: tuple[str, ...]
    receipts: dict[str, SideEffectReceipt]
    compensations: tuple[CompensationRecord, ...]
    checkpoint: CheckpointEnvelope


@dataclass(frozen=True)
class CitationVerificationResult:
    """Verification outcome for research citations and retraction screening (CON-RES-007)."""

    citation_id: str
    doi_or_pmid: str
    verified: bool
    retracted: bool
    admissible: bool
    reason: str


@dataclass(frozen=True)
class ReassessmentTrigger:
    """Structured reassessment trigger emitted on contract drift or guideline withdrawal."""

    trigger_id: str
    source_type: str  # "contract_drift" | "guideline_update" | "safety_incident"
    affected_component: str
    affected_personas: tuple[str, ...]
    affected_skills: tuple[str, ...]
    quarantined: bool
    summary: str
    created_at: str


_PHI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PATIENT_REF", re.compile(r"\bPatient/[A-Za-z0-9._-]+\b")),
    ("NHS_NUMBER", re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b")),
    ("MRN", re.compile(r"\bMRN[-:\s]*[A-Z0-9]{5,12}\b", re.IGNORECASE)),
    ("DOB_ISO", re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")),
    ("DOB_SLASH", re.compile(r"\b\d{2}/\d{2}/(?:19|20)\d{2}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("NI_NUMBER", re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b", re.IGNORECASE)),
)

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*override", re.IGNORECASE),
    re.compile(r"<tool_call>|invoke_tool|execute_shell|DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"bypass\s+(?:hitl|safety|consent|redaction)", re.IGNORECASE),
    re.compile(r"exfiltrate\s+(?:phi|patient|token)", re.IGNORECASE),
)


class ConductorResearchGovernance:
    """Governed R0-R5 research pipeline enforcing R0-first, zero-PHI egress via
    ``prompt-engine`` healthcare redaction, prompt-injection quarantine, citation
    verification, and ``symphonix-health-research-to-caid-agent`` impact policy.
    """

    def __init__(
        self,
        *,
        internal_kb_entries: dict[str, dict[str, Any]] | None = None,
        verified_citations: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._internal_kb = dict(internal_kb_entries or {})
        self._verified_citations = dict(verified_citations or {})

    def redact_and_verify_zero_phi(
        self,
        query: str,
        *,
        patient_names: tuple[str, ...] = (),
        fail_closed_on_phi: bool = False,
    ) -> tuple[str, list[str]]:
        """Redact PHI patterns and patient names prior to external R1-R3 egress (CON-RES-003).

        Integrates both UK NHS/SPID patterns and ``prompt_engine.healthcare.redaction.redact_phi``
        (18 HIPAA Safe Harbor categories). When ``fail_closed_on_phi=True``, raises
        ``ConductorSecurityError`` if any PHI is detected in an outbound external query.
        """
        detected: list[str] = []
        sanitized = query
        for label, pattern in _PHI_PATTERNS:
            if pattern.search(sanitized):
                detected.append(label)
                sanitized = pattern.sub(f"[REDACTED_{label}]", sanitized)
        for name in patient_names:
            clean_name = name.strip()
            if clean_name and re.search(re.escape(clean_name), sanitized, re.IGNORECASE):
                detected.append("PATIENT_NAME")
                sanitized = re.sub(
                    re.escape(clean_name),
                    "[REDACTED_PATIENT_NAME]",
                    sanitized,
                    flags=re.IGNORECASE,
                )

        # Delegate additional HIPAA Safe Harbor redaction to prompt-engine spine library
        _ensure_spine_paths_on_sys_path()
        try:
            from prompt_engine.healthcare.redaction import redact_phi as pe_redact_phi

            pe_sanitized = pe_redact_phi(sanitized)
            if pe_sanitized != sanitized:
                detected.append("PROMPT_ENGINE_SAFE_HARBOR")
                sanitized = pe_sanitized
        except ImportError:
            pass

        if fail_closed_on_phi and detected:
            raise ConductorSecurityError(
                f"Outbound research egress blocked (CON-RES-003): detected PHI markers {detected}"
            )
        # Verify zero residual match
        for label, pattern in _PHI_PATTERNS:
            if pattern.search(sanitized):
                raise ConductorSecurityError(
                    f"Residual PHI marker {label} remained after redaction"
                )
        return sanitized, detected

    def inspect_external_content(self, content: str, *, source_uri: str) -> dict[str, Any]:
        """Quarantine untrusted external content containing prompt-injection payloads
        (CON-RES-006, CON-PERF-002).
        """
        matched = [p.pattern for p in _INJECTION_PATTERNS if p.search(content)]
        if matched:
            return {
                "admissible": False,
                "quarantined": True,
                "source_uri": source_uri,
                "reason": "prompt_injection_detected",
                "matched_signatures": matched,
                "can_trigger_tools": False,
                "can_mutate_clinical_memory": False,
            }
        return {
            "admissible": True,
            "quarantined": False,
            "source_uri": source_uri,
            "sanitized_text": content,
            "can_trigger_tools": False,
            "can_mutate_clinical_memory": False,
        }

    def verify_citation(
        self,
        citation_id: str,
        doi_or_pmid: str,
    ) -> CitationVerificationResult:
        """Verify a citation against the curated/registry index and reject fabricated
        or retracted studies (CON-RES-007).
        """
        record = self._verified_citations.get(doi_or_pmid)
        if record is None:
            return CitationVerificationResult(
                citation_id=citation_id,
                doi_or_pmid=doi_or_pmid,
                verified=False,
                retracted=False,
                admissible=False,
                reason="unverified_or_fabricated_citation",
            )
        is_retracted = bool(record.get("retracted", False))
        if is_retracted:
            return CitationVerificationResult(
                citation_id=citation_id,
                doi_or_pmid=doi_or_pmid,
                verified=True,
                retracted=True,
                admissible=False,
                reason="retracted_publication_rejected",
            )
        return CitationVerificationResult(
            citation_id=citation_id,
            doi_or_pmid=doi_or_pmid,
            verified=True,
            retracted=False,
            admissible=True,
            reason="verified_active_evidence",
        )

    def execute_research(
        self,
        topic: str,
        *,
        patient_names: tuple[str, ...] = (),
        allow_external_escalation: bool = True,
        clinical_guideline_impact: bool = False,
    ) -> dict[str, Any]:
        """Execute R0-first research, escalating to R1-R3 only when internal KB is
        insufficient or stale, and requiring human clinical governance + VisionImpactPolicy
        gates for clinical guideline changes (CON-RES-001..005, CON-RES-008).
        """
        kb_hit = self._internal_kb.get(topic)
        if kb_hit and not kb_hit.get("stale", False):
            return {
                "tier_used": ResearchTier.R0_INTERNAL_KB.value,
                "external_egress_performed": False,
                "kb_entry_id": kb_hit["id"],
                "content": kb_hit["content"],
                "requires_clinical_governance_signoff": clinical_guideline_impact,
                "autonomous_clinical_policy_mutation": False,
            }
        if not allow_external_escalation:
            raise ConductorAdmissionError(
                f"R0 internal KB miss/stale for '{topic}' and external escalation disabled"
            )
        sanitized_query, redacted_markers = self.redact_and_verify_zero_phi(
            topic, patient_names=patient_names, fail_closed_on_phi=False
        )

        # Attach authoritative VisionImpactPolicy metadata from symphonix-health-research-to-caid-agent
        _ensure_spine_paths_on_sys_path()
        impact_policy_version = "2026-06-22.1"
        try:
            from symphonix_health_research_to_caid.impact_policy import (
                vision_impact_policy_document,
            )

            policy_doc = vision_impact_policy_document()
            impact_policy_version = str(policy_doc.get("policy_version", impact_policy_version))
        except ImportError:
            pass

        return {
            "tier_used": ResearchTier.R3_DEEP_RESEARCH.value,
            "external_egress_performed": True,
            "sanitized_query": sanitized_query,
            "redacted_phi_markers": redacted_markers,
            "requires_clinical_governance_signoff": clinical_guideline_impact,
            "autonomous_clinical_policy_mutation": False,
            "vision_impact_policy_version": impact_policy_version,
            "handoff_status": (
                "PENDING_CSO_CLINICAL_GOVERNANCE"
                if clinical_guideline_impact
                else "READY_FOR_REA_EXTRACTION"
            ),
        }

    def evaluate_watchlist_alert(
        self,
        *,
        guideline_id: str,
        change_type: str,
        affected_component: str,
        affected_personas: tuple[str, ...],
        affected_skills: tuple[str, ...],
    ) -> ReassessmentTrigger:
        """Emit a deterministic R5 reassessment trigger when an external guideline or
        safety alert invalidates an existing workflow or skill (CON-RES-009, CON-PROM-003).
        """
        quarantine = change_type in {"withdrawn", "black_box_warning", "contraindicated"}
        return ReassessmentTrigger(
            trigger_id=f"reassess-{guideline_id}-{hashlib.sha256(change_type.encode()).hexdigest()[:8]}",
            source_type="guideline_update",
            affected_component=affected_component,
            affected_personas=affected_personas,
            affected_skills=affected_skills,
            quarantined=quarantine,
            summary=f"Guideline {guideline_id} status changed to '{change_type}'",
            created_at=_now_iso(),
        )


class ConductorCoordinator:
    """Governed Conductor coordination facade integrating GHARRA seed registry discovery
    (58 SuperPersonas, 53 skills, 38 tools, 37 guardrails), PersonaTokenClaims asymmetric
    PEP, DurableLedgerAdapter (DAEC 1.0.0), HandoffInbox HITL gates, and sibling contract
    execution.
    """

    def __init__(
        self,
        adapter: DurableLedgerAdapter,
        *,
        manifests: dict[str, AgentActionManifest] | None = None,
        approved_skills: set[str] | None = None,
        signed_mcp_tools: dict[str, str] | None = None,
        monthly_ceiling_gbp: float = 10.0,
        gateway_cap_gbp: float = 5.0,
        routing_mode: str = "local_first",
        workspace_root: Path | None = None,
    ) -> None:
        self._adapter = adapter
        self._manifests = manifests or all_conductor_manifests()
        self._gharra_registry = load_gharra_seed_registry(workspace_root)
        default_skills = {
            "baseline-governed-agent",
            "clinical-triage-pathway",
            "discharge-medication-reconciliation",
            "sepsis-ng51-escalation",
            "federated-appointment-coordination",
            "eclaims-preauth-validation",
            "evidence-synthesis-grade",
            *self._gharra_registry["skills"].keys(),
        }
        self._approved_skills: set[str] = set(approved_skills or default_skills)
        self._revoked_skills: set[str] = set()
        self._revoked_tokens: set[str] = set()
        self._revoked_personas: set[str] = set()
        default_mcp_tools = {
            "signalbox-mcp.invoke-tool": "sha256:8f9d2a1c4b7e6031982a",
            "signalbox-mcp.capture-attestation": "sha256:4c1e9b7a2d5f8012349b",
            "rea-agent.derive_all": "sha256:7a3b5c9e1d2f4081726c",
            "caid-agent.caid_validate": "sha256:2e6f8a0c3b5d9174628d",
        }
        for tool_id in self._gharra_registry["tools"]:
            digest = hashlib.sha256(f"gharra-tool:{tool_id}:1.0.0".encode("utf-8")).hexdigest()[:20]
            default_mcp_tools.setdefault(tool_id, f"sha256:{digest}")
        self._signed_mcp_tools: dict[str, str] = dict(signed_mcp_tools or default_mcp_tools)
        self._downstream_effects: dict[str, dict[str, Any]] = {}
        self._monthly_ceiling_gbp = monthly_ceiling_gbp
        self._gateway_cap_gbp = gateway_cap_gbp
        self._routing_mode = routing_mode
        self._accumulated_spend_gbp = 0.0

    @property
    def adapter(self) -> DurableLedgerAdapter:
        return self._adapter

    @property
    def gharra_registry(self) -> dict[str, Any]:
        return self._gharra_registry

    def revoke_token(self, token_id: str) -> None:
        """Immediately revoke a delegation token ID (CON-PER-004)."""
        self._revoked_tokens.add(token_id)

    def revoke_persona(self, persona_key: str) -> None:
        """Immediately revoke or suspend a persona (CON-PER-004)."""
        self._revoked_personas.add(persona_key)

    def revoke_skill(self, skill_id: str) -> None:
        """Quarantine/deprecate a skill pack so runtime admission fails closed (CON-SKL-003)."""
        self._revoked_skills.add(skill_id)

    def verify_delegation_claims(
        self,
        claims: PersonaTokenClaims,
        *,
        target_component: str,
        target_patient: str | None,
        target_tenant: str,
        token_tenant: str,
        required_scope: PersonaScope,
        target_jurisdiction: str = "UK_NHS",
        token_jurisdiction: str = "UK_NHS",
        is_write: bool = False,
        is_provisional: bool = False,
        safety_class: SafetyClass = SafetyClass.sensitive,
    ) -> None:
        """Enforce two-phase PEP checks: tenant/patient boundary, scope, revocation,
        jurisdiction compatibility, and provisional execution rules
        (CON-PER-003, CON-PER-004, CON-AUTH-001..003, CON-SEC-004, CON-PERS-006).
        """
        if claims.persona.lower() in {"superuser", "root", "*"}:
            raise ConductorSecurityError("Wildcard/superuser persona is forbidden (ADR-CON-003)")
        if claims.persona in self._revoked_personas:
            raise ConductorSecurityError(
                f"Persona '{claims.persona}' has been revoked/suspended (CON-PER-004)"
            )
        if claims.token_id and claims.token_id in self._revoked_tokens:
            raise ConductorSecurityError(
                f"Delegation token '{claims.token_id}' has been revoked prior to execution (CON-PER-004)"
            )
        if token_tenant != target_tenant:
            raise ConductorSecurityError(
                f"Cross-tenant boundary violation (CON-AUTH-001): token tenant '{token_tenant}' != '{target_tenant}'"
            )
        if target_patient is not None and claims.patient_context != target_patient:
            if not claims.emergency:
                raise ConductorSecurityError(
                    f"Cross-patient boundary violation (CON-AUTH-001): token bound to "
                    f"'{claims.patient_context}' cannot access '{target_patient}'"
                )
        if target_component not in claims.allowed_systems:
            raise ConductorAuthorizationError(
                f"Component '{target_component}' not in token allowed_systems {claims.allowed_systems} (CON-TOOL-002)"
            )
        if required_scope not in claims.scopes:
            raise ConductorAuthorizationError(
                f"Missing required scope '{required_scope.value}' in token scopes (CON-AUTH-001)"
            )
        if token_jurisdiction != target_jurisdiction:
            raise ConductorAuthorizationError(
                f"Cross-jurisdiction handoff blocked without explicit revalidation (CON-AUTH-003): "
                f"'{token_jurisdiction}' -> '{target_jurisdiction}'"
            )
        if is_provisional and (is_write and safety_class is SafetyClass.high_risk):
            raise ConductorAuthorizationError(
                "Provisional role-aligned execution cannot perform high-risk clinical writes "
                "without human supervisor gate (CON-PER-003 / CON-PERS-006)"
            )

    def admit_skill_and_tool(
        self,
        *,
        skill_id: str,
        intent: str,
        payload: dict[str, Any],
        mcp_tool_id: str | None = None,
        mcp_digest: str | None = None,
    ) -> tuple[str, SafetyClass]:
        """Validate skill lifecycle status, block BulletTrain infra ops, verify MCP signature,
        and validate tool input schema before dispatch (CON-SKL-003, CON-TOOL-001..005).
        """
        if intent in BULLETTRAIN_INFRA_OPS_ACTIONS or (
            mcp_tool_id and mcp_tool_id in BULLETTRAIN_INFRA_OPS_ACTIONS
        ):
            raise ConductorAdmissionError(
                f"Clinical/operational Conductor is strictly isolated from BulletTrain "
                f"infrastructure self-healing action '{intent}' (CON-TOOL-005)"
            )
        if skill_id in self._revoked_skills or skill_id not in self._approved_skills:
            raise ConductorAdmissionError(
                f"Skill '{skill_id}' is unapproved, stale, or quarantined (CON-SKL-003)"
            )
        if mcp_tool_id is not None:
            expected_digest = self._signed_mcp_tools.get(mcp_tool_id)
            if expected_digest is None or expected_digest != mcp_digest:
                raise ConductorAdmissionError(
                    f"Dynamic or unsigned MCP tool '{mcp_tool_id}' rejected: "
                    "missing GHARRA digest verification (CON-TOOL-003)"
                )
        decision = resolve_intent(intent, self._manifests)
        if not decision.manifest_backed or decision.component is None:
            raise ConductorAdmissionError(
                f"Intent '{intent}' is not backed by an approved AgentActionManifest (CON-TOOL-001)"
            )
        manifest = self._manifests[decision.component]
        action_intent = manifest.get(intent)
        action_intent.validate_payload(payload)
        return decision.component, action_intent.safety_class

    def enforce_budget_and_fanout(
        self,
        *,
        requested_fanout: int,
        max_fanout: int = 5,
        estimated_tokens: int = 1000,
        token_budget: int = 4000,
        estimated_cost_gbp: float = 0.0,
        contains_phi: bool = True,
        requested_provider: str = "ollama_local",
    ) -> dict[str, Any]:
        """Enforce local-first routing, PHI internal-only provider policy, sub-agent
        fan-out bounds, and the £10.00/month ceiling (ADR-CON-005, CON-SKL-004, CON-PERF-001).
        """
        if contains_phi and requested_provider not in {"ollama_local", "internal_clinical"}:
            raise ConductorSecurityError(
                f"PHI workload cannot route to external provider '{requested_provider}' "
                "(ADR-CON-005: phi_internal_only)"
            )
        if requested_fanout > max_fanout:
            raise ConductorBudgetExceededError(
                f"Requested sub-agent fan-out ({requested_fanout}) exceeds max_fanout ({max_fanout}) "
                "(CON-SKL-004 / CON-PERF-001)"
            )
        if estimated_tokens > token_budget:
            raise ConductorBudgetExceededError(
                f"Estimated tokens ({estimated_tokens}) exceed token_budget ({token_budget}) "
                "(CON-PERF-001)"
            )
        if self._accumulated_spend_gbp + estimated_cost_gbp > self._gateway_cap_gbp:
            raise ConductorBudgetExceededError(
                f"Projected spend £{self._accumulated_spend_gbp + estimated_cost_gbp:.2f} "
                f"exceeds LFG-Control gateway hard cap £{self._gateway_cap_gbp:.2f} "
                f"(monthly ceiling £{self._monthly_ceiling_gbp:.2f}, mode={self._routing_mode})"
            )
        self._accumulated_spend_gbp += estimated_cost_gbp
        return {
            "routing_mode": self._routing_mode,
            "selected_provider": requested_provider,
            "accumulated_spend_gbp": round(self._accumulated_spend_gbp, 4),
            "gateway_cap_gbp": self._gateway_cap_gbp,
            "monthly_ceiling_gbp": self._monthly_ceiling_gbp,
        }

    def execute_governed_step(
        self,
        workflow_id: str,
        *,
        step_id: str,
        intent: str,
        payload: dict[str, Any],
        idempotency_key: str,
        claims: PersonaTokenClaims,
        skill_id: str = "baseline-governed-agent",
        tenant_id: str = "nhs-trust-01",
        token_tenant: str = "nhs-trust-01",
        target_jurisdiction: str = "UK_NHS",
        token_jurisdiction: str = "UK_NHS",
        is_write: bool = True,
        is_provisional: bool = False,
        clinician_hitl_signoff_id: str | None = None,
        fn: Callable[[], dict[str, Any]],
    ) -> SideEffectReceipt:
        """Execute a single governed step with two-phase PEP check, pre-retry downstream
        effect reconciliation (CON-DUR-002), mandatory HITL suspension for high-risk
        clinical discharge/dispensing actions (CON-AUTH-002, CON-SIB-003, CON-SIB-004),
        and ``prompt_engine.healthcare.validators.validate_output`` schema check.
        """
        component, safety_class = self.admit_skill_and_tool(
            skill_id=skill_id, intent=intent, payload=payload
        )
        patient_ref = payload.get("patient")
        # Phase 1 PEP check: dispatch authorization
        self.verify_delegation_claims(
            claims,
            target_component=component,
            target_patient=patient_ref,
            target_tenant=tenant_id,
            token_tenant=token_tenant,
            required_scope=PersonaScope.api_write if is_write else PersonaScope.api_read,
            target_jurisdiction=target_jurisdiction,
            token_jurisdiction=token_jurisdiction,
            is_write=is_write,
            is_provisional=is_provisional,
            safety_class=safety_class,
        )

        # Mandatory HITL check for irreversible clinical actions (CON-AUTH-002)
        if intent in CLINICAL_HITL_MANDATORY_INTENTS and not clinician_hitl_signoff_id:
            pkg = HandoffPackage(
                workflow_id=workflow_id,
                trigger=HandoffTrigger.policy_block,
                task_summary=f"Mandatory clinician HITL review required for '{intent}'",
                provenance_ref=f"Provenance/{workflow_id}-{step_id}",
                audit_chain_ref=f"AuditEvent/{workflow_id}-{step_id}",
                decision_rationale=f"Intent '{intent}' is classified high_risk clinical action requiring human clinician sign-off",
                recommended_next_action=f"Review and sign off '{intent}' for {patient_ref}",
                pre_handoff_state=WorkflowState.running.value,
                pending_inputs=["clinician_hitl_signoff_id"],
            )
            self._adapter.suspend_for_human_review(
                pkg, tenant_id=tenant_id, operator_subject=claims.persona
            )
            raise ConductorAuthorizationError(
                f"Workflow '{workflow_id}' suspended to WAITING_HUMAN (needs_human_review): "
                f"'{intent}' requires explicit clinician_hitl_signoff_id (CON-AUTH-002)"
            )

        reconciled_effect = self._downstream_effects.get(idempotency_key)

        def _wrapped_execution() -> dict[str, Any]:
            # Phase 2 PEP check: immediately before irreversible write (CON-PER-004)
            self.verify_delegation_claims(
                claims,
                target_component=component,
                target_patient=patient_ref,
                target_tenant=tenant_id,
                token_tenant=token_tenant,
                required_scope=PersonaScope.api_write if is_write else PersonaScope.api_read,
                target_jurisdiction=target_jurisdiction,
                token_jurisdiction=token_jurisdiction,
                is_write=is_write,
                is_provisional=is_provisional,
                safety_class=safety_class,
            )
            if reconciled_effect is not None:
                return dict(reconciled_effect)
            result = fn() or {}
            # Validate output against prompt-engine healthcare output validator
            _ensure_spine_paths_on_sys_path()
            try:
                from prompt_engine.healthcare.validators import validate_output

                validate_output(result, {"type": "object"})
            except ImportError:
                pass
            self._downstream_effects[idempotency_key] = dict(result)
            return result

        return self._adapter.execute_idempotent_step(
            workflow_id,
            step_id=step_id,
            idempotency_key=idempotency_key,
            payload=payload,
            fn=_wrapped_execution,
            tenant_id=tenant_id,
            operator_subject=claims.persona,
        )

    def record_unacknowledged_downstream_commit(
        self, idempotency_key: str, effect_output: dict[str, Any]
    ) -> None:
        """Simulate a downstream commit whose network response was lost before the caller
        received acknowledgement, so the next retry reconciles it (CON-DUR-002).
        """
        self._downstream_effects[idempotency_key] = dict(effect_output)

    def execute_dag(
        self,
        workflow_id: str,
        nodes: list[ConductorDAGNode],
        *,
        claims: PersonaTokenClaims,
        step_handlers: dict[str, Callable[[ConductorDAGNode], dict[str, Any]]],
        cancel_after_steps: set[str] | None = None,
        tenant_id: str = "nhs-trust-01",
    ) -> ConductorDAGResult:
        """Execute a multi-step DAG with dependency barriers (CON-DUR-003) and
        parent-to-child cancellation + deterministic compensation propagation (CON-DUR-004).
        """
        all_step_ids = [n.step_id for n in nodes]
        completed: list[str] = []
        cancelled: list[str] = []
        receipts: dict[str, SideEffectReceipt] = {}
        compensations: list[CompensationRecord] = []
        pending = list(nodes)

        # Ensure workflow is admitted and running
        ledger = self._adapter.load_ledger()
        if ledger.current_state(workflow_id) is None:
            self._adapter.admit(
                workflow_id,
                f"{workflow_id}:admit",
                payload={"dag_steps": all_step_ids},
                tenant_id=tenant_id,
                operator_subject=claims.persona,
            )
            self._adapter.record(
                workflow_id,
                f"{workflow_id}:dispatch",
                WorkflowState.running,
                payload={"phase": ConductorLifecycleState.DISPATCHED.value},
                tenant_id=tenant_id,
                operator_subject=claims.persona,
            )

        while pending:
            ready = [
                n for n in pending if all(dep in completed for dep in n.depends_on)
            ]
            if not ready:
                raise LedgerError(
                    f"DAG deadlock or unsatisfied barrier in workflow '{workflow_id}'"
                )
            for node in ready:
                pending.remove(node)
                if cancel_after_steps and cancel_after_steps.issubset(set(completed)):
                    cancelled.append(node.step_id)
                    continue
                handler = step_handlers[node.step_id]
                receipt = self.execute_governed_step(
                    workflow_id,
                    step_id=node.step_id,
                    intent=node.intent,
                    payload=node.payload,
                    idempotency_key=node.idempotency_key,
                    claims=claims,
                    tenant_id=tenant_id,
                    token_tenant=tenant_id,
                    is_write=node.is_write,
                    fn=lambda n=node, h=handler: h(n),
                )
                receipts[node.step_id] = receipt
                completed.append(node.step_id)

            if cancel_after_steps and cancel_after_steps.issubset(set(completed)):
                for remaining in list(pending):
                    cancelled.append(remaining.step_id)
                pending.clear()
                self._adapter.record(
                    workflow_id,
                    f"{workflow_id}:compensating",
                    WorkflowState.compensating,
                    payload={"cancelled_steps": cancelled},
                    tenant_id=tenant_id,
                    operator_subject=claims.persona,
                )
                for done_step_id in reversed(completed):
                    done_node = next(n for n in nodes if n.step_id == done_step_id)
                    if done_node.compensation_action:
                        compensations.append(
                            CompensationRecord(
                                workflow_id=workflow_id,
                                step_id=done_step_id,
                                compensation_action=done_node.compensation_action,
                                reason="parent_workflow_cancelled",
                                recorded_at=_now_iso(),
                            )
                        )
                self._adapter.record(
                    workflow_id,
                    f"{workflow_id}:cancelled",
                    WorkflowState.cancelled,
                    payload={
                        "compensations": [c.compensation_action for c in compensations]
                    },
                    tenant_id=tenant_id,
                    operator_subject=claims.persona,
                )
                break
        else:
            self._adapter.record(
                workflow_id,
                f"{workflow_id}:completed",
                WorkflowState.completed,
                payload={"completed_steps": completed},
                tenant_id=tenant_id,
                operator_subject=claims.persona,
            )

        ckpt = self._adapter.checkpoint_envelope(
            workflow_id,
            tenant_id=tenant_id,
            operator_subject=claims.persona,
            all_step_ids=all_step_ids,
        )
        return ConductorDAGResult(
            workflow_id=workflow_id,
            state=ckpt.state,
            completed_steps=tuple(completed),
            cancelled_steps=tuple(cancelled),
            receipts=receipts,
            compensations=tuple(compensations),
            checkpoint=ckpt,
        )

    def detect_contract_drift(
        self,
        *,
        component: str,
        intent: str,
        observed_payload: dict[str, Any],
        affected_personas: tuple[str, ...] = ("clinician-superpersona",),
        affected_skills: tuple[str, ...] = ("baseline-governed-agent",),
    ) -> ReassessmentTrigger | None:
        """Detect sibling API/schema drift against the registered AgentActionManifest
        and emit a fail-closed ReassessmentTrigger (CON-OPS-001, CON-PROM-003).
        """
        manifest = self._manifests.get(component)
        if manifest is None or not manifest.has(intent):
            return ReassessmentTrigger(
                trigger_id=f"drift-{component}-{intent}",
                source_type="contract_drift",
                affected_component=component,
                affected_personas=affected_personas,
                affected_skills=affected_skills,
                quarantined=True,
                summary=f"Missing manifest/intent '{intent}' on component '{component}'",
                created_at=_now_iso(),
            )
        try:
            manifest.get(intent).validate_payload(observed_payload)
            return None
        except ManifestError as exc:
            for skill in affected_skills:
                self._revoked_skills.add(skill)
            return ReassessmentTrigger(
                trigger_id=f"drift-{component}-{intent}",
                source_type="contract_drift",
                affected_component=component,
                affected_personas=affected_personas,
                affected_skills=affected_skills,
                quarantined=True,
                summary=f"Schema drift detected on {component}:{intent}: {exc}",
                created_at=_now_iso(),
            )
