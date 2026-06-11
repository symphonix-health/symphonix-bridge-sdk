"""Reference workflow rollout + scale-out: shadow mode + governance-ladder promotion.

Workstream 12 (capstone). Proves the full contract on one reference workflow,
then propagates it across the sibling portfolio. Depends on ALL preceding
workstreams -- it composes them rather than adding new primitives.

Composition (reuse, never reinvent):
- WS1 `AgentActionManifest` -- the typed intents an onboarded sibling must expose.
- WS7 `ReleaseGate` / `RunMetrics` -- the metric thresholds a workflow must beat.
- WS10 `ClinicalSafetyCase` / `AutonomyStage` -- the safety-case promotion gate.

What WS12 adds: a `ShadowRunner` (observe + propose, NEVER commit -- FR-RO-001), a
`PromotionOrchestrator` that advances a workflow up the governance ladder
(shadow -> advisory -> bounded_auto) ONLY when BOTH the Arena release gate and the
clinical safety case pass (FR-RO-002), and a `SiblingOnboarding` record that
propagates the contract by reusing shared middleware rather than per-app
reimplementation (FR-RO-003 / NFR-RO-001).

Requirements: FR-RO-001..003, NFR-RO-001..002
(``BulletTrain/docs/ROLLOUT_REQUIREMENTS.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bridge_sdk.agent_arena import ReleaseGate, RunMetrics
from bridge_sdk.clinical_safety_case import AutonomyStage, ClinicalSafetyCase

__all__ = [
    "OnboardingError",
    "PromotionOrchestrator",
    "PromotionRejected",
    "RolloutError",
    "ShadowProposal",
    "ShadowRunner",
    "SiblingOnboarding",
]

# The shared-middleware capabilities every onboarded sibling reuses (NFR-RO-001).
# Reusing these -- rather than re-implementing per app -- is what keeps onboarding
# bounded. The names map to the WS1-11 modules.
REQUIRED_SHARED_CAPABILITIES: tuple[str, ...] = (
    "agent_contract",  # WS1 AgentActionManifest
    "execution_ledger",  # WS2
    "persona_delegation",  # WS3
    "agent_audit",  # WS4
    "error_envelope",  # WS5
    "consent_projection",  # WS9
    "human_handoff",  # WS11
)

# Ladder ordering (mirrors clinical_safety_case._STAGE_ORDER).
_LADDER = [AutonomyStage.shadow, AutonomyStage.advisory, AutonomyStage.bounded_auto]


class RolloutError(Exception):
    """Base error for rollout/scale-out violations."""


class PromotionRejected(RolloutError):
    """Raised when a promotion attempt fails a gate; names the failing criteria."""

    def __init__(self, stage: str, failing: list[str]) -> None:
        self.stage = stage
        self.failing = failing
        super().__init__(f"promotion to '{stage}' rejected: {failing}")


class OnboardingError(RolloutError):
    """Raised when a sibling onboarding is missing a shared capability."""


@dataclass(frozen=True)
class ShadowProposal:
    """A proposal a shadow agent emits -- observed, never committed (FR-RO-001)."""

    workflow_id: str
    proposed_action: str
    committed: bool = False  # ALWAYS False in shadow mode; asserted by the runner

    def __post_init__(self) -> None:
        if self.committed:
            raise RolloutError("shadow proposals must never be committed")


class ShadowRunner:
    """Runs a reference agent in shadow mode: observe + propose, NO commit.

    Every action becomes a `ShadowProposal` with ``committed=False``; the runner
    refuses to mark anything committed. This is the FR-RO-001 guarantee -- the
    shadow agent writes zero production changes.
    """

    def __init__(self, workflow_id: str) -> None:
        self._workflow_id = workflow_id
        self._proposals: list[ShadowProposal] = []

    def propose(self, action: str) -> ShadowProposal:
        p = ShadowProposal(workflow_id=self._workflow_id, proposed_action=action)
        self._proposals.append(p)
        return p

    @property
    def proposals(self) -> list[ShadowProposal]:
        return list(self._proposals)

    def production_writes(self) -> int:
        """Always 0 in shadow mode (FR-RO-001-AC01)."""
        return sum(1 for p in self._proposals if p.committed)


class PromotionOrchestrator:
    """Advance a workflow up the governance ladder, gated by BOTH WS7 + WS10.

    A promotion to advisory or bounded_auto requires:
    - the WS7 Arena `ReleaseGate` to PASS on the latest metrics, AND
    - the WS10 `ClinicalSafetyCase` to permit the target stage.
    Either failure rejects the promotion and NAMES the failing criteria
    (FR-RO-002-AC01). Shadow is always permitted (the starting rung).
    """

    def __init__(
        self, *, release_gate: ReleaseGate, safety_case: ClinicalSafetyCase
    ) -> None:
        self._gate = release_gate
        self._safety = safety_case

    def can_promote(
        self, *, to_stage: AutonomyStage, metrics: RunMetrics
    ) -> tuple[bool, list[str]]:
        """Return (allowed, failing_criteria) without raising."""
        if to_stage is AutonomyStage.shadow:
            return (True, [])
        failing: list[str] = []
        gate_decision = self._gate.evaluate(metrics)
        if not gate_decision.promoted:
            failing.extend(f"arena:{c}" for c in gate_decision.failing_criteria)
        if not self._safety.can_promote_to(to_stage):
            if not self._safety.approved_by:
                failing.append("safety:no_approved_case")
            for h in self._safety.uncontrolled_critical_hazards():
                failing.append(f"safety:open_critical:{h.hazard_id}")
        return (not failing, failing)

    def promote(
        self, *, current: AutonomyStage, to_stage: AutonomyStage, metrics: RunMetrics
    ) -> AutonomyStage:
        """Promote one rung up the ladder, or raise ``PromotionRejected``.

        Enforces single-step, forward-only promotion (no skipping rungs) AND the
        combined gate.
        """
        ci, ti = _LADDER.index(current), _LADDER.index(to_stage)
        if ti != ci + 1:
            raise RolloutError(
                f"promotion must be one rung forward: {current.value} -> {to_stage.value}"
            )
        allowed, failing = self.can_promote(to_stage=to_stage, metrics=metrics)
        if not allowed:
            raise PromotionRejected(to_stage.value, failing)
        return to_stage


@dataclass
class SiblingOnboarding:
    """Propagate the contract to a sibling by reusing shared middleware (FR-RO-003).

    Onboarding is bounded (NFR-RO-001): a sibling declares which shared
    capabilities it wires; it must wire ALL `REQUIRED_SHARED_CAPABILITIES` and may
    not fork/reimplement them. A missing capability fails closed.
    """

    sibling: str
    wired_capabilities: set[str] = field(default_factory=set)
    reimplemented: set[str] = field(default_factory=set)  # forbidden; must stay empty

    def missing(self) -> list[str]:
        return [
            c for c in REQUIRED_SHARED_CAPABILITIES if c not in self.wired_capabilities
        ]

    def validate(self) -> None:
        """Raise ``OnboardingError`` on a missing or forked capability."""
        miss = self.missing()
        if miss:
            raise OnboardingError(
                f"sibling '{self.sibling}' missing shared capabilities: {miss}"
            )
        if self.reimplemented:
            raise OnboardingError(
                f"sibling '{self.sibling}' must REUSE shared middleware, not "
                f"reimplement: {sorted(self.reimplemented)}"
            )

    def is_bounded(self) -> bool:
        """True iff onboarding reused everything and forked nothing (NFR-RO-001)."""
        return not self.missing() and not self.reimplemented

    def to_dict(self) -> dict[str, Any]:
        return {
            "sibling": self.sibling,
            "wired_capabilities": sorted(self.wired_capabilities),
            "missing": self.missing(),
            "bounded": self.is_bounded(),
        }
