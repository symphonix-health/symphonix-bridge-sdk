"""Tests for bridge_sdk.signal_governance -- the shared decide+govern core.

Covers every governance tier and the fail-closed safe-bypass predicate, and the
determinism property the two-face parity test relies on. Composes only the real
primitives (no mocks).
"""

from __future__ import annotations

import pytest

from bridge_sdk import (
    ActionIntent,
    AgentActionManifest,
    AutonomyLevel,
    ClinicalSafetyCase,
    EmergencyOverride,
    ExecutionBudgetLimits,
    GovernanceTier,
    Hazard,
    HazardSeverity,
    IOContract,
    PerceivedSignal,
    PersonaExecutionBudget,
    SafetyClass,
    evaluate_signal_action,
    project_consent,
)

PERSONA = "ops-agent"

# A routine (non-clinical) manifest -- the only class eligible for auto-on-loop.
_ROUTINE_MANIFEST = AgentActionManifest(
    component="ops",
    intents=[
        ActionIntent(
            intent="dashboard.filter",
            title="Filter the dashboard",
            component="ops",
            safety_class=SafetyClass.routine,
            autonomy_default=AutonomyLevel.auto_with_threshold_hitl,
            input=IOContract(fields=[]),
            output=IOContract(fields=[]),
            preconditions=[],
            postconditions=[],
            fhir_task_code="filter",
        )
    ],
)
_ROUTINE = {"ops": _ROUTINE_MANIFEST}

# A signal that satisfies the safe-bypass predicate.
_BYPASS_SIGNAL = PerceivedSignal(
    description="Filter to active patients",
    evidence_ref="urn:agent-evidence:ui-filter:v1",
    attested=True,
    confidence=0.99,
    origin="human",
    reversible=True,
)


def test_perceive_never_blocks() -> None:
    d = evaluate_signal_action(
        intent="triage.start", persona=PERSONA, action_intended=False
    )
    assert d.tier is GovernanceTier.perceive
    assert d.permitted is True
    assert d.decision_card is not None


def test_routine_action_auto_on_loop() -> None:
    d = evaluate_signal_action(
        intent="dashboard.filter",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        manifests=_ROUTINE,
    )
    assert d.tier is GovernanceTier.auto_on_loop
    assert d.permitted is True
    assert "safe_bypass:granted" in d.reasons
    assert d.handoff is None


@pytest.mark.parametrize(
    "mutate,reason",
    [
        ({"confidence": 0.5}, "bypass_block:low_confidence"),
        ({"attested": False}, "bypass_block:unattested"),
        ({"reversible": False}, "bypass_block:not_reversible"),
        ({"reversible": None}, "bypass_block:not_reversible"),
    ],
)
def test_failed_bypass_predicate_escalates(mutate: dict, reason: str) -> None:
    from dataclasses import replace

    sig = replace(_BYPASS_SIGNAL, **mutate)
    d = evaluate_signal_action(
        intent="dashboard.filter", persona=PERSONA, signal=sig, manifests=_ROUTINE
    )
    assert d.tier is GovernanceTier.human_in_loop
    assert d.permitted is False
    assert reason in d.reasons
    assert d.handoff is not None  # escalation artefact built


def test_high_risk_class_never_auto() -> None:
    # triage.start is high_risk; even a perfect signal must not auto-bypass.
    d = evaluate_signal_action(
        intent="triage.start", persona=PERSONA, signal=_BYPASS_SIGNAL
    )
    assert d.tier is GovernanceTier.human_in_loop
    assert d.permitted is False
    assert "safety_class:high_risk" in d.reasons


def test_sensitive_without_consent_escalates() -> None:
    # appointment.book is sensitive; no consent context -> cannot auto-proceed.
    d = evaluate_signal_action(
        intent="appointment.book", persona=PERSONA, signal=_BYPASS_SIGNAL
    )
    assert d.tier is GovernanceTier.human_in_loop
    assert "consent:absent_for_sensitive" in d.reasons


def test_consent_revoked_halts() -> None:
    consent = project_consent(
        consent_reference="Consent/abc",
        patient_reference="Patient/1",
        is_active=True,
        permitted_purposes=["TREAT"],
        permitted_resource_types=["Appointment"],
        approved_jurisdictions=["INTL"],
        consent_version=1,
    )
    d = evaluate_signal_action(
        intent="appointment.book",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        consent=consent,
        purpose_of_use="TREAT",
        resource_type="Appointment",
        jurisdiction="INTL",
        current_consent_version=2,  # live version moved past projection -> revoked
    )
    assert d.tier is GovernanceTier.halt
    assert d.permitted is False
    assert any(r.startswith("consent:consent_revoked") for r in d.reasons)


def test_break_glass_not_approved_halts() -> None:
    d = evaluate_signal_action(
        intent="triage.start",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        break_glass=True,
        break_glass_category="life_threatening",
        # A non-empty whitelist that EXCLUDES the category. (An empty/None set
        # falls back to bridge_sdk's default emergency whitelist, which permits.)
        emergency=EmergencyOverride(approved=frozenset({"unrelated_category"})),
    )
    assert d.tier is GovernanceTier.halt
    assert "break_glass:not_approved" in d.reasons


def test_break_glass_approved_escalates_not_auto() -> None:
    d = evaluate_signal_action(
        intent="triage.start",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        break_glass=True,
        break_glass_category="life_threatening",
        emergency=EmergencyOverride(approved=frozenset({"life_threatening"})),
    )
    # Break-glass never auto-proceeds; it routes to a blocking review.
    assert d.tier is GovernanceTier.human_in_loop
    assert "break_glass:approved" in d.reasons
    assert d.handoff is not None


def test_budget_saturation_blocks_auto() -> None:
    budget = PersonaExecutionBudget(
        limits=ExecutionBudgetLimits(max_concurrent_workflows=1)
    )
    budget.acquire_workflow(PERSONA)  # fill concurrency -> saturated
    d = evaluate_signal_action(
        intent="dashboard.filter",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        budget=budget,
        manifests=_ROUTINE,
    )
    assert d.tier is GovernanceTier.human_in_loop
    assert "budget:saturated" in d.reasons


def test_safety_case_unapproved_blocks_auto() -> None:
    unapproved = ClinicalSafetyCase(
        persona=PERSONA,
        hazards=[Hazard("H1", "open critical", HazardSeverity.critical, "mitigate")],
    )
    d = evaluate_signal_action(
        intent="dashboard.filter",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        safety_case=unapproved,
        manifests=_ROUTINE,
    )
    assert d.tier is GovernanceTier.human_in_loop
    assert "safety_case:not_approved_for_auto" in d.reasons


def test_safety_case_approved_allows_auto_for_routine() -> None:
    approved = ClinicalSafetyCase(persona=PERSONA, approved_by="cmo")
    d = evaluate_signal_action(
        intent="dashboard.filter",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        safety_case=approved,
        manifests=_ROUTINE,
    )
    assert d.tier is GovernanceTier.auto_on_loop
    assert d.permitted is True


def test_deterministic_same_inputs_same_decision() -> None:
    """The purity property the two-face parity test depends on."""
    kwargs = dict(
        intent="dashboard.filter",
        persona=PERSONA,
        signal=_BYPASS_SIGNAL,
        manifests=_ROUTINE,
    )
    a = evaluate_signal_action(**kwargs)
    b = evaluate_signal_action(**kwargs)
    assert a.to_dict() == b.to_dict()
