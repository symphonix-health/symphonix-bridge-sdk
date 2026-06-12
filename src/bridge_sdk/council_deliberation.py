"""Council deliberation: Cynefin-routed multi-superpersona decision contract.

Workstream 13 (proposed), slice 1. A council seat is a duty, not a prompt:
decisions are routed by complexity (clear / complicated / complex / chaotic),
only complicated and complex convene a council, members are seated only fully
equipped (tools resolved approved-latest and healthy, skill packs current, a
per-member intuition pass), round-1 ballots are blind and evidence-grounded,
synthesis is weighted voting over typed decision options, and contested or
under-equipped convenings escalate to needs_human_review rather than advise.

Design decision: EXTEND, don't duplicate.
- ``EnsembleVoter`` (BulletTrain ``bullettrain/rl/ensemble_manager.py:344``)
  votes among reasoning STRATEGIES keyed on ``diagnosis_code``. This module
  generalises the ballot option to a typed ``DecisionOption`` and the voter
  population to council members; the weighted-score + consensus + disagreement
  semantics are preserved so the two can be reconciled.
- ``IntuitionDecision`` (``bridge_sdk.superpersona_contract``) is REUSED twice:
  as the router input and as the per-member intuition pass inside each ballot.
- ``SafetyClass`` (``bridge_sdk.agent_contract``) is REUSED for the high-risk
  never-autonomous rule.
- WS6 EmergencyOverride, WS11 HandoffPackage, WS4 audit, WS2 ledger are
  composed by callers; chaotic-class refusal here is the contract hook.

Slice 1 implements: FR-CDL-001, 002 (routing contract incl. red-flag screen),
003, 014 (composition + equipage), 004 (six-field ballot), 005 (hazard
checklist + cross-scan), 007 (weighted synthesis), 008 (disposition),
009 (chaotic no-convene guard), 012-AC02 (high-risk never auto-commits).
OUT of slice 1 (still proposed): FR-CDL-006 (debate round), 010 (governance
emission wiring), 011 (RLCAF re-weighting governance), 013 (injection
defence at orchestration layer).

Requirements: ``BulletTrain/docs/PERSONA_COUNCIL_REQUIREMENTS.md``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from bridge_sdk.agent_contract import SafetyClass
from bridge_sdk.superpersona_contract import IntuitionDecision

__all__ = [
    "BallotValidationError",
    "CompositionError",
    "ConveningError",
    "CouncilBallot",
    "CouncilComposition",
    "CouncilError",
    "CynefinClass",
    "DecisionOption",
    "Disposition",
    "DispositionResult",
    "EquipageCheck",
    "HazardChecklistItem",
    "MemberEquipage",
    "RoutingDecision",
    "SkillPackCheck",
    "SynthesisResult",
    "ToolHealth",
    "WeightRelease",
    "blind_spot_cross_scan",
    "deliberate",
    "dispose",
    "route",
    "synthesize",
]

# Routing thresholds. Initial values; tuned during WS12 shadow per the
# router FP/FN analysis in the requirements doc (FN budget ~0, FP tunable).
CLEAR_CONFIDENCE_FLOOR = 0.85
CLEAR_RISK_CEILING = 0.2
COMPLICATED_CONFIDENCE_FLOOR = 0.5
COMPLICATED_RISK_CEILING = 0.6
# Weight multiplier applied to a ballot with no evidence_refs (FR-CDL-004-AC03).
UNGROUNDED_WEIGHT_FACTOR = 0.5
# Minimum weighted share of the vote the winning option needs for advisory.
DEFAULT_CONSENSUS_THRESHOLD = 0.7


class CouncilError(Exception):
    """Base error for council deliberation contract violations."""


class CompositionError(CouncilError):
    """Raised when a council composition fails equipage or seating rules."""


class BallotValidationError(CouncilError):
    """Raised when a ballot is missing one of the six required fields."""


class ConveningError(CouncilError):
    """Raised when a convening is attempted for a class that must not convene."""


class CynefinClass(str, Enum):
    """Complexity class assigned by the router (FR-CDL-001)."""

    clear = "clear"
    complicated = "complicated"
    complex = "complex"
    chaotic = "chaotic"

    @property
    def convenes_council(self) -> bool:
        return self in (CynefinClass.complicated, CynefinClass.complex)


@dataclass(frozen=True)
class RoutingDecision:
    """Auditable routing record (FR-CDL-001-AC01): inputs, class, disposition."""

    cynefin_class: CynefinClass
    confidence: float
    risk_score: float
    reason_codes: tuple[str, ...]
    deterministic_basis: bool
    emergency: bool
    red_flags: tuple[str, ...]
    disposition_hint: str

    def audit_record(self) -> dict[str, object]:
        """Every routing decision is reconstructable from this record."""
        return {
            "cynefin_class": self.cynefin_class.value,
            "inputs": {
                "confidence": self.confidence,
                "risk_score": self.risk_score,
                "reason_codes": list(self.reason_codes),
                "deterministic_basis": self.deterministic_basis,
                "emergency": self.emergency,
                "red_flags": list(self.red_flags),
            },
            "disposition_hint": self.disposition_hint,
        }


def route(
    intuition: IntuitionDecision,
    *,
    deterministic_basis: bool,
    emergency: bool = False,
    red_flags: Sequence[str] = (),
) -> RoutingDecision:
    """Classify a candidate decision into a Cynefin class (FR-CDL-001/002/009).

    - Emergency routes chaotic: break-glass path, the council never blocks it
      (FR-CDL-009; Design Principle 4).
    - A present red flag (deterministic sentinel rules watching the router,
      FR-CDL-002-AC02) forbids clear regardless of confidence.
    - Clear REQUIRES a deterministic basis (guideline/rule-engine match,
      FR-CDL-001-AC03); IntuitionDecision confidence alone is never enough.
    - Anything unclassifiable fails toward complex, never clear
      (FR-CDL-001-AC02).
    """
    flags = tuple(red_flags)
    confidence = intuition.confidence
    risk = intuition.risk_score
    reasons = tuple(intuition.reason_codes)

    if emergency:
        cls, hint = CynefinClass.chaotic, "break_glass_then_shadow_review"
    elif flags:
        cls, hint = CynefinClass.complex, "council_debate_red_flag"
    elif (
        deterministic_basis
        and confidence >= CLEAR_CONFIDENCE_FLOOR
        and risk <= CLEAR_RISK_CEILING
    ):
        cls, hint = CynefinClass.clear, "single_agent_fast_path"
    elif (
        confidence >= COMPLICATED_CONFIDENCE_FLOOR
        and risk <= COMPLICATED_RISK_CEILING
    ):
        cls, hint = CynefinClass.complicated, "council_advisory"
    else:
        # Disorder / high-risk / low-confidence: the cautious branch.
        cls, hint = CynefinClass.complex, "council_debate"

    return RoutingDecision(
        cynefin_class=cls,
        confidence=confidence,
        risk_score=risk,
        reason_codes=reasons,
        deterministic_basis=deterministic_basis,
        emergency=emergency,
        red_flags=flags,
        disposition_hint=hint,
    )


class ToolHealth(str, Enum):
    """Composition-time health of a member's bound tool surface."""

    healthy = "healthy"
    unhealthy = "unhealthy"
    unresolved = "unresolved"


@dataclass(frozen=True)
class EquipageCheck:
    """Resolution result for one ToolBinding at composition time (FR-CDL-014)."""

    tool_id: str
    health: ToolHealth
    approved_latest: bool
    version: str

    @property
    def passes(self) -> bool:
        return self.health is ToolHealth.healthy and self.approved_latest


@dataclass(frozen=True)
class SkillPackCheck:
    """Resolution result for one SkillPackRef at composition time."""

    pack_id: str
    version: str
    approved: bool


@dataclass(frozen=True)
class MemberEquipage:
    """A seated member's full equipage: tools, skills, token, substrate."""

    member_id: str
    lens: str
    substrate: str  # e.g. "llm", "rules", "bayesian"
    persona_token_ref: str
    tool_checks: tuple[EquipageCheck, ...] = ()
    skill_checks: tuple[SkillPackCheck, ...] = ()
    is_safety_seat: bool = False

    def equipage_failures(self) -> list[str]:
        failures: list[str] = []
        if not self.persona_token_ref:
            failures.append(f"{self.member_id}: no scoped persona token")
        for check in self.tool_checks:
            if not check.passes:
                failures.append(
                    f"{self.member_id}: tool {check.tool_id} "
                    f"{check.health.value}, approved_latest={check.approved_latest}"
                )
        for pack in self.skill_checks:
            if not pack.approved:
                failures.append(
                    f"{self.member_id}: skill pack {pack.pack_id} not approved"
                )
        return failures


@dataclass
class CouncilComposition:
    """The seated council for one convening (FR-CDL-003, FR-CDL-014)."""

    decision_domain: str
    seats: tuple[MemberEquipage, ...]
    coverage_gaps: tuple[str, ...] = ()

    def validate(self) -> None:
        """Fail-closed seating rules.

        - FR-CDL-003-AC01: the standing devil's-advocate-and-safety seat is
          mandatory; a convening without it fails validation.
        - FR-CDL-003-AC02: every seat carries a scoped persona token.
        - FR-CDL-003-AC03: at least one seat uses a non-LLM substrate.
        - FR-CDL-014-AC01: every seat is fully equipped (tools healthy at
          approved-latest, skill packs approved).
        """
        if not self.seats:
            raise CompositionError("a council requires at least one seat")
        if not any(seat.is_safety_seat for seat in self.seats):
            raise CompositionError(
                "standing devil's-advocate-and-safety seat is missing"
            )
        if not any(seat.substrate != "llm" for seat in self.seats):
            raise CompositionError(
                "substrate diversity violated: every seat is llm-substrate"
            )
        failures = [f for seat in self.seats for f in seat.equipage_failures()]
        if failures:
            raise CompositionError("; ".join(failures))


@dataclass(frozen=True)
class DecisionOption:
    """A typed decision option -- the generalisation of diagnosis_code."""

    option_id: str
    label: str
    safety_class: SafetyClass = SafetyClass.routine
    action_intent: str | None = None


@dataclass(frozen=True)
class CouncilBallot:
    """One member's round-1 opinion: the six-field structured ballot.

    Round-1 blindness (FR-CDL-004-AC02) is structural: the ballot type has
    no field through which another member's output could be carried, and the
    orchestrator must not include other ballots in round-1 prompts.
    """

    member_id: str
    option: DecisionOption
    confidence: float
    unique_perspective: str
    blind_spots: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    intuition: IntuitionDecision

    def validate(self) -> None:
        """FR-CDL-004-AC01: a ballot missing any of the six fields fails."""
        if not self.member_id:
            raise BallotValidationError("ballot missing member_id")
        if self.option is None or not self.option.option_id:
            raise BallotValidationError("ballot missing recommendation option")
        if not 0.0 <= self.confidence <= 1.0:
            raise BallotValidationError(
                f"ballot confidence out of range: {self.confidence}"
            )
        if not self.unique_perspective:
            raise BallotValidationError("ballot missing unique_perspective")
        if self.blind_spots is None:
            raise BallotValidationError("ballot missing blind_spots")
        if self.evidence_refs is None:
            raise BallotValidationError("ballot missing evidence_refs")
        if self.intuition is None:
            raise BallotValidationError("ballot missing intuition pass")

    @property
    def is_grounded(self) -> bool:
        """FR-CDL-004-AC03: a recommendation must cite tool-derived evidence."""
        return bool(self.evidence_refs)


@dataclass(frozen=True)
class HazardChecklistItem:
    """One domain hazard check (FR-CDL-005).

    FR-CDL-005-AC03: where a registry tool exists for the item
    (``tool_available``), satisfaction REQUIRES a recorded tool invocation
    (``satisfied_by``); model recall does not satisfy it.
    """

    item_id: str
    description: str
    tool_available: bool
    satisfied: bool
    satisfied_by: str | None = None

    @property
    def validly_satisfied(self) -> bool:
        if not self.satisfied:
            return False
        if self.tool_available and not self.satisfied_by:
            return False
        return True


@dataclass(frozen=True)
class BlindSpotScan:
    """Cross-scan output (FR-CDL-005): runs even on unanimous consensus."""

    uncovered_risks: tuple[str, ...]
    salience_divergence: tuple[str, ...]
    checklist_complete: bool
    unsatisfied_items: tuple[str, ...]


def _normalize(text: str) -> str:
    """Lower-case and collapse separators so 'renal dosing' matches
    'tool://renal-dosing/check'. Deterministic; no stemming or fuzziness."""
    return "".join(c if c.isalnum() else " " for c in text.lower())


def blind_spot_cross_scan(
    ballots: Sequence[CouncilBallot],
    checklist: Sequence[HazardChecklistItem],
) -> BlindSpotScan:
    """Cross-reference declared blind spots and intuition salience (FR-CDL-005).

    - A declared blind spot is UNCOVERED unless some OTHER member's evidence
      or perspective addresses it (separator-normalised containment,
      case-insensitive).
    - A candidate hypothesis appearing in exactly ONE member's intuition pass
      is salience divergence: a candidate blind spot for everyone else.
    - Checklist items invalid per FR-CDL-005-AC03 block advisory disposition
      (enforced in dispose()).
    """
    uncovered: list[str] = []
    for ballot in ballots:
        others = [b for b in ballots if b.member_id != ballot.member_id]
        for spot in ballot.blind_spots:
            needle = " ".join(_normalize(spot).split())
            addressed = any(
                needle in " ".join(_normalize(ref).split())
                for other in others
                for ref in (*other.evidence_refs, other.unique_perspective)
            )
            if not addressed and spot not in uncovered:
                uncovered.append(spot)

    hypothesis_holders: dict[str, set[str]] = {}
    for ballot in ballots:
        for hyp in ballot.intuition.candidate_hypotheses:
            hypothesis_holders.setdefault(hyp, set()).add(ballot.member_id)
    divergence = tuple(
        hyp for hyp, holders in hypothesis_holders.items() if len(holders) == 1
    )

    unsatisfied = tuple(
        item.item_id for item in checklist if not item.validly_satisfied
    )
    return BlindSpotScan(
        uncovered_risks=tuple(uncovered),
        salience_divergence=divergence,
        checklist_complete=not unsatisfied,
        unsatisfied_items=unsatisfied,
    )


@dataclass(frozen=True)
class WeightRelease:
    """A versioned member-weight release (FR-CDL-011 hook, slice-1 minimal).

    Weights are regulated parameters: callers obtain them from a gated
    release, never from live mutation. ``model_versions`` binds each weight
    to the member substrate version it was learned against.
    """

    version: str
    weights: Mapping[str, float] = field(default_factory=dict)
    model_versions: Mapping[str, str] = field(default_factory=dict)

    def weight_for(self, member_id: str) -> float:
        return float(self.weights.get(member_id, 1.0))


@dataclass(frozen=True)
class SynthesisResult:
    """Weighted synthesis over typed options (FR-CDL-007).

    Reproducible from (ballots, weight release) alone: pure arithmetic,
    no randomness, no clock (FR-CDL-007-AC01).
    """

    winning_option: DecisionOption
    consensus_level: float
    option_scores: Mapping[str, float]
    disagreeing_members: tuple[str, ...]
    ungrounded_members: tuple[str, ...]
    weight_release_version: str


def synthesize(
    ballots: Sequence[CouncilBallot],
    weight_release: WeightRelease | None = None,
) -> SynthesisResult:
    """Weighted vote generalising EnsembleVoter semantics (FR-CDL-007).

    Score per option = sum over its ballots of confidence * member weight,
    with ungrounded ballots down-weighted (FR-CDL-004-AC03). Consensus level
    is the winning option's share of the total weighted score, mirroring
    ``EnsembleVoter._calculate_consensus``'s agreement-share semantics.
    """
    if not ballots:
        raise CouncilError("no ballots to synthesize")
    release = weight_release or WeightRelease(version="unweighted-1.0")

    for ballot in ballots:
        ballot.validate()

    option_scores: dict[str, float] = {}
    options_by_id: dict[str, DecisionOption] = {}
    for ballot in ballots:
        weight = release.weight_for(ballot.member_id)
        if not ballot.is_grounded:
            weight *= UNGROUNDED_WEIGHT_FACTOR
        score = ballot.confidence * weight
        option_scores[ballot.option.option_id] = (
            option_scores.get(ballot.option.option_id, 0.0) + score
        )
        options_by_id[ballot.option.option_id] = ballot.option

    winner_id = max(option_scores, key=lambda oid: option_scores[oid])
    total = sum(option_scores.values())
    consensus = option_scores[winner_id] / total if total else 0.0
    disagreeing = tuple(
        b.member_id for b in ballots if b.option.option_id != winner_id
    )
    ungrounded = tuple(b.member_id for b in ballots if not b.is_grounded)

    return SynthesisResult(
        winning_option=options_by_id[winner_id],
        consensus_level=consensus,
        option_scores=dict(option_scores),
        disagreeing_members=disagreeing,
        ungrounded_members=ungrounded,
        weight_release_version=release.version,
    )


class Disposition(str, Enum):
    """How a convening concludes (FR-CDL-008)."""

    advisory = "advisory"
    needs_human_review = "needs_human_review"


@dataclass(frozen=True)
class DispositionResult:
    """The convening's outcome, dissent preserved verbatim (FR-CDL-008-AC02)."""

    disposition: Disposition
    consensus_level: float
    winning_option: DecisionOption
    dissent: tuple[CouncilBallot, ...]
    uncovered_risks: tuple[str, ...]
    requires_human_signoff: bool
    reasons: tuple[str, ...]

    @property
    def may_autocommit(self) -> bool:
        """FR-CDL-008-AC01 + FR-CDL-012-AC02: contested or high-risk never
        auto-commits; advisory itself still requires clinician sign-off for
        high-risk options."""
        return (
            self.disposition is Disposition.advisory
            and not self.requires_human_signoff
        )


def dispose(
    synthesis: SynthesisResult,
    scan: BlindSpotScan,
    composition: CouncilComposition,
    ballots: Sequence[CouncilBallot],
    *,
    consensus_threshold: float = DEFAULT_CONSENSUS_THRESHOLD,
) -> DispositionResult:
    """Disposition: consensus advises, contention escalates (FR-CDL-008)."""
    reasons: list[str] = []

    if composition.coverage_gaps:
        reasons.append(
            "lens coverage gap: " + ", ".join(composition.coverage_gaps)
        )
    if not scan.checklist_complete:
        reasons.append(
            "hazard checklist incomplete: " + ", ".join(scan.unsatisfied_items)
        )
    if synthesis.consensus_level < consensus_threshold:
        reasons.append(
            f"contested: consensus {synthesis.consensus_level:.2f} "
            f"< threshold {consensus_threshold:.2f}"
        )
    winner_backers = [
        b
        for b in ballots
        if b.option.option_id == synthesis.winning_option.option_id
    ]
    if winner_backers and all(not b.is_grounded for b in winner_backers):
        reasons.append("winning option has no tool-grounded evidence")

    disposition = (
        Disposition.needs_human_review if reasons else Disposition.advisory
    )
    dissent = tuple(
        b
        for b in ballots
        if b.option.option_id != synthesis.winning_option.option_id
    )
    high_risk = synthesis.winning_option.safety_class is SafetyClass.high_risk
    requires_signoff = high_risk or disposition is Disposition.needs_human_review

    return DispositionResult(
        disposition=disposition,
        consensus_level=synthesis.consensus_level,
        winning_option=synthesis.winning_option,
        dissent=dissent,
        uncovered_risks=scan.uncovered_risks,
        requires_human_signoff=requires_signoff,
        reasons=tuple(reasons),
    )


def deliberate(
    routing: RoutingDecision,
    composition: CouncilComposition,
    ballots: Sequence[CouncilBallot],
    checklist: Iterable[HazardChecklistItem] = (),
    weight_release: WeightRelease | None = None,
    *,
    consensus_threshold: float = DEFAULT_CONSENSUS_THRESHOLD,
) -> DispositionResult:
    """One convening: validate seating, scan, synthesize, dispose.

    Refuses classes that must not convene: clear runs the single-agent
    fast-path with zero council events (FR-CDL-002-AC01); chaotic runs
    break-glass with the council shadow-only and never on the critical
    path (FR-CDL-009-AC01).
    """
    if routing.cynefin_class is CynefinClass.clear:
        raise ConveningError(
            "clear-class decisions do not convene a council "
            "(single-agent fast-path, FR-CDL-002)"
        )
    if routing.cynefin_class is CynefinClass.chaotic:
        raise ConveningError(
            "chaotic-class decisions break-glass first; the council is "
            "shadow-only and never blocks the emergency path (FR-CDL-009)"
        )
    composition.validate()
    scan = blind_spot_cross_scan(tuple(ballots), tuple(checklist))
    synthesis = synthesize(ballots, weight_release)
    return dispose(
        synthesis,
        scan,
        composition,
        ballots,
        consensus_threshold=consensus_threshold,
    )
