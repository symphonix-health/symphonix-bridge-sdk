"""Router reliability suite (WS13): the Cynefin router is safety-critical.

A wrong CLEAR (under-convening) is the failure mode that would bypass
deliberation, so this suite proves the router's safety properties hold
over the WHOLE input space, not just example points:

1. Soundness of clear: clear is reachable ONLY with a deterministic
   basis AND no red flags AND no emergency AND confidence/risk inside
   the clear envelope (FR-CDL-001-AC03, FR-CDL-002-AC02).
2. Emergency dominance: the emergency flag yields chaotic regardless of
   every other input (FR-CDL-009, DP4 never-block).
3. Fail-toward-caution monotonicity: lowering confidence, raising risk,
   adding a red flag, or removing the deterministic basis NEVER moves
   the class toward less caution (FR-CDL-001-AC02).
4. Totality: every valid input classifies; no exception paths.
5. Convene-permission equivalence: deliberate() refuses exactly the
   classes whose cynefin_class.convenes_council is False.

The grid is deterministic (no randomness, no clock) so failures are
reproducible. Caution order: clear < complicated < complex; chaotic is
the emergency-dominance axis and is excluded from the monotone order.

Traceability: BulletTrain/docs/PERSONA_COUNCIL_REQUIREMENTS.md
(FR-CDL-001, FR-CDL-002, FR-CDL-009; router FP/FN analysis section);
matrix UC council_router_props_0009.
"""

from __future__ import annotations

import pytest

from bridge_sdk.council_deliberation import (
    CLEAR_CONFIDENCE_FLOOR,
    CLEAR_RISK_CEILING,
    ConveningError,
    CouncilComposition,
    CynefinClass,
    EquipageCheck,
    MemberEquipage,
    SkillPackCheck,
    ToolHealth,
    deliberate,
    route,
)
from bridge_sdk.superpersona_contract import IntuitionDecision

CAUTION_ORDER = {
    CynefinClass.clear: 0,
    CynefinClass.complicated: 1,
    CynefinClass.complex: 2,
}

# 0.00, 0.05, ..., 1.00 -- integer grid avoids float-step drift.
GRID = [i / 20 for i in range(21)]
COARSE = [i / 4 for i in range(5)]


def _intuition(confidence: float, risk: float) -> IntuitionDecision:
    return IntuitionDecision(
        selected_framework="grid",
        confidence=confidence,
        risk_score=risk,
    )


def _route(conf: float, risk: float, basis: bool, flags: tuple = (), emergency: bool = False):
    return route(
        _intuition(conf, risk),
        deterministic_basis=basis,
        emergency=emergency,
        red_flags=flags,
    )


# ---- 1. Soundness + completeness of clear (FR-CDL-001-AC03, 002-AC02) -----


def test_clear_is_sound_over_the_full_grid() -> None:
    # clear implies: basis AND no flags AND inside the clear envelope.
    for conf in GRID:
        for risk in GRID:
            for basis in (True, False):
                for flags in ((), ("red-flag",)):
                    decision = _route(conf, risk, basis, flags)
                    if decision.cynefin_class is CynefinClass.clear:
                        assert basis, f"clear without basis at conf={conf}"
                        assert not flags, f"clear despite red flag at conf={conf}"
                        assert conf >= CLEAR_CONFIDENCE_FLOOR
                        assert risk <= CLEAR_RISK_CEILING


def test_clear_is_complete_inside_its_envelope() -> None:
    # Inside the envelope with basis and no flags, clear MUST fire --
    # otherwise the fast path silently disappears (an availability FP).
    for conf in GRID:
        for risk in GRID:
            if conf >= CLEAR_CONFIDENCE_FLOOR and risk <= CLEAR_RISK_CEILING:
                decision = _route(conf, risk, True)
                assert decision.cynefin_class is CynefinClass.clear


def test_clear_envelope_boundaries_are_inclusive() -> None:
    assert _route(CLEAR_CONFIDENCE_FLOOR, CLEAR_RISK_CEILING, True).cynefin_class is CynefinClass.clear
    assert _route(CLEAR_CONFIDENCE_FLOOR - 0.01, CLEAR_RISK_CEILING, True).cynefin_class is not CynefinClass.clear
    assert _route(CLEAR_CONFIDENCE_FLOOR, CLEAR_RISK_CEILING + 0.01, True).cynefin_class is not CynefinClass.clear


def test_confidence_alone_never_reaches_clear_anywhere() -> None:
    # FR-CDL-001-AC03 over the whole grid, not just one example.
    for conf in GRID:
        for risk in GRID:
            assert _route(conf, risk, False).cynefin_class is not CynefinClass.clear


# ---- 2. Emergency dominance (FR-CDL-009, DP4) ------------------------------


def test_emergency_dominates_every_other_input() -> None:
    for conf in COARSE:
        for risk in COARSE:
            for basis in (True, False):
                for flags in ((), ("sentinel",)):
                    decision = _route(conf, risk, basis, flags, emergency=True)
                    assert decision.cynefin_class is CynefinClass.chaotic
                    assert decision.disposition_hint == "break_glass_then_shadow_review"


# ---- 3. Fail-toward-caution monotonicity (FR-CDL-001-AC02) -----------------


def test_lower_confidence_never_reduces_caution() -> None:
    for risk in GRID:
        for basis in (True, False):
            previous = None
            # Walk confidence downward; caution must be non-decreasing.
            for conf in reversed(GRID):
                cls = _route(conf, risk, basis).cynefin_class
                if previous is not None:
                    assert CAUTION_ORDER[cls] >= CAUTION_ORDER[previous], (
                        f"caution dropped lowering confidence to {conf} at risk={risk}"
                    )
                previous = cls


def test_higher_risk_never_reduces_caution() -> None:
    for conf in GRID:
        for basis in (True, False):
            previous = None
            for risk in GRID:
                cls = _route(conf, risk, basis).cynefin_class
                if previous is not None:
                    assert CAUTION_ORDER[cls] >= CAUTION_ORDER[previous], (
                        f"caution dropped raising risk to {risk} at conf={conf}"
                    )
                previous = cls


def test_adding_a_red_flag_never_reduces_caution() -> None:
    for conf in GRID:
        for risk in GRID:
            for basis in (True, False):
                plain = _route(conf, risk, basis).cynefin_class
                flagged = _route(conf, risk, basis, ("flag",)).cynefin_class
                assert CAUTION_ORDER[flagged] >= CAUTION_ORDER[plain]
                assert flagged is CynefinClass.complex


def test_removing_deterministic_basis_never_reduces_caution() -> None:
    for conf in GRID:
        for risk in GRID:
            with_basis = _route(conf, risk, True).cynefin_class
            without = _route(conf, risk, False).cynefin_class
            assert CAUTION_ORDER[without] >= CAUTION_ORDER[with_basis]


# ---- 4. Totality + audit record over the grid ------------------------------


def test_router_is_total_and_always_auditable() -> None:
    for conf in COARSE:
        for risk in COARSE:
            for basis in (True, False):
                for flags in ((), ("f",)):
                    for emergency in (False, True):
                        decision = _route(conf, risk, basis, flags, emergency)
                        record = decision.audit_record()
                        assert record["cynefin_class"] in {c.value for c in CynefinClass}
                        assert record["disposition_hint"]


# ---- 5. Convene-permission equivalence (FR-CDL-002-AC01, 009-AC01) ---------


def _minimal_composition() -> CouncilComposition:
    ok = EquipageCheck("terminology", ToolHealth.healthy, True, "1.0")
    pack = SkillPackCheck("core", "1.0", True)
    return CouncilComposition(
        decision_domain="grid",
        seats=(
            MemberEquipage("m1", "lens", "llm", "token://m1", (ok,), (pack,)),
            MemberEquipage("m2", "lens", "rules", "token://m2", (ok,), (pack,), is_safety_seat=True),
        ),
    )


def test_deliberate_permission_equals_convenes_council() -> None:
    comp = _minimal_composition()
    for conf in COARSE:
        for risk in COARSE:
            for basis in (True, False):
                for emergency in (False, True):
                    decision = _route(conf, risk, basis, emergency=emergency)
                    if decision.cynefin_class.convenes_council:
                        continue  # convening proper is covered by the main suite
                    with pytest.raises(ConveningError):
                        deliberate(decision, comp, [])


# ---- Golden clinical regression cases ---------------------------------------


def test_golden_atypical_presentation_does_not_die_on_fast_path() -> None:
    # The external-review case: atypical aortic dissection presenting as
    # indigestion. The model is confident and sees low risk, but NO
    # guideline deterministically covers it -- it must convene.
    decision = _route(0.9, 0.1, basis=False)
    assert decision.cynefin_class is CynefinClass.complicated
    assert decision.cynefin_class.convenes_council


def test_golden_red_flag_overrides_guideline_match() -> None:
    # Guideline matched AND model confident, but a deterministic sentinel
    # (e.g. chest-pain red flag) fired: the fast path is forbidden.
    decision = _route(0.95, 0.05, basis=True, flags=("chest_pain_red_flag",))
    assert decision.cynefin_class is CynefinClass.complex


def test_golden_emergency_with_red_flags_still_breaks_glass() -> None:
    decision = _route(0.1, 0.95, basis=False, flags=("sentinel",), emergency=True)
    assert decision.cynefin_class is CynefinClass.chaotic
