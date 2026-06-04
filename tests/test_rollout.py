"""Tests for rollout + scale-out (WS12, FR-RO-*/NFR-RO-*).

Composes the REAL WS7 ReleaseGate and WS10 ClinicalSafetyCase -- no mocks of
either gate.
"""
from __future__ import annotations

import pytest

from bridge_sdk.agent_arena import ReleaseGate, RunMetrics
from bridge_sdk.clinical_safety_case import (
    AutonomyStage,
    ClinicalSafetyCase,
    Hazard,
    HazardSeverity,
)
from bridge_sdk.rollout import (
    REQUIRED_SHARED_CAPABILITIES,
    OnboardingError,
    PromotionOrchestrator,
    PromotionRejected,
    RolloutError,
    ShadowRunner,
    SiblingOnboarding,
)


def _clean_metrics() -> RunMetrics:
    # A workflow that beats every release threshold.
    return RunMetrics(
        task_success=1.0,
        path_optimality=1.0,
        unsafe_action_rate=0.0,
        permission_breach_rate=0.0,
        consent_breach_rate=0.0,
        human_handoff_rate=0.0,
        mean_steps_vs_golden=1.0,
    )


def _weak_metrics() -> RunMetrics:
    return RunMetrics(
        task_success=0.5,          # below 0.90
        path_optimality=0.3,
        unsafe_action_rate=0.2,    # above 0.0
        permission_breach_rate=0.0,
        consent_breach_rate=0.0,
        human_handoff_rate=0.1,
        mean_steps_vs_golden=3.0,  # above 2.0
    )


def _approved_case() -> ClinicalSafetyCase:
    return ClinicalSafetyCase(
        persona="eclaims-prior-auth-agent",
        hazards=[Hazard("HAZ-1", "wrong payer", HazardSeverity.critical, "verify", True)],
        approved_by="dr-tedam",
    )


def _unapproved_case() -> ClinicalSafetyCase:
    return ClinicalSafetyCase(persona="eclaims-prior-auth-agent", approved_by=None)


# ---- FR-RO-001: shadow mode, no production writes ----------------------

def test_shadow_runner_never_commits() -> None:
    runner = ShadowRunner("wf-claim-1")
    runner.propose("claim.submit")
    runner.propose("claim.submit")
    assert len(runner.proposals) == 2
    assert all(not p.committed for p in runner.proposals)
    assert runner.production_writes() == 0  # FR-RO-001-AC01


def test_shadow_proposal_cannot_be_committed() -> None:
    from bridge_sdk.rollout import ShadowProposal
    with pytest.raises(RolloutError):
        ShadowProposal(workflow_id="w", proposed_action="x", committed=True)


# ---- FR-RO-002: promotion gated by BOTH Arena + safety case ------------

def test_promote_succeeds_when_both_gates_pass() -> None:
    orch = PromotionOrchestrator(
        release_gate=ReleaseGate(), safety_case=_approved_case(),
    )
    allowed, failing = orch.can_promote(
        to_stage=AutonomyStage.advisory, metrics=_clean_metrics(),
    )
    assert allowed is True and failing == []
    result = orch.promote(
        current=AutonomyStage.shadow, to_stage=AutonomyStage.advisory,
        metrics=_clean_metrics(),
    )
    assert result is AutonomyStage.advisory


def test_promote_blocked_when_arena_metrics_fail() -> None:
    orch = PromotionOrchestrator(
        release_gate=ReleaseGate(), safety_case=_approved_case(),
    )
    with pytest.raises(PromotionRejected) as ei:
        orch.promote(
            current=AutonomyStage.shadow, to_stage=AutonomyStage.advisory,
            metrics=_weak_metrics(),
        )
    # FR-RO-002-AC01: failing criteria named (arena-prefixed).
    assert any(c.startswith("arena:") for c in ei.value.failing)


def test_promote_blocked_when_safety_case_unapproved() -> None:
    orch = PromotionOrchestrator(
        release_gate=ReleaseGate(), safety_case=_unapproved_case(),
    )
    with pytest.raises(PromotionRejected) as ei:
        orch.promote(
            current=AutonomyStage.shadow, to_stage=AutonomyStage.advisory,
            metrics=_clean_metrics(),
        )
    assert "safety:no_approved_case" in ei.value.failing


def test_promote_blocked_by_open_critical_hazard() -> None:
    case = ClinicalSafetyCase(
        persona="p",
        hazards=[Hazard("HAZ-9", "missed sepsis", HazardSeverity.critical, "screen", False)],
        approved_by="dr-tedam",
    )
    orch = PromotionOrchestrator(release_gate=ReleaseGate(), safety_case=case)
    with pytest.raises(PromotionRejected) as ei:
        orch.promote(
            current=AutonomyStage.shadow, to_stage=AutonomyStage.advisory,
            metrics=_clean_metrics(),
        )
    assert any("open_critical:HAZ-9" in c for c in ei.value.failing)


def test_promotion_must_be_single_rung_forward() -> None:
    orch = PromotionOrchestrator(
        release_gate=ReleaseGate(), safety_case=_approved_case(),
    )
    # shadow -> bounded_auto skips advisory.
    with pytest.raises(RolloutError):
        orch.promote(
            current=AutonomyStage.shadow, to_stage=AutonomyStage.bounded_auto,
            metrics=_clean_metrics(),
        )


def test_shadow_always_allowed() -> None:
    orch = PromotionOrchestrator(
        release_gate=ReleaseGate(), safety_case=_unapproved_case(),
    )
    allowed, failing = orch.can_promote(
        to_stage=AutonomyStage.shadow, metrics=_weak_metrics(),
    )
    assert allowed is True and failing == []


# ---- FR-RO-003 / NFR-RO-001: bounded sibling onboarding ----------------

def test_onboarding_requires_all_shared_capabilities() -> None:
    ob = SiblingOnboarding(
        sibling="pharmacy-system",
        wired_capabilities=set(REQUIRED_SHARED_CAPABILITIES),
    )
    ob.validate()  # no raise
    assert ob.is_bounded() is True


def test_onboarding_missing_capability_fails() -> None:
    partial = set(REQUIRED_SHARED_CAPABILITIES) - {"consent_projection"}
    ob = SiblingOnboarding(sibling="pharmacy-system", wired_capabilities=partial)
    with pytest.raises(OnboardingError):
        ob.validate()
    assert "consent_projection" in ob.missing()


def test_onboarding_rejects_reimplementation() -> None:
    # NFR-RO-001: reuse shared middleware, never fork it per app.
    ob = SiblingOnboarding(
        sibling="pharmacy-system",
        wired_capabilities=set(REQUIRED_SHARED_CAPABILITIES),
        reimplemented={"execution_ledger"},
    )
    with pytest.raises(OnboardingError):
        ob.validate()
    assert ob.is_bounded() is False


def test_required_capabilities_cover_ws1_through_ws11() -> None:
    # The shared middleware a sibling reuses spans the foundational + safety WS.
    assert set(REQUIRED_SHARED_CAPABILITIES) == {
        "agent_contract", "execution_ledger", "persona_delegation",
        "agent_audit", "error_envelope", "consent_projection", "human_handoff",
    }
