"""Signal governance -- turn a perceived UI signal into a governed decision.

This is the shared "decide + govern" core consumed by BOTH SignalBox faces (the
standalone signalbox-mcp server and the BulletTrain-embedded control plane), in
the same one-capability-two-faces pattern as :func:`bridge_sdk.agent_contract.
resolve_intent` (FR-AEC-005). It does NOT reinvent governance: it COMPOSES the
existing primitives ::

    resolve_intent        (agent_contract)     -- intent -> typed path + safety class
    ClinicalSafetyCase    (clinical_safety_case, WS10) -- autonomy gate
    ConsentProjection     (consent_projection, WS9)    -- fail-closed consent gate
    PersonaExecutionBudget(concurrency, WS6)            -- scope / mandate headroom
    EmergencyOverride     (concurrency, WS6)            -- break-glass gate
    HandoffPackage        (human_handoff, WS11)         -- HITL escalation artefact
    DecisionCard          (agent_audit, WS4)            -- audit / explainability

It implements the risk-tiered HITL model with a fail-closed safe-bypass predicate
(AGENT_TOOLTIPS_DESIGN.md section 6): perception never blocks; a reversible,
high-confidence, attested, in-scope, routine action may run human-ON-the-loop;
everything else escalates to a blocking human-IN-the-loop review or halts.

PURITY CONTRACT. ``evaluate_signal_action`` is a pure decision function: it only
READS the gates (``can_promote_to``, ``permits``, ``saturation``, ``is_approved``)
and never mutates them (no budget charge, no inbox enqueue, no override authorise).
The caller (each face) applies the side effects AFTER acting on the decision. This
keeps the two faces deterministic and identical -- the property the parity test
relies on -- and prevents double-charging when the decision is evaluated twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bridge_sdk.agent_contract import (
    REFERENCE_MANIFESTS,
    AgentActionManifest,
    ManifestError,
    SafetyClass,
    resolve_intent,
)
from bridge_sdk.clinical_safety_case import AutonomyStage, ClinicalSafetyCase
from bridge_sdk.concurrency import EmergencyOverride, PersonaExecutionBudget
from bridge_sdk.consent_projection import ConsentDenied, ConsentProjection
from bridge_sdk.agent_audit import DecisionCard
from bridge_sdk.human_handoff import HandoffPackage, HandoffTrigger

__all__ = [
    "PerceivedSignal",
    "GovernanceTier",
    "GovernedDecision",
    "evaluate_signal_action",
    "CONFIDENCE_BYPASS_THRESHOLD",
]

# A reversible, in-scope action may run human-on-the-loop only at/above this
# model/data confidence. Below it, the action escalates to a blocking review.
CONFIDENCE_BYPASS_THRESHOLD = 0.85


class GovernanceTier(str, Enum):
    """Where the human sits relative to the decision (design section 6)."""

    perceive = "perceive"  # Tier 0: read-only; perception never blocks
    auto_on_loop = "auto_on_loop"  # Tier 1/2: proceed, human ON the loop (undo/audit)
    human_in_loop = "human_in_loop"  # Tier 3: blocking human sign-off
    halt = "halt"  # blocked outright (fail-closed)


@dataclass(frozen=True)
class PerceivedSignal:
    """The agent-perceived context for a UI element (from the SignalBox RefMap).

    ``description`` is the resolved accessible description (the human tooltip
    channel); ``evidence_ref`` is the non-PHI agent-evidence pointer. The rest are
    machine hints that, once the evidence-resolution API exists, come from the
    canonical FHIR evidence (``attested`` = signature + anchor verified).
    """

    description: str = ""
    evidence_ref: str = ""
    attested: bool = False
    confidence: float | None = None
    origin: str = ""  # ai | human | device | ""
    reversible: bool | None = None


@dataclass(frozen=True)
class GovernedDecision:
    """The governed outcome for a single intended action against a signal."""

    tier: GovernanceTier
    permitted: bool
    reasons: list[str] = field(default_factory=list)
    resolver_path: str = ""
    safety_class: str = ""
    handoff: dict[str, Any] | None = None  # HandoffPackage.to_dict() when escalating
    decision_card: dict[str, Any] | None = None  # DecisionCard.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "permitted": self.permitted,
            "reasons": list(self.reasons),
            "resolver_path": self.resolver_path,
            "safety_class": self.safety_class,
            "handoff": self.handoff,
            "decision_card": self.decision_card,
        }


def _safety_class_for(
    intent: str, decision: Any, manifests: dict[str, AgentActionManifest]
) -> SafetyClass:
    """Resolve the action's safety class from its manifest, fail-closed.

    A manifest-backed intent carries an explicit class; an unknown intent
    (ui_fallback) is treated as ``sensitive`` so it can never auto-bypass.
    """
    if decision.manifest_backed and decision.component in manifests:
        try:
            return manifests[decision.component].get(intent).safety_class
        except ManifestError:
            return SafetyClass.high_risk
    return SafetyClass.sensitive


def _trigger_from_reasons(reasons: list[str]) -> HandoffTrigger:
    joined = " ".join(reasons)
    if "consent:" in joined:
        return HandoffTrigger.consent_conflict
    if "safety_class:" in joined or "safety_case:" in joined or "break_glass:" in joined:
        return HandoffTrigger.policy_block
    if "bypass_block:low_confidence" in joined:
        return HandoffTrigger.low_confidence
    return HandoffTrigger.low_confidence


def evaluate_signal_action(
    *,
    intent: str,
    persona: str,
    signal: PerceivedSignal | None = None,
    action_intended: bool = True,
    safety_case: ClinicalSafetyCase | None = None,
    consent: ConsentProjection | None = None,
    budget: PersonaExecutionBudget | None = None,
    emergency: EmergencyOverride | None = None,
    purpose_of_use: str = "",
    resource_type: str = "",
    jurisdiction: str = "",
    current_consent_version: int | None = None,
    break_glass: bool = False,
    break_glass_category: str = "",
    workflow_id: str = "",
    correlation_id: str = "",
    manifests: dict[str, AgentActionManifest] | None = None,
) -> GovernedDecision:
    """Compose the governance gates into one decision for an intended action.

    Returns a :class:`GovernedDecision`; never raises (a faulty gate fails closed
    to escalation). See the module docstring for the purity contract.
    """
    sig = signal or PerceivedSignal()
    ms = REFERENCE_MANIFESTS if manifests is None else manifests
    reasons: list[str] = []

    decision = resolve_intent(intent, ms)
    resolver_path = decision.path.value
    safety_class = _safety_class_for(intent, decision, ms)
    action_path = f"{decision.component or 'ui'}/{intent}"

    # Tier 0: pure perception never blocks.
    if not action_intended:
        return GovernedDecision(
            tier=GovernanceTier.perceive,
            permitted=True,
            reasons=["read_only"],
            resolver_path=resolver_path,
            safety_class=safety_class.value,
            decision_card=_card(
                correlation_id, workflow_id, persona, action_path, "perceive",
                ["read_only"], sig,
            ),
        )

    halt = False

    # --- Consent gate (WS9), fail-closed --------------------------------------
    consent_denied: str | None = None
    if consent is not None:
        ccv = (
            current_consent_version
            if current_consent_version is not None
            else consent.consent_version
        )
        try:
            consent.authorise(
                purpose_of_use=purpose_of_use,
                resource_type=resource_type,
                target_jurisdiction=jurisdiction,
                current_consent_version=ccv,
            )
        except ConsentDenied as denied:
            # ConsentDenied stores the machine-readable code in `.reason` and
            # passes the human detail to the base Exception (so args[0] is the
            # detail, not the code).
            consent_denied = denied.reason
            reasons.append(f"consent:{consent_denied}")
    elif safety_class in (SafetyClass.sensitive, SafetyClass.high_risk):
        # A sensitive/high-risk action with no consent context cannot auto-proceed.
        reasons.append("consent:absent_for_sensitive")

    # --- Break-glass gate (WS6) -----------------------------------------------
    break_glass_ok = False
    if break_glass:
        break_glass_ok = emergency is not None and emergency.is_approved(
            break_glass_category
        )
        reasons.append(
            "break_glass:approved" if break_glass_ok else "break_glass:not_approved"
        )
        if not break_glass_ok:
            halt = True

    # Consent denial halts unless an APPROVED break-glass routes it to review.
    if consent_denied is not None and not (break_glass and break_glass_ok):
        halt = True

    # --- Safety-case gate (WS10) ----------------------------------------------
    safety_ok_for_auto = True
    if safety_case is not None and not safety_case.can_promote_to(
        AutonomyStage.bounded_auto
    ):
        safety_ok_for_auto = False
        reasons.append("safety_case:not_approved_for_auto")
    if safety_class is SafetyClass.high_risk:
        safety_ok_for_auto = False
        reasons.append("safety_class:high_risk")

    # --- Budget / scope headroom (WS6), read-only -----------------------------
    budget_ok = True
    if budget is not None:
        sat = budget.saturation(persona)
        if sat.get("breaches", 0) > 0 or sat.get("concurrent_workflows", 0) >= sat.get(
            "max_concurrent_workflows", 1
        ):
            budget_ok = False
            reasons.append("budget:saturated")

    # --- Resolve the tier ------------------------------------------------------
    if halt:
        tier = GovernanceTier.halt
        permitted = False
    else:
        bypass = (
            sig.reversible is True
            and sig.confidence is not None
            and sig.confidence >= CONFIDENCE_BYPASS_THRESHOLD
            and sig.attested is True
            and safety_class is SafetyClass.routine
            and safety_ok_for_auto
            and budget_ok
            and consent_denied is None
            and not break_glass
        )
        if bypass:
            tier = GovernanceTier.auto_on_loop
            permitted = True
            reasons.append("safe_bypass:granted")
        else:
            tier = GovernanceTier.human_in_loop
            permitted = False
            if sig.reversible is not True:
                reasons.append("bypass_block:not_reversible")
            if not (sig.confidence is not None and sig.confidence >= CONFIDENCE_BYPASS_THRESHOLD):
                reasons.append("bypass_block:low_confidence")
            if not sig.attested:
                reasons.append("bypass_block:unattested")

    # --- Escalation artefact (WS11) -------------------------------------------
    handoff: dict[str, Any] | None = None
    if tier is GovernanceTier.human_in_loop or (tier is GovernanceTier.halt and break_glass):
        pkg = HandoffPackage(
            workflow_id=workflow_id or "wf-unknown",
            trigger=_trigger_from_reasons(reasons),
            task_summary=f"Governed review of intent '{intent}' for persona '{persona}'",
            provenance_ref=sig.evidence_ref or "signalbox://no-evidence-pointer",
            audit_chain_ref=correlation_id or workflow_id or "corr-unknown",
            decision_rationale="; ".join(reasons) or "escalated",
            recommended_next_action=f"Human review then resume '{intent}'",
            pre_handoff_state="awaiting_human_review",
        )
        handoff = pkg.to_dict()

    card = _card(
        correlation_id, workflow_id, persona, action_path, tier.value, reasons, sig
    )
    return GovernedDecision(
        tier=tier,
        permitted=permitted,
        reasons=reasons,
        resolver_path=resolver_path,
        safety_class=safety_class.value,
        handoff=handoff,
        decision_card=card,
    )


def _card(
    correlation_id: str,
    workflow_id: str,
    persona: str,
    action_path: str,
    outcome: str,
    reasons: list[str],
    sig: PerceivedSignal,
) -> dict[str, Any]:
    return DecisionCard(
        correlation_id=correlation_id or workflow_id or "corr-unknown",
        persona=persona,
        action_path=action_path,
        outcome=outcome,
        rationale="; ".join(reasons) or "ok",
        evidence_references=[sig.evidence_ref] if sig.evidence_ref else [],
    ).to_dict()
