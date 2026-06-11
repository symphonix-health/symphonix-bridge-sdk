"""Tests for human handoff + deferred HITL (WS11, FR-HH-*/NFR-HH-*)."""

from __future__ import annotations

import pytest

from bridge_sdk.execution_ledger import (
    ExecutionLedger,
    LedgerError,
    WorkflowState,
    is_transition_allowed,
)
from bridge_sdk.human_handoff import (
    HandoffError,
    HandoffInbox,
    HandoffPackage,
    HandoffTrigger,
    OutcomeTally,
    PackageValidationError,
    ReviewerOutcome,
    summarise_outcomes,
)

TS = "2026-06-02T12:00:00Z"


def _package(**over) -> HandoffPackage:
    base = dict(
        workflow_id="wf-1",
        trigger=HandoffTrigger.consent_conflict,
        task_summary="Triage paused: consent conflict on lab access.",
        provenance_ref="Provenance/p-1",
        audit_chain_ref="case-2026-06-02-00042",
        decision_rationale="Active consent does not permit lab disclosure.",
        recommended_next_action="Clinician to confirm consent scope, then resume.",
        pre_handoff_state="running",
        pending_inputs=["updated consent scope"],
    )
    base.update(over)
    return HandoffPackage(**base)


# ---- FR-HH-001: needs_human_review is terminal-but-resumable -----------


def test_ledger_has_needs_human_review_state() -> None:
    assert WorkflowState.needs_human_review.value == "needs_human_review"


def test_running_can_enter_needs_human_review() -> None:
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    led.record("wf-1", "e1", WorkflowState.running, TS)
    ev = led.record("wf-1", "e2", WorkflowState.needs_human_review, TS)
    assert ev is not None
    assert led.current_state("wf-1") is WorkflowState.needs_human_review


def test_needs_human_review_is_resumable_to_running() -> None:
    # FR-HH-001: terminal-but-RESUMABLE -> the only forward moves are running
    # (one-click resume) or cancelled.
    assert is_transition_allowed(
        WorkflowState.needs_human_review, WorkflowState.running
    )
    assert is_transition_allowed(
        WorkflowState.needs_human_review, WorkflowState.cancelled
    )
    # Not, e.g., straight to completed.
    assert not is_transition_allowed(
        WorkflowState.needs_human_review, WorkflowState.completed
    )


def test_resume_from_needs_human_review_continues_workflow() -> None:
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    led.record("wf-1", "e1", WorkflowState.running, TS)
    led.record("wf-1", "e2", WorkflowState.needs_human_review, TS)
    ev = led.record("wf-1", "e3", WorkflowState.running, TS)  # resume
    assert ev is not None
    led.record("wf-1", "e4", WorkflowState.completed, TS)
    assert led.current_state("wf-1") is WorkflowState.completed


def test_illegal_jump_out_of_needs_human_review_rejected() -> None:
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    led.record("wf-1", "e1", WorkflowState.running, TS)
    led.record("wf-1", "e2", WorkflowState.needs_human_review, TS)
    with pytest.raises(LedgerError):
        led.record("wf-1", "e3", WorkflowState.completed, TS)


# ---- FR-HH-002: Handoff Inbox one-click resume -------------------------


def test_inbox_enqueue_and_one_click_resume() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    assert len(inbox.pending()) == 1
    resumed_state = inbox.resume("wf-1")
    assert resumed_state == "running"  # resumes to exact pre-handoff state
    assert inbox.pending() == []
    assert inbox.resolution_of("wf-1") == "resume"


def test_inbox_amend_and_cancel_resolutions() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package(workflow_id="wf-a"))
    inbox.enqueue(_package(workflow_id="wf-b"))
    inbox.amend("wf-a", note="corrected dosage")
    inbox.cancel("wf-b", reason="duplicate referral")
    assert inbox.resolution_of("wf-a") == "amend"
    assert inbox.resolution_of("wf-b") == "cancel"
    assert inbox.pending() == []


def test_amend_requires_note_and_cancel_requires_reason() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    with pytest.raises(HandoffError):
        inbox.amend("wf-1", note="")
    with pytest.raises(HandoffError):
        inbox.cancel("wf-1", reason="")


# ---- FR-HH-003: package validation -------------------------------------


@pytest.mark.parametrize(
    "missing",
    [
        "task_summary",
        "provenance_ref",
        "audit_chain_ref",
        "decision_rationale",
        "recommended_next_action",
    ],
)
def test_package_missing_required_element_fails(missing) -> None:
    pkg = _package(**{missing: ""})
    with pytest.raises(PackageValidationError):
        pkg.validate()
    # And the inbox refuses to enqueue an invalid package.
    with pytest.raises(PackageValidationError):
        HandoffInbox().enqueue(pkg)


def test_complete_package_carries_all_review_context() -> None:
    pkg = _package()
    d = pkg.to_dict()
    assert d["task_summary"]
    assert d["provenance_ref"] == "Provenance/p-1"
    assert d["audit_chain_ref"] == "case-2026-06-02-00042"
    assert d["decision_rationale"]
    assert d["recommended_next_action"]
    assert d["pending_inputs"] == ["updated consent scope"]


# ---- FR-HH-004: deterministic triggers ---------------------------------


@pytest.mark.parametrize(
    "trigger",
    [
        HandoffTrigger.triage_edge_case,
        HandoffTrigger.consent_conflict,
        HandoffTrigger.contradictory_records,
        HandoffTrigger.booking_failure,
    ],
)
def test_each_trigger_creates_a_routable_package(trigger) -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package(workflow_id=f"wf-{trigger.value}", trigger=trigger))
    pkg = inbox.get(f"wf-{trigger.value}")
    assert pkg.trigger is trigger


# ---- NFR-HH-001: resume fidelity ---------------------------------------


def test_resume_fidelity_returns_exact_pre_handoff_state() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package(workflow_id="wf-x", pre_handoff_state="waiting_for_input"))
    assert inbox.resume("wf-x") == "waiting_for_input"


def test_double_enqueue_rejected() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    with pytest.raises(HandoffError):
        inbox.enqueue(_package())


# ---- reviewer rubric grade (measurement backlog item 3) ----------------


def test_grade_is_recorded_and_distinct_from_disposition() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    inbox.resume("wf-1", outcome=ReviewerOutcome.correct)
    assert inbox.resolution_of("wf-1") == "resume"  # what reviewer did
    assert inbox.outcome_of("wf-1") is ReviewerOutcome.correct  # the rubric grade


def test_grade_can_be_set_independently_of_a_disposition() -> None:
    # Grading a sampled action for calibration: no resume/amend/cancel needed.
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    inbox.grade("wf-1", ReviewerOutcome.unsafe)
    assert inbox.outcome_of("wf-1") is ReviewerOutcome.unsafe
    assert inbox.resolution_of("wf-1") is None  # disposition untouched


def test_ungraded_workflow_returns_none() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    assert inbox.outcome_of("wf-1") is None


def test_amend_and_cancel_accept_a_grade() -> None:
    inbox = HandoffInbox()
    inbox.enqueue(_package())
    inbox.amend("wf-1", note="fixed scope", outcome=ReviewerOutcome.incorrect_harmless)
    assert inbox.outcome_of("wf-1") is ReviewerOutcome.incorrect_harmless


def test_reviewer_outcome_unsafe_and_correct_flags() -> None:
    assert ReviewerOutcome.unsafe.is_unsafe is True
    assert ReviewerOutcome.correct.is_correct is True
    assert ReviewerOutcome.correct_suboptimal.is_unsafe is False


def test_summarise_outcomes_yields_scorecard_rates() -> None:
    grades = [
        ReviewerOutcome.correct,
        ReviewerOutcome.correct,
        ReviewerOutcome.correct_suboptimal,
        ReviewerOutcome.incorrect_harmless,
        ReviewerOutcome.unsafe,
    ]
    tally = summarise_outcomes(grades)
    assert isinstance(tally, OutcomeTally)
    assert tally.total == 5
    assert tally.correct == 2
    assert tally.unsafe == 1
    assert tally.correct_rate == pytest.approx(0.4)
    assert tally.unsafe_rate == pytest.approx(0.2)
    # error_rate = unsafe + incorrect-but-harmless.
    assert tally.error_rate == pytest.approx(0.4)


def test_summarise_empty_is_zero_not_division_error() -> None:
    tally = summarise_outcomes([])
    assert tally.total == 0
    assert tally.unsafe_rate == 0.0
    assert tally.correct_rate == 0.0
