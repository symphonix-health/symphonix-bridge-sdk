"""Tests for the clinical safety case + MCP transport guard (WS10, FR-CS-*/NFR-CS-*)."""

from __future__ import annotations

import pytest

from bridge_sdk.clinical_safety_case import (
    AutonomyStage,
    BreakGlassReview,
    ClinicalSafetyCase,
    Hazard,
    HazardSeverity,
    McpTransportError,
    McpTransportGuard,
    SafetyCaseError,
)


def _case(**over) -> ClinicalSafetyCase:
    base = dict(
        persona="triage-intake-agent",
        hazards=[
            Hazard(
                "HAZ-1",
                "under-triage of chest pain",
                HazardSeverity.critical,
                "mandatory red-flag escalation",
                controlled=True,
            ),
        ],
        contraindicated_behaviours=["auto-discharge without clinician sign-off"],
        override_rules=["clinician may override urgency band with reason"],
        rollout_constraints=["shadow >= 10000 decisions before advisory"],
        approved_by="dr-tedam",
    )
    base.update(over)
    return ClinicalSafetyCase(**base)


# ---- FR-CS-001: promotion gated by an approved safety case -------------


def test_shadow_allowed_without_approval() -> None:
    case = _case(approved_by=None)
    assert case.can_promote_to(AutonomyStage.shadow) is True
    case.assert_promotion(AutonomyStage.shadow)  # no raise


def test_promotion_past_shadow_requires_approved_case() -> None:
    # FR-CS-001-AC01: a persona without an approved safety case cannot be
    # promoted past shadow mode.
    case = _case(approved_by=None)
    assert case.can_promote_to(AutonomyStage.advisory) is False
    with pytest.raises(SafetyCaseError):
        case.assert_promotion(AutonomyStage.advisory)


def test_uncontrolled_critical_hazard_blocks_promotion() -> None:
    case = _case(
        hazards=[
            Hazard(
                "HAZ-2",
                "missed sepsis",
                HazardSeverity.critical,
                "screen",
                controlled=False,
            ),
        ]
    )
    assert case.uncontrolled_critical_hazards()
    with pytest.raises(SafetyCaseError):
        case.assert_promotion(AutonomyStage.bounded_auto)


def test_approved_case_promotes() -> None:
    case = _case()
    assert case.is_approved() is True
    case.assert_promotion(AutonomyStage.advisory)  # no raise
    case.assert_promotion(AutonomyStage.bounded_auto)  # no raise


# ---- FR-CS-002: hazard log + mandatory post-event review ---------------


def test_case_carries_hazard_log_linked_to_persona() -> None:
    case = _case()
    assert case.persona == "triage-intake-agent"
    assert case.hazards and case.hazards[0].hazard_id == "HAZ-1"
    assert case.contraindicated_behaviours
    assert case.override_rules


def test_break_glass_review_is_outstanding_until_completed() -> None:
    rv = BreakGlassReview(event_id="BG-1", reason="cardiac arrest")
    assert rv.is_outstanding() is True
    rv.complete_review(reviewer="dr-tedam")
    assert rv.is_outstanding() is False
    assert rv.reviewer == "dr-tedam"


def test_break_glass_review_requires_named_reviewer() -> None:
    rv = BreakGlassReview(event_id="BG-2", reason="emergency")
    with pytest.raises(SafetyCaseError):
        rv.complete_review(reviewer="")


# ---- FR-CS-003 + NFR-CS-002: MCP transport lockdown --------------------


def test_consent_required_and_client_bound() -> None:
    g = McpTransportGuard(granted_scopes=frozenset({"task:execute"}))
    with pytest.raises(McpTransportError) as ei:
        g.check_consent(client_id="client-A", consent_client_id=None)
    assert ei.value.reason == "missing_consent"
    with pytest.raises(McpTransportError) as ei2:
        g.check_consent(client_id="client-A", consent_client_id="client-B")
    assert ei2.value.reason == "consent_client_mismatch"
    g.check_consent(client_id="client-A", consent_client_id="client-A")  # ok


def test_token_passthrough_rejected() -> None:
    g = McpTransportGuard(granted_scopes=frozenset())
    with pytest.raises(McpTransportError) as ei:
        g.reject_token_passthrough(downstream_headers={"Authorization": "Bearer x"})
    assert ei.value.reason == "token_passthrough"
    g.reject_token_passthrough(downstream_headers={"content-type": "application/json"})


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://localhost:8000/admin",  # loopback by name
        "http://127.0.0.1:9000/",  # loopback IP
        "http://10.0.0.5/internal",  # private
        "http://[::1]/",  # ipv6 loopback
    ],
)
def test_ssrf_blocks_internal_targets(url) -> None:
    g = McpTransportGuard(granted_scopes=frozenset())
    with pytest.raises(McpTransportError) as ei:
        g.check_ssrf(url)
    assert ei.value.reason == "ssrf_blocked"


def test_ssrf_allows_public_host() -> None:
    g = McpTransportGuard(granted_scopes=frozenset())
    g.check_ssrf("https://fhir.example.org/Patient/123")  # public hostname, no raise


def test_session_isolation_enforced() -> None:
    g = McpTransportGuard(granted_scopes=frozenset())
    with pytest.raises(McpTransportError) as ei:
        g.check_session_isolation(session_client_id="A", calling_client_id="B")
    assert ei.value.reason == "session_isolation"
    g.check_session_isolation(session_client_id="A", calling_client_id="A")


def test_scope_minimisation_rejects_escalation() -> None:
    g = McpTransportGuard(granted_scopes=frozenset({"task:execute", "api:read"}))
    with pytest.raises(McpTransportError) as ei:
        g.minimise_scopes(frozenset({"task:execute", "api:write"}))
    assert ei.value.reason == "scope_escalation"
    g.minimise_scopes(frozenset({"api:read"}))  # subset, ok
