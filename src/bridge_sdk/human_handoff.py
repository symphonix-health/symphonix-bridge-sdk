"""Human handoff + deferred HITL: needs_human_review + Handoff Inbox package.

Workstream 11. Deferred HITL with deterministic triggers, not removal of human
oversight. Depends on WS2 (ledger) and WS4 (audit).

Design decision: EXTEND my own WS2 ledger + WS4 audit, don't duplicate.
- WS2 `ExecutionLedger` has a 9-state FSM that deliberately did NOT include
  `needs_human_review` (WS2 scoped to the plan's WS2 list). WS11 adds that state
  + its transitions to the ledger (FR-HH-001) -- a clean extension of code I own.
- WS4 `StepAuditRecords` already carries the provenance + audit chain a handoff
  package must include; the package references it rather than re-deriving it.

What is genuinely NEW (FR-HH-*): the `needs_human_review` terminal-but-resumable
state, the `HandoffPackage` (task summary, provenance ref, audit-chain ref,
decision rationale, pending inputs, recommended next action), the `HandoffInbox`
with one-click resume, and resume-fidelity (resumes from the EXACT pre-handoff
state with no data loss).

Requirements: FR-HH-001..004, NFR-HH-001
(``BulletTrain/docs/HUMAN_HANDOFF_REQUIREMENTS.md``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "HandoffError",
    "HandoffInbox",
    "HandoffPackage",
    "HandoffTrigger",
    "OutcomeTally",
    "PackageValidationError",
    "ReceiverObserverEvidence",
    "ReviewerOutcome",
    "summarise_outcomes",
]


class HandoffError(Exception):
    """Base error for handoff/HITL violations."""


class PackageValidationError(HandoffError):
    """Raised when a handoff package is missing a required element (FR-HH-003)."""


class HandoffTrigger(str, Enum):
    """Deterministic triggers that route a workflow to the inbox (FR-HH-004)."""

    triage_edge_case = "triage_edge_case"
    consent_conflict = "consent_conflict"
    contradictory_records = "contradictory_records"
    booking_failure = "booking_failure"
    low_confidence = "low_confidence"
    policy_block = "policy_block"


class ReviewerOutcome(str, Enum):
    """The four-class reviewer rubric grade for an agent step.

    This is the measurement-framework rubric (see
    ``BulletTrain/docs/AGENT_NATIVE_MEASUREMENT_AND_EVALUATION.md``). It is
    DISTINCT from the inbox disposition (resume / amend / cancel): the
    disposition records what the reviewer DID; the grade records whether the
    agent was right. Reviewer disagreement, unsafe-action, rework, subgroup
    parity, and calibration KPIs all depend on this grade.
    """

    unsafe = "unsafe"  # unsafe had it executed; blocker
    incorrect_harmless = "incorrect_harmless"  # wrong, but no harm
    correct_suboptimal = "correct_suboptimal"  # right outcome, poor path
    correct = "correct"  # safe, correct, appropriate

    @property
    def is_unsafe(self) -> bool:
        return self is ReviewerOutcome.unsafe

    @property
    def is_correct(self) -> bool:
        return self is ReviewerOutcome.correct


@dataclass(frozen=True)
class OutcomeTally:
    """Aggregate reviewer grades into the rates the scorecard reports."""

    total: int
    unsafe: int
    incorrect_harmless: int
    correct_suboptimal: int
    correct: int

    @property
    def unsafe_rate(self) -> float:
        """Share graded unsafe -- the release blocker; target near zero."""
        return self.unsafe / self.total if self.total else 0.0

    @property
    def correct_rate(self) -> float:
        """Share graded fully correct -- the task-success proxy."""
        return self.correct / self.total if self.total else 0.0

    @property
    def error_rate(self) -> float:
        """Share graded wrong (unsafe + incorrect-but-harmless) -- feeds rework."""
        wrong = self.unsafe + self.incorrect_harmless
        return wrong / self.total if self.total else 0.0


def summarise_outcomes(outcomes: Iterable[ReviewerOutcome]) -> OutcomeTally:
    """Tally a set of reviewer grades for the correctness / safety KPIs."""
    items = list(outcomes)
    return OutcomeTally(
        total=len(items),
        unsafe=sum(1 for o in items if o is ReviewerOutcome.unsafe),
        incorrect_harmless=sum(
            1 for o in items if o is ReviewerOutcome.incorrect_harmless
        ),
        correct_suboptimal=sum(
            1 for o in items if o is ReviewerOutcome.correct_suboptimal
        ),
        correct=sum(1 for o in items if o is ReviewerOutcome.correct),
    )


@dataclass(frozen=True)
class ReceiverObserverEvidence:
    """Evidence that the receiving observer can safely resume a handed-off task."""

    receiver_ref: str
    evidence_ref: str
    accessible: bool = True
    permitted: bool = True
    attested: bool = True

    def validate(self) -> None:
        missing = [
            field_name
            for field_name in ("receiver_ref", "evidence_ref")
            if not getattr(self, field_name)
        ]
        if missing:
            raise HandoffError(f"receiver observer evidence missing: {missing}")
        if not self.accessible:
            raise HandoffError("receiver observer evidence is not accessible")
        if not self.permitted:
            raise HandoffError("receiver observer evidence is not permitted")
        if not self.attested:
            raise HandoffError("receiver observer evidence is not attested")

    def to_dict(self) -> dict[str, Any]:
        return {
            "receiver_ref": self.receiver_ref,
            "evidence_ref": self.evidence_ref,
            "accessible": self.accessible,
            "permitted": self.permitted,
            "attested": self.attested,
        }


# Required elements of a handoff package (FR-HH-003). A package missing any of
# these fails validation -- a clinician must never get a half-empty handoff.
_REQUIRED_PACKAGE_FIELDS: tuple[str, ...] = (
    "task_summary",
    "provenance_ref",
    "audit_chain_ref",
    "decision_rationale",
    "recommended_next_action",
)


@dataclass(frozen=True)
class HandoffPackage:
    """The package a clinician/ops reviewer receives (FR-HH-003).

    ``provenance_ref`` / ``audit_chain_ref`` are references to the WS4 records
    (not copies). ``pre_handoff_state`` is the ledger state to resume from, so
    resume fidelity is exact (NFR-HH-001).
    """

    workflow_id: str
    trigger: HandoffTrigger
    task_summary: str
    provenance_ref: str  # -> WS4 Provenance record
    audit_chain_ref: str  # -> WS4 audit chain / correlation id
    decision_rationale: str
    recommended_next_action: str
    pre_handoff_state: str  # the WS2 ledger state to resume from
    pending_inputs: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Raise ``PackageValidationError`` if any required element is empty."""
        missing = [f for f in _REQUIRED_PACKAGE_FIELDS if not getattr(self, f)]
        if missing:
            raise PackageValidationError(
                f"handoff package for '{self.workflow_id}' missing: {missing}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "trigger": self.trigger.value,
            "task_summary": self.task_summary,
            "provenance_ref": self.provenance_ref,
            "audit_chain_ref": self.audit_chain_ref,
            "decision_rationale": self.decision_rationale,
            "recommended_next_action": self.recommended_next_action,
            "pre_handoff_state": self.pre_handoff_state,
            "pending_inputs": list(self.pending_inputs),
        }


@dataclass
class _InboxEntry:
    package: HandoffPackage
    resolved: bool = False
    resolution: str | None = None  # resume | amend | cancel (the disposition)
    resumed_to_state: str | None = None
    reviewer_outcome: ReviewerOutcome | None = None  # the 4-class rubric grade
    receiver_observer_evidence: ReceiverObserverEvidence | None = None


class HandoffInbox:
    """A minimal Handoff Inbox with one-click resume (FR-HH-002).

    Backs the provider-portal + Command Centre inbox UI. A handed-off task is
    enqueued with its package; a reviewer resumes it in one action and the
    workflow continues from the EXACT pre-handoff state (NFR-HH-001).
    """

    def __init__(self) -> None:
        self._entries: dict[str, _InboxEntry] = {}

    def enqueue(self, package: HandoffPackage) -> None:
        """Add a handed-off task. Validates the package first (FR-HH-003)."""
        package.validate()
        if package.workflow_id in self._entries:
            raise HandoffError(f"workflow '{package.workflow_id}' already in inbox")
        self._entries[package.workflow_id] = _InboxEntry(package=package)

    def pending(self) -> list[HandoffPackage]:
        return [e.package for e in self._entries.values() if not e.resolved]

    def get(self, workflow_id: str) -> HandoffPackage:
        if workflow_id not in self._entries:
            raise HandoffError(f"workflow '{workflow_id}' not in inbox")
        return self._entries[workflow_id].package

    def resume(
        self,
        workflow_id: str,
        *,
        receiver_observer_evidence: ReceiverObserverEvidence | None = None,
        outcome: ReviewerOutcome | None = None,
    ) -> str:
        """One-click resume; returns the state the workflow resumes to (FR-HH-002).

        Resume fidelity (NFR-HH-001): the returned state equals the package's
        ``pre_handoff_state`` -- the workflow continues from exactly where it
        paused, no data loss, no work repeated. ``receiver_observer_evidence``
        proves the receiving observer has admitted evidence for the resume
        action. ``outcome`` optionally records the reviewer's four-class rubric
        grade alongside the disposition.
        """
        entry = self._entry(workflow_id)
        if receiver_observer_evidence is None:
            raise HandoffError("resume requires receiver observer evidence")
        receiver_observer_evidence.validate()
        entry.resolved = True
        entry.resolution = "resume"
        entry.resumed_to_state = entry.package.pre_handoff_state
        entry.receiver_observer_evidence = receiver_observer_evidence
        if outcome is not None:
            entry.reviewer_outcome = outcome
        return entry.resumed_to_state

    def amend(
        self, workflow_id: str, *, note: str, outcome: ReviewerOutcome | None = None
    ) -> None:
        if not note:
            raise HandoffError("amend requires a note")
        entry = self._entry(workflow_id)
        entry.resolved = True
        entry.resolution = "amend"
        if outcome is not None:
            entry.reviewer_outcome = outcome

    def cancel(
        self, workflow_id: str, *, reason: str, outcome: ReviewerOutcome | None = None
    ) -> None:
        if not reason:
            raise HandoffError("cancel requires a reason")
        entry = self._entry(workflow_id)
        entry.resolved = True
        entry.resolution = "cancel"
        if outcome is not None:
            entry.reviewer_outcome = outcome

    def resolution_of(self, workflow_id: str) -> str | None:
        """The disposition (resume / amend / cancel) -- what the reviewer DID."""
        return self._entry(workflow_id).resolution

    def grade(self, workflow_id: str, outcome: ReviewerOutcome) -> None:
        """Record the four-class rubric grade -- whether the agent was right.

        Distinct from the disposition; can be set independently of resume/amend/
        cancel (e.g. when grading a sampled action for the calibration KPI).
        """
        self._entry(workflow_id).reviewer_outcome = outcome

    def outcome_of(self, workflow_id: str) -> ReviewerOutcome | None:
        """The reviewer's rubric grade for a workflow, or None if ungraded."""
        return self._entry(workflow_id).reviewer_outcome

    def receiver_observer_evidence_of(
        self, workflow_id: str
    ) -> ReceiverObserverEvidence | None:
        return self._entry(workflow_id).receiver_observer_evidence

    def _entry(self, workflow_id: str) -> _InboxEntry:
        if workflow_id not in self._entries:
            raise HandoffError(f"workflow '{workflow_id}' not in inbox")
        return self._entries[workflow_id]
