"""Tests for council deliberation (WS13 slice 1, FR-CDL-*).

Traceability: BulletTrain/docs/PERSONA_COUNCIL_REQUIREMENTS.md;
matrix BulletTrain/tests/harness/reduced_json_matrices/council_deliberation_matrix.14col.json.
"""

from __future__ import annotations

import pytest

from bridge_sdk.agent_contract import SafetyClass
from bridge_sdk.council_deliberation import (
    BallotValidationError,
    CompositionError,
    ConveningError,
    CouncilBallot,
    CouncilComposition,
    CouncilError,
    CynefinClass,
    DecisionOption,
    Disposition,
    EquipageCheck,
    HazardChecklistItem,
    MemberEquipage,
    SkillPackCheck,
    ToolHealth,
    WeightRelease,
    blind_spot_cross_scan,
    deliberate,
    dispose,
    route,
    synthesize,
)
from bridge_sdk.superpersona_contract import IntuitionDecision


def _intuition(
    confidence: float = 0.9,
    risk: float = 0.1,
    hypotheses: list[str] | None = None,
    reasons: list[str] | None = None,
) -> IntuitionDecision:
    return IntuitionDecision(
        selected_framework="clinical_reasoning_v1",
        route_salience={"clinical": 0.8},
        candidate_hypotheses=hypotheses or [],
        confidence=confidence,
        risk_score=risk,
        reason_codes=reasons or [],
    )


OPTION_A = DecisionOption(option_id="opt-a", label="Start treatment A")
OPTION_B = DecisionOption(option_id="opt-b", label="Order further imaging")
OPTION_HIGH = DecisionOption(
    option_id="opt-hr",
    label="High-risk intervention",
    safety_class=SafetyClass.high_risk,
)


def _ballot(member: str = "clinical", option: DecisionOption = OPTION_A, **over) -> CouncilBallot:
    base = dict(
        member_id=member,
        option=option,
        confidence=0.8,
        unique_perspective=f"{member} lens perspective",
        blind_spots=(),
        evidence_refs=(f"tool://terminology/{member}/lookup-1",),
        intuition=_intuition(),
    )
    base.update(over)
    return CouncilBallot(**base)


def _tool_ok(tool_id: str = "terminology") -> EquipageCheck:
    return EquipageCheck(
        tool_id=tool_id,
        health=ToolHealth.healthy,
        approved_latest=True,
        version="2.1.0",
    )


def _seat(member: str, *, substrate: str = "llm", safety: bool = False, **over) -> MemberEquipage:
    base = dict(
        member_id=member,
        lens=f"{member}-lens",
        substrate=substrate,
        persona_token_ref=f"token://{member}",
        tool_checks=(_tool_ok(),),
        skill_checks=(SkillPackCheck(pack_id="core-clinical", version="1.0", approved=True),),
        is_safety_seat=safety,
    )
    base.update(over)
    return MemberEquipage(**base)


def _composition(**over) -> CouncilComposition:
    base = dict(
        decision_domain="differential-review",
        seats=(
            _seat("clinical"),
            _seat("pharmacy"),
            _seat("rules-safety", substrate="rules", safety=True),
        ),
        coverage_gaps=(),
    )
    base.update(over)
    return CouncilComposition(**base)


def _routing(cls: CynefinClass = CynefinClass.complicated):
    if cls is CynefinClass.clear:
        return route(_intuition(0.95, 0.05), deterministic_basis=True)
    if cls is CynefinClass.chaotic:
        return route(_intuition(), deterministic_basis=False, emergency=True)
    if cls is CynefinClass.complicated:
        return route(_intuition(0.7, 0.3), deterministic_basis=False)
    return route(_intuition(0.3, 0.8), deterministic_basis=False)


# ---- FR-CDL-001: Cynefin routing -----------------------------------------


def test_clear_requires_deterministic_basis() -> None:
    # FR-CDL-001-AC03: confidence alone is never sufficient for clear.
    decision = route(_intuition(0.99, 0.01), deterministic_basis=False)
    assert decision.cynefin_class is not CynefinClass.clear


def test_clear_with_deterministic_basis_and_low_risk() -> None:
    decision = route(_intuition(0.95, 0.05), deterministic_basis=True)
    assert decision.cynefin_class is CynefinClass.clear
    assert not decision.cynefin_class.convenes_council


def test_unclassifiable_fails_toward_complex() -> None:
    # FR-CDL-001-AC02: disorder routes complex, never clear.
    decision = route(
        _intuition(0.2, 0.9, reasons=["contradictory_records"]),
        deterministic_basis=False,
    )
    assert decision.cynefin_class is CynefinClass.complex


def test_routing_emits_auditable_record() -> None:
    # FR-CDL-001-AC01: inputs + class + disposition reconstructable.
    decision = route(
        _intuition(0.7, 0.3, reasons=["ambiguous_presentation"]),
        deterministic_basis=False,
    )
    record = decision.audit_record()
    assert record["cynefin_class"] == "complicated"
    assert record["inputs"]["confidence"] == 0.7
    assert record["inputs"]["reason_codes"] == ["ambiguous_presentation"]
    assert record["disposition_hint"]


# ---- FR-CDL-002: fast-path guards ----------------------------------------


def test_red_flag_forbids_clear() -> None:
    # FR-CDL-002-AC02: deterministic sentinel rules watch the router.
    decision = route(
        _intuition(0.99, 0.01),
        deterministic_basis=True,
        red_flags=("atypical_presentation_chest_pain",),
    )
    assert decision.cynefin_class is CynefinClass.complex


def test_clear_class_never_convenes() -> None:
    # FR-CDL-002-AC01: zero council events on the fast path.
    with pytest.raises(ConveningError):
        deliberate(_routing(CynefinClass.clear), _composition(), [_ballot()])


# ---- FR-CDL-009: emergency bypass ----------------------------------------


def test_emergency_routes_chaotic_break_glass() -> None:
    decision = route(_intuition(), deterministic_basis=False, emergency=True)
    assert decision.cynefin_class is CynefinClass.chaotic
    assert decision.disposition_hint == "break_glass_then_shadow_review"


def test_chaotic_class_never_convenes_on_critical_path() -> None:
    # FR-CDL-009-AC01.
    with pytest.raises(ConveningError):
        deliberate(_routing(CynefinClass.chaotic), _composition(), [_ballot()])


# ---- FR-CDL-003 + FR-CDL-014: composition and equipage --------------------


def test_missing_safety_seat_fails_validation() -> None:
    # FR-CDL-003-AC01.
    comp = _composition(seats=(_seat("clinical"), _seat("pharmacy", substrate="rules")))
    with pytest.raises(CompositionError, match="safety seat"):
        comp.validate()


def test_all_llm_substrate_fails_validation() -> None:
    # FR-CDL-003-AC03: substrate diversity is mandatory.
    comp = _composition(
        seats=(_seat("clinical"), _seat("pharmacy"), _seat("devil", safety=True)),
    )
    with pytest.raises(CompositionError, match="substrate diversity"):
        comp.validate()


def test_unhealthy_tool_fails_seat() -> None:
    # FR-CDL-014-AC01: unresolved/unhealthy tool surface fails the seat.
    bad = EquipageCheck(
        tool_id="interaction-checker",
        health=ToolHealth.unhealthy,
        approved_latest=True,
        version="2.0.0",
    )
    comp = _composition(
        seats=(
            _seat("clinical"),
            _seat("pharmacy", tool_checks=(bad,)),
            _seat("rules-safety", substrate="rules", safety=True),
        ),
    )
    with pytest.raises(CompositionError, match="interaction-checker"):
        comp.validate()


def test_version_stale_tool_fails_seat() -> None:
    # FR-CDL-014-AC01: approved-latest is required, healthy is not enough.
    stale = EquipageCheck(
        tool_id="terminology",
        health=ToolHealth.healthy,
        approved_latest=False,
        version="1.9.0",
    )
    comp = _composition(
        seats=(
            _seat("clinical", tool_checks=(stale,)),
            _seat("pharmacy"),
            _seat("rules-safety", substrate="rules", safety=True),
        ),
    )
    with pytest.raises(CompositionError, match="approved_latest=False"):
        comp.validate()


def test_missing_persona_token_fails_seat() -> None:
    # FR-CDL-003-AC02.
    comp = _composition(
        seats=(
            _seat("clinical", persona_token_ref=""),
            _seat("pharmacy"),
            _seat("rules-safety", substrate="rules", safety=True),
        ),
    )
    with pytest.raises(CompositionError, match="persona token"):
        comp.validate()


def test_unapproved_skill_pack_fails_seat() -> None:
    comp = _composition(
        seats=(
            _seat(
                "clinical",
                skill_checks=(
                    SkillPackCheck(pack_id="oncology-pack", version="0.9", approved=False),
                ),
            ),
            _seat("pharmacy"),
            _seat("rules-safety", substrate="rules", safety=True),
        ),
    )
    with pytest.raises(CompositionError, match="oncology-pack"):
        comp.validate()


def test_fully_equipped_composition_validates() -> None:
    _composition().validate()


def test_coverage_gap_caps_disposition_at_review() -> None:
    # FR-CDL-014-AC03: a recorded lens gap cannot reach advisory.
    comp = _composition(coverage_gaps=("imaging lens unavailable",))
    ballots = [_ballot("clinical"), _ballot("pharmacy"), _ballot("rules-safety")]
    result = deliberate(_routing(), comp, ballots)
    assert result.disposition is Disposition.needs_human_review
    assert any("coverage gap" in r for r in result.reasons)


# ---- FR-CDL-004: six-field ballot -----------------------------------------


def test_ballot_with_all_six_fields_validates() -> None:
    _ballot().validate()


@pytest.mark.parametrize(
    "over,fragment",
    [
        ({"member_id": ""}, "member_id"),
        ({"unique_perspective": ""}, "unique_perspective"),
        ({"confidence": 1.5}, "confidence"),
        ({"intuition": None}, "intuition"),
        ({"blind_spots": None}, "blind_spots"),
        ({"evidence_refs": None}, "evidence_refs"),
    ],
)
def test_ballot_missing_field_fails(over, fragment) -> None:
    # FR-CDL-004-AC01.
    with pytest.raises(BallotValidationError, match=fragment):
        _ballot(**over).validate()


def test_ballot_grounding_flag() -> None:
    # FR-CDL-004-AC03.
    assert _ballot().is_grounded
    assert not _ballot(evidence_refs=()).is_grounded


def test_ballot_type_carries_no_other_member_output() -> None:
    # FR-CDL-004-AC02 (structural blindness): the ballot type has no field
    # through which another member's ballot could be threaded.
    fields = set(CouncilBallot.__dataclass_fields__)
    assert fields == {
        "member_id",
        "option",
        "confidence",
        "unique_perspective",
        "blind_spots",
        "evidence_refs",
        "intuition",
    }


# ---- FR-CDL-005: hazard checklist + blind-spot cross-scan ------------------


def test_unaddressed_blind_spot_is_uncovered() -> None:
    ballots = [
        _ballot("clinical", blind_spots=("renal dosing unverified",)),
        _ballot("pharmacy"),
    ]
    scan = blind_spot_cross_scan(ballots, ())
    assert "renal dosing unverified" in scan.uncovered_risks


def test_addressed_blind_spot_is_covered() -> None:
    ballots = [
        _ballot("clinical", blind_spots=("renal dosing",)),
        _ballot(
            "pharmacy",
            evidence_refs=("tool://renal-dosing/check-eGFR-ok",),
        ),
    ]
    scan = blind_spot_cross_scan(ballots, ())
    assert "renal dosing" not in scan.uncovered_risks


def test_scan_runs_on_unanimous_consensus() -> None:
    # FR-CDL-005-AC01: unanimity does not skip the scan.
    ballots = [_ballot("clinical"), _ballot("pharmacy")]
    scan = blind_spot_cross_scan(ballots, ())
    assert scan.uncovered_risks == ()
    assert scan.checklist_complete


def test_salience_divergence_flags_single_holder_hypothesis() -> None:
    ballots = [
        _ballot("clinical", intuition=_intuition(hypotheses=["pe", "dissection"])),
        _ballot("pharmacy", intuition=_intuition(hypotheses=["pe"])),
    ]
    scan = blind_spot_cross_scan(ballots, ())
    assert "dissection" in scan.salience_divergence
    assert "pe" not in scan.salience_divergence


def test_tool_available_item_requires_tool_invocation() -> None:
    # FR-CDL-005-AC03: model recall does not satisfy a tool-backed item.
    recall_only = HazardChecklistItem(
        item_id="drug-interactions",
        description="Interaction check",
        tool_available=True,
        satisfied=True,
        satisfied_by=None,
    )
    assert not recall_only.validly_satisfied
    tooled = HazardChecklistItem(
        item_id="drug-interactions",
        description="Interaction check",
        tool_available=True,
        satisfied=True,
        satisfied_by="tool://interaction-checker/run-77",
    )
    assert tooled.validly_satisfied


def test_incomplete_checklist_blocks_advisory() -> None:
    # FR-CDL-005-AC02.
    ballots = [_ballot("clinical"), _ballot("pharmacy"), _ballot("rules-safety")]
    checklist = [
        HazardChecklistItem(
            item_id="allergy",
            description="Allergy reconciliation",
            tool_available=True,
            satisfied=False,
        )
    ]
    result = deliberate(_routing(), _composition(), ballots, checklist)
    assert result.disposition is Disposition.needs_human_review
    assert any("checklist" in r for r in result.reasons)


# ---- FR-CDL-007: weighted synthesis ---------------------------------------


def test_synthesis_winner_and_consensus_share() -> None:
    ballots = [
        _ballot("clinical", OPTION_A, confidence=0.9),
        _ballot("pharmacy", OPTION_A, confidence=0.7),
        _ballot("rules-safety", OPTION_B, confidence=0.4),
    ]
    result = synthesize(ballots)
    assert result.winning_option.option_id == "opt-a"
    expected = (0.9 + 0.7) / (0.9 + 0.7 + 0.4)
    assert result.consensus_level == pytest.approx(expected)
    assert result.disagreeing_members == ("rules-safety",)


def test_weight_release_changes_winner() -> None:
    ballots = [
        _ballot("clinical", OPTION_A, confidence=0.6),
        _ballot("pharmacy", OPTION_B, confidence=0.6),
    ]
    release = WeightRelease(
        version="rlcaf-2026-06",
        weights={"pharmacy": 3.0, "clinical": 1.0},
    )
    result = synthesize(ballots, release)
    assert result.winning_option.option_id == "opt-b"
    assert result.weight_release_version == "rlcaf-2026-06"


def test_ungrounded_ballot_is_downweighted() -> None:
    # FR-CDL-004-AC03 at synthesis time.
    ballots = [
        _ballot("clinical", OPTION_A, confidence=0.8, evidence_refs=()),
        _ballot("pharmacy", OPTION_B, confidence=0.5),
    ]
    result = synthesize(ballots)
    # 0.8 * 0.5 = 0.40 < 0.50: the grounded ballot wins despite lower confidence.
    assert result.winning_option.option_id == "opt-b"
    assert result.ungrounded_members == ("clinical",)


def test_synthesis_is_reproducible_from_inputs() -> None:
    # FR-CDL-007-AC01.
    ballots = [
        _ballot("clinical", OPTION_A, confidence=0.9),
        _ballot("pharmacy", OPTION_B, confidence=0.6),
    ]
    release = WeightRelease(version="w1", weights={"clinical": 1.2})
    first = synthesize(ballots, release)
    second = synthesize(ballots, release)
    assert first == second


def test_synthesis_requires_ballots() -> None:
    with pytest.raises(CouncilError, match="no ballots"):
        synthesize([])


# ---- FR-CDL-008: disposition ----------------------------------------------


def test_confident_consensus_disposes_advisory() -> None:
    ballots = [_ballot("clinical"), _ballot("pharmacy"), _ballot("rules-safety")]
    result = deliberate(_routing(), _composition(), ballots)
    assert result.disposition is Disposition.advisory
    assert result.may_autocommit
    assert result.dissent == ()


def test_contested_consensus_escalates_with_dissent_verbatim() -> None:
    # FR-CDL-008-AC01 + AC02.
    dissenting = _ballot("rules-safety", OPTION_B, confidence=0.9)
    ballots = [
        _ballot("clinical", OPTION_A, confidence=0.7),
        _ballot("pharmacy", OPTION_B, confidence=0.2),
        dissenting,
    ]
    result = deliberate(_routing(), _composition(), ballots)
    assert result.disposition is Disposition.needs_human_review
    assert not result.may_autocommit
    assert any(b == dissenting for b in result.dissent) or any(
        b.option.option_id != result.winning_option.option_id for b in result.dissent
    )


def test_sole_ungrounded_winner_escalates() -> None:
    # FR-CDL-004-AC03: an ungrounded recommendation cannot be the sole basis
    # of an advisory disposition.
    ballots = [
        _ballot("clinical", OPTION_A, confidence=0.95, evidence_refs=()),
        _ballot("pharmacy", OPTION_A, confidence=0.9, evidence_refs=()),
        _ballot("rules-safety", OPTION_B, confidence=0.1),
    ]
    synthesis = synthesize(ballots)
    scan = blind_spot_cross_scan(ballots, ())
    result = dispose(synthesis, scan, _composition(), ballots)
    assert result.disposition is Disposition.needs_human_review
    assert any("no tool-grounded evidence" in r for r in result.reasons)


# ---- FR-CDL-012-AC02: high-risk never auto-commits -------------------------


def test_high_risk_winner_requires_human_signoff_even_unanimous() -> None:
    ballots = [
        _ballot("clinical", OPTION_HIGH),
        _ballot("pharmacy", OPTION_HIGH),
        _ballot("rules-safety", OPTION_HIGH),
    ]
    result = deliberate(_routing(), _composition(), ballots)
    assert result.disposition is Disposition.advisory
    assert result.requires_human_signoff
    assert not result.may_autocommit


def test_routine_advisory_may_autocommit() -> None:
    ballots = [_ballot("clinical"), _ballot("pharmacy"), _ballot("rules-safety")]
    result = deliberate(_routing(), _composition(), ballots)
    assert result.winning_option.safety_class is SafetyClass.routine
    assert result.may_autocommit


# ---- Cross-repo contract: EnsembleVoter parity (FR-CDL-007) ----------------

import importlib.util  # noqa: E402


@pytest.mark.skipif(
    importlib.util.find_spec("bullettrain") is None,
    reason="BulletTrain not importable in this interpreter",
)
def test_synthesis_winner_matches_real_ensemble_voter() -> None:
    # The SDK synthesis generalises EnsembleVoter's weighted-score semantics
    # (score = confidence * weight, aggregated per option, max wins). For an
    # equivalent input under identical explicit weights, the two must pick
    # the same winner, so the council and the diagnostic ensemble never
    # diverge on voting arithmetic.
    from bullettrain.rl.ensemble_manager import EnsembleVoter  # type: ignore
    from bullettrain.rl.ensemble_strategies import StrategyResult  # type: ignore

    def _strategy(name: str, code: str, conf: float) -> StrategyResult:
        return StrategyResult(
            diagnosis_code=code,
            diagnosis_name=f"diagnosis {code}",
            confidence=conf,
            reasoning="parity fixture",
            supporting_evidence=["evidence://fixture"],
            next_tests=[],
            execution_time_ms=1.0,
            strategy_name=name,
        )

    weights = {"clinical": 1.0, "pharmacy": 1.0, "rules-safety": 1.0}
    voter_result = EnsembleVoter().vote(
        {
            "clinical": _strategy("clinical", "J18.9", 0.9),
            "pharmacy": _strategy("pharmacy", "J18.9", 0.7),
            "rules-safety": _strategy("rules-safety", "I26.0", 0.4),
        },
        historical_weights=weights,
        use_rlcaf_weights=False,
    )

    opt_j = DecisionOption(option_id="J18.9", label="Pneumonia, unspecified")
    opt_i = DecisionOption(option_id="I26.0", label="PE with acute cor pulmonale")
    sdk_result = synthesize(
        [
            _ballot("clinical", opt_j, confidence=0.9),
            _ballot("pharmacy", opt_j, confidence=0.7),
            _ballot("rules-safety", opt_i, confidence=0.4),
        ],
        WeightRelease(version="parity-1.0", weights=weights),
    )

    assert voter_result.final_diagnosis_code == sdk_result.winning_option.option_id
