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

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "HandoffError",
    "HandoffInbox",
    "HandoffPackage",
    "HandoffTrigger",
    "PackageValidationError",
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
    provenance_ref: str               # -> WS4 Provenance record
    audit_chain_ref: str              # -> WS4 audit chain / correlation id
    decision_rationale: str
    recommended_next_action: str
    pre_handoff_state: str            # the WS2 ledger state to resume from
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
    resolution: str | None = None     # resume | amend | cancel
    resumed_to_state: str | None = None


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

    def resume(self, workflow_id: str) -> str:
        """One-click resume; returns the state the workflow resumes to (FR-HH-002).

        Resume fidelity (NFR-HH-001): the returned state equals the package's
        ``pre_handoff_state`` -- the workflow continues from exactly where it
        paused, no data loss, no work repeated.
        """
        entry = self._entry(workflow_id)
        entry.resolved = True
        entry.resolution = "resume"
        entry.resumed_to_state = entry.package.pre_handoff_state
        return entry.resumed_to_state

    def amend(self, workflow_id: str, *, note: str) -> None:
        if not note:
            raise HandoffError("amend requires a note")
        entry = self._entry(workflow_id)
        entry.resolved = True
        entry.resolution = "amend"

    def cancel(self, workflow_id: str, *, reason: str) -> None:
        if not reason:
            raise HandoffError("cancel requires a reason")
        entry = self._entry(workflow_id)
        entry.resolved = True
        entry.resolution = "cancel"

    def resolution_of(self, workflow_id: str) -> str | None:
        return self._entry(workflow_id).resolution

    def _entry(self, workflow_id: str) -> _InboxEntry:
        if workflow_id not in self._entries:
            raise HandoffError(f"workflow '{workflow_id}' not in inbox")
        return self._entries[workflow_id]
