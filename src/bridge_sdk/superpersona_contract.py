"""Superpersona contracts for governed clinical agent execution.

This module binds an existing persona key to action manifests, tool bindings,
IAM scopes, safety posture, eval evidence, jurisdiction context, intuition
selection, and runtime budget policy. It does not own the persona registry.
GHARRA remains the persona source of truth; this SDK owns the interoperable
contract shape that GHARRA and downstream consumers exchange.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from bridge_sdk.agent_contract import (
    REFERENCE_MANIFESTS,
    AgentActionManifest,
    AutonomyLevel,
    ExecutionMode,
    SafetyClass,
)
from bridge_sdk.persona_delegation import PersonaScope

__all__ = [
    "EvalPackRef",
    "IntuitionDecision",
    "RuntimeBudgetPolicy",
    "SkillPackRef",
    "SuperpersonaContract",
    "ToolBinding",
    "ToolProtocol",
    "build_superpersona_contract",
    "reference_superpersona_contract",
]

CONTRACT_SCHEMA_VERSION = "1.0.0"
SIGNALBOX_TOOL_IDS = (
    "signalbox.capture-session",
    "signalbox-mcp.invoke-tool",
    "signalbox-mcp.capture-attestation",
)


class ToolProtocol(str, Enum):
    """Protocol surface used by a governed tool binding."""

    typed_api = "typed_api"
    nexus_a2a = "nexus_a2a"
    mcp = "mcp"
    semantic_ui = "semantic_ui"
    browser = "browser"


class SkillPackRef(BaseModel):
    """Reference to a persona skill pack or clinical competency bundle."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    owner: str = "symphonix"
    version: str = "1.0.0"


class EvalPackRef(BaseModel):
    """Reference to eval evidence required before a contract is trusted."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: str = "1.0.0"
    evidence_uri: str | None = None


class RuntimeBudgetPolicy(BaseModel):
    """Runtime cost, concurrency, and provider-risk envelope."""

    model_config = ConfigDict(extra="forbid")

    budget_class: str
    provider_policy: str
    latency_slo_ms: int = Field(ge=1)
    token_budget: int = Field(ge=1)
    cost_class: str
    max_concurrency: int = Field(ge=1)


class IntuitionDecision(BaseModel):
    """Auditable pre-deliberation route and framework selection."""

    model_config = ConfigDict(extra="forbid")

    selected_framework: str
    route_salience: dict[str, float] = Field(default_factory=dict)
    candidate_hypotheses: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)


class ToolBinding(BaseModel):
    """A governed binding between a persona and executable tool surface."""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    component: str
    protocol: ToolProtocol
    intent_ids: list[str] = Field(default_factory=list)
    required_scopes: list[PersonaScope] = Field(default_factory=list)
    safety_class: SafetyClass = SafetyClass.routine


class SuperpersonaContract(BaseModel):
    """Versioned contract binding a persona to governed execution rights."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    version: str = CONTRACT_SCHEMA_VERSION
    persona_key: str
    role_title: str
    role_category: str
    jurisdiction_pack: str
    allowed_purposes: list[str] = Field(default_factory=list)
    skill_packs: list[SkillPackRef] = Field(default_factory=list)
    tool_bindings: list[ToolBinding] = Field(default_factory=list)
    action_intent_ids: list[str] = Field(default_factory=list)
    autonomy_default: AutonomyLevel = AutonomyLevel.advisory
    safety_class: SafetyClass = SafetyClass.routine
    eval_packs: list[EvalPackRef] = Field(default_factory=list)
    runtime_budget: RuntimeBudgetPolicy
    required_token_scopes: list[PersonaScope] = Field(default_factory=list)
    intuition: IntuitionDecision

    @model_validator(mode="after")
    def _validate_contract(self) -> "SuperpersonaContract":
        known = _intent_component_map()
        unknown = sorted(set(self.action_intent_ids) - set(known))
        if unknown:
            raise ValueError(f"unknown action intent ids: {unknown}")
        if not self.required_token_scopes:
            raise ValueError("required_token_scopes must not be empty")
        bound = {intent for binding in self.tool_bindings for intent in binding.intent_ids}
        missing_bindings = sorted(set(self.action_intent_ids) - bound)
        if missing_bindings:
            raise ValueError(f"action intents missing tool bindings: {missing_bindings}")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def execution_modes(self) -> list[ExecutionMode]:
        protocols = {binding.protocol for binding in self.tool_bindings}
        modes: set[ExecutionMode] = set()
        if ToolProtocol.typed_api in protocols or ToolProtocol.nexus_a2a in protocols:
            modes.add(ExecutionMode.typed_api)
        if ToolProtocol.mcp in protocols or ToolProtocol.semantic_ui in protocols:
            modes.add(ExecutionMode.semantic_ui)
        if ToolProtocol.browser in protocols:
            modes.add(ExecutionMode.browser)
        return sorted(modes, key=lambda mode: mode.value)

    def to_gharra_contract(self) -> dict[str, Any]:
        """Emit the registry-facing contract payload without token material."""
        return self.model_dump(mode="json")

    def a2a_card_extension(self) -> dict[str, Any]:
        """Emit the A2A card extension block for this superpersona."""
        return {
            "x-symphonix-superpersona": {
                "contract_id": self.contract_id,
                "version": self.version,
                "persona_key": self.persona_key,
                "action_intent_ids": list(self.action_intent_ids),
                "safety_class": self.safety_class.value,
                "required_token_scopes": [s.value for s in self.required_token_scopes],
                "runtime_budget_class": self.runtime_budget.budget_class,
            }
        }

    def mcp_tool_policy(self) -> dict[str, Any]:
        """Emit a minimal MCP policy fragment for fail-closed gateways."""
        return {
            "persona_key": self.persona_key,
            "contract_id": self.contract_id,
            "contract_version": self.version,
            "allowed_tools": [
                {
                    "tool_id": binding.tool_id,
                    "component": binding.component,
                    "intent_ids": list(binding.intent_ids),
                    "required_scopes": [s.value for s in binding.required_scopes],
                    "safety_class": binding.safety_class.value,
                }
                for binding in self.tool_bindings
            ],
        }

    def audit_evidence_ref(
        self,
        *,
        token_id: str | None = None,
        token_hash: str | None = None,
    ) -> dict[str, Any]:
        """Emit audit-safe identifiers. Never pass a raw JWT here."""
        payload: dict[str, Any] = {
            "contract_id": self.contract_id,
            "contract_version": self.version,
            "persona_key": self.persona_key,
            "safety_class": self.safety_class.value,
            "runtime_budget_class": self.runtime_budget.budget_class,
        }
        if token_id:
            payload["persona_token_id"] = token_id
        if token_hash:
            payload["persona_token_hash"] = token_hash
        return payload


def build_superpersona_contract(
    *,
    persona_key: str,
    role_title: str,
    role_category: str,
    allowed_purposes: list[str],
    jurisdiction_pack: str = "INTL",
    default_framework: str | None = None,
    toolset: list[str] | None = None,
    capabilities: list[dict[str, Any]] | None = None,
    action_intent_ids: list[str] | None = None,
    autonomy_default: AutonomyLevel = AutonomyLevel.advisory,
) -> SuperpersonaContract:
    """Build a deterministic contract from registry persona primitives."""
    intents = action_intent_ids or _infer_action_intents(role_category, allowed_purposes)
    scopes = _infer_scopes(role_category, intents, capabilities or [])
    safety = _max_safety_class(intents)
    signalbox_required = _requires_signalbox(
        role_category,
        allowed_purposes,
        capabilities or [],
        safety,
    )
    if signalbox_required:
        scopes = _merge_scopes(
            scopes,
            [
                PersonaScope.api_read,
                PersonaScope.task_execute,
                PersonaScope.ui_navigate,
                PersonaScope.task_escalate,
            ],
        )
    runtime_budget = _runtime_budget_for(safety)
    framework = default_framework or "soap"
    salience = {intent: round(1.0 / len(intents), 4) for intent in intents} if intents else {}

    return SuperpersonaContract(
        contract_id=_contract_id(persona_key, jurisdiction_pack, intents),
        persona_key=persona_key,
        role_title=role_title,
        role_category=role_category,
        jurisdiction_pack=jurisdiction_pack.upper(),
        allowed_purposes=list(allowed_purposes),
        skill_packs=_skill_packs_for(toolset or [], capabilities or []),
        tool_bindings=_tool_bindings_for(
            intents,
            scopes,
            signalbox_required=signalbox_required,
        ),
        action_intent_ids=intents,
        autonomy_default=autonomy_default,
        safety_class=safety,
        eval_packs=_eval_packs_for(safety),
        runtime_budget=runtime_budget,
        required_token_scopes=scopes,
        intuition=IntuitionDecision(
            selected_framework=framework,
            route_salience=salience,
            candidate_hypotheses=[f"{persona_key}:{intent}" for intent in intents],
            confidence=0.72 if safety is SafetyClass.high_risk else 0.8,
            risk_score=_risk_score_for(safety),
            reason_codes=[
                "persona.default_framework",
                "reference_action_manifest",
                f"safety.{safety.value}",
            ],
        ),
    )


def reference_superpersona_contract(persona_key: str) -> SuperpersonaContract:
    """Return a reference contract for common SignalBox/BulletTrain personas."""
    persona_key = persona_key.lower()
    refs: dict[str, dict[str, Any]] = {
        "doctor": {
            "role_title": "Doctor",
            "role_category": "clinical",
            "allowed_purposes": ["treatment", "emergency"],
            "default_framework": "isbar",
        },
        "nurse": {
            "role_title": "Nurse",
            "role_category": "nursing",
            "allowed_purposes": ["treatment", "emergency"],
            "default_framework": "i-pass",
        },
        "pharmacist": {
            "role_title": "Pharmacist",
            "role_category": "pharmacy",
            "allowed_purposes": ["treatment"],
            "default_framework": "soap",
        },
        "admin": {
            "role_title": "Administrator",
            "role_category": "administrative",
            "allowed_purposes": ["operations"],
            "default_framework": "soap",
        },
        "auditor": {
            "role_title": "Auditor",
            "role_category": "governance",
            "allowed_purposes": ["operations"],
            "default_framework": "soap",
        },
        "technician": {
            "role_title": "Technician",
            "role_category": "engineering",
            "allowed_purposes": ["operations"],
            "default_framework": "soap",
        },
    }
    if persona_key not in refs:
        raise KeyError(f"no reference superpersona contract for '{persona_key}'")
    return build_superpersona_contract(persona_key=persona_key, **refs[persona_key])


def _intent_component_map() -> dict[str, AgentActionManifest]:
    return {
        intent.intent: manifest
        for manifest in REFERENCE_MANIFESTS.values()
        for intent in manifest.intents
    }


def _infer_action_intents(role_category: str, allowed_purposes: list[str]) -> list[str]:
    category = role_category.lower()
    purposes = {p.lower() for p in allowed_purposes}
    if "emergency" in purposes or category in {"clinical", "nursing", "emergency"}:
        return ["triage.start", "appointment.book", "lab.order", "result.retrieve"]
    if category == "pharmacy":
        return ["result.retrieve"]
    if "operations" in purposes or category in {
        "administrative",
        "operations",
        "engineering",
        "governance",
    }:
        return ["appointment.book", "claim.submit", "result.retrieve"]
    return ["result.retrieve"]


def _infer_scopes(
    role_category: str,
    intents: list[str],
    capabilities: list[dict[str, Any]],
) -> list[PersonaScope]:
    scopes: set[PersonaScope] = {PersonaScope.api_read, PersonaScope.task_execute}
    category = role_category.lower()
    if category in {"administrative", "operations", "engineering", "governance"}:
        scopes.add(PersonaScope.api_write)
    if any(intent in {"appointment.book", "claim.submit", "lab.order"} for intent in intents):
        scopes.add(PersonaScope.api_write)
    for cap in capabilities:
        domain = str(cap.get("domain", "")).lower()
        actions = {str(a).lower() for a in cap.get("actions", [])}
        if domain in {"form_input", "workflow"} or actions & {"fill", "select"}:
            scopes.add(PersonaScope.ui_fill)
        if actions & {"submit", "approve", "order", "book"}:
            scopes.add(PersonaScope.ui_submit)
        if actions & {"navigate", "click", "scroll"}:
            scopes.add(PersonaScope.ui_navigate)
        if actions & {"escalate", "delegate"}:
            scopes.add(PersonaScope.task_escalate)
    return sorted(scopes, key=lambda scope: scope.value)


def _requires_signalbox(
    role_category: str,
    allowed_purposes: list[str],
    capabilities: list[dict[str, Any]],
    safety: SafetyClass,
) -> bool:
    category = role_category.lower()
    purposes = {purpose.lower() for purpose in allowed_purposes}
    if safety is SafetyClass.high_risk:
        return True
    if category in {"governance", "operations", "engineering"}:
        return True
    if purposes & {"oversight", "healthcare_operations", "operations"}:
        return True
    for cap in capabilities:
        domain = str(cap.get("domain", "")).lower()
        actions = {str(action).lower() for action in cap.get("actions", [])}
        if domain in {"governance", "audit", "workflow", "computer_use"}:
            return True
        if actions & {"audit", "attest", "capture", "delegate", "escalate"}:
            return True
    return False


def _merge_scopes(
    scopes: list[PersonaScope],
    additional: list[PersonaScope],
) -> list[PersonaScope]:
    return sorted({*scopes, *additional}, key=lambda scope: scope.value)


def _tool_bindings_for(
    intents: list[str],
    scopes: list[PersonaScope],
    *,
    signalbox_required: bool = False,
) -> list[ToolBinding]:
    by_component: dict[str, list[str]] = {}
    safety_by_component: dict[str, SafetyClass] = {}
    intent_map = _intent_component_map()
    for intent_id in intents:
        manifest = intent_map[intent_id]
        by_component.setdefault(manifest.component, []).append(intent_id)
        safety_by_component[manifest.component] = _max_safety_class(by_component[manifest.component])
    bindings = [
        ToolBinding(
            tool_id=f"{component}.agent-actions",
            component=component,
            protocol=ToolProtocol.typed_api,
            intent_ids=intent_ids,
            required_scopes=scopes,
            safety_class=safety_by_component[component],
        )
        for component, intent_ids in sorted(by_component.items())
    ]
    if signalbox_required:
        bindings.extend(_signalbox_tool_bindings(intents, scopes))
    return bindings


def _signalbox_tool_bindings(
    intents: list[str],
    scopes: list[PersonaScope],
) -> list[ToolBinding]:
    signalbox_scopes = [
        scope
        for scope in scopes
        if scope
        in {
            PersonaScope.api_read,
            PersonaScope.task_execute,
            PersonaScope.ui_navigate,
            PersonaScope.task_escalate,
        }
    ]
    safety = _max_safety_class(intents)
    return [
        ToolBinding(
            tool_id="signalbox.capture-session",
            component="signalbox",
            protocol=ToolProtocol.semantic_ui,
            intent_ids=list(intents),
            required_scopes=signalbox_scopes,
            safety_class=safety,
        ),
        ToolBinding(
            tool_id="signalbox-mcp.invoke-tool",
            component="signalbox-mcp",
            protocol=ToolProtocol.mcp,
            intent_ids=list(intents),
            required_scopes=signalbox_scopes,
            safety_class=safety,
        ),
        ToolBinding(
            tool_id="signalbox-mcp.capture-attestation",
            component="signalbox-mcp",
            protocol=ToolProtocol.mcp,
            intent_ids=list(intents),
            required_scopes=signalbox_scopes,
            safety_class=safety,
        ),
    ]


def _max_safety_class(intents: list[str]) -> SafetyClass:
    rank = {
        SafetyClass.routine: 0,
        SafetyClass.sensitive: 1,
        SafetyClass.high_risk: 2,
    }
    intent_map = _intent_component_map()
    classes = [intent_map[intent].get(intent).safety_class for intent in intents]
    return max(classes, key=lambda safety: rank[safety])


def _runtime_budget_for(safety: SafetyClass) -> RuntimeBudgetPolicy:
    if safety is SafetyClass.high_risk:
        return RuntimeBudgetPolicy(
            budget_class="clinical_high_risk",
            provider_policy="phi_internal_only",
            latency_slo_ms=2000,
            token_budget=4000,
            cost_class="high",
            max_concurrency=1,
        )
    if safety is SafetyClass.sensitive:
        return RuntimeBudgetPolicy(
            budget_class="clinical_sensitive",
            provider_policy="phi_internal_only",
            latency_slo_ms=1500,
            token_budget=2500,
            cost_class="medium",
            max_concurrency=3,
        )
    return RuntimeBudgetPolicy(
        budget_class="routine",
        provider_policy="general",
        latency_slo_ms=1000,
        token_budget=1000,
        cost_class="low",
        max_concurrency=10,
    )


def _eval_packs_for(safety: SafetyClass) -> list[EvalPackRef]:
    packs = [EvalPackRef(id="agent-contract-smoke", evidence_uri="tests://agent_contract")]
    if safety is SafetyClass.high_risk:
        packs.append(
            EvalPackRef(
                id="clinical-safety-case",
                evidence_uri="tests://clinical_safety_case",
            )
        )
    return packs


def _skill_packs_for(
    toolset: list[str],
    capabilities: list[dict[str, Any]],
) -> list[SkillPackRef]:
    packs: dict[str, SkillPackRef] = {}
    for item in toolset:
        slug = _slug(item)
        packs[slug] = SkillPackRef(id=slug, title=item)
    for cap in capabilities:
        domain = str(cap.get("domain", "")).strip()
        if not domain:
            continue
        slug = f"capability-{_slug(domain)}"
        packs.setdefault(slug, SkillPackRef(id=slug, title=f"{domain} capability"))
    if not packs:
        packs["baseline-governed-agent"] = SkillPackRef(
            id="baseline-governed-agent",
            title="Baseline governed agent capability",
        )
    return sorted(packs.values(), key=lambda pack: pack.id)


def _risk_score_for(safety: SafetyClass) -> float:
    return {
        SafetyClass.routine: 0.2,
        SafetyClass.sensitive: 0.55,
        SafetyClass.high_risk: 0.85,
    }[safety]


def _contract_id(persona_key: str, jurisdiction_pack: str, intents: list[str]) -> str:
    seed = "|".join([persona_key, jurisdiction_pack.upper(), *sorted(intents)])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"spc-{_slug(persona_key)}-{jurisdiction_pack.lower()}-{digest}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
