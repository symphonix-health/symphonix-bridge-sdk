"""Agent Execution Ledger: event-sourced, replayable agent workflow state.

Workstream 2. Gives agents resumable, replayable workflow state instead of
fragile in-page state. Depends on Workstream 1 (the FHIR Task projection comes
from ``agent_contract``).

Design decision (deviation from the plan, justified by the repo). The plan said
"introduce an Agent Execution Ledger". BulletTrain already ships the spine this
needs, so WS2 EXTENDS rather than rebuilds:

- ``services/workflow_orchestrator/main.py:158`` already defines a
  ``WorkflowStatus`` enum (pending/in_progress/completed/failed/cancelled/
  suspended). That is execution-engine state, NOT the agent-clinical lifecycle
  the plan's FR-LE-002 specifies (admitted/running/waiting_for_input/
  needs_consent/blocked/compensating/completed/escalated/cancelled). This module
  adds the agent lifecycle FSM; the BulletTrain ledger service maps it onto the
  existing engine states at the boundary.
- ``bullettrain/who/shared/hash_chain.py`` already provides a production,
  tamper-evident SHA-256 ``HashChain`` (append + verify_integrity). The
  BulletTrain-side ledger service uses THAT directly; this SDK module carries a
  dependency-free, behaviourally-identical chain (same canonical-JSON +
  index:timestamp:data_hash:previous_hash construction) so the ledger is unit-
  testable in any venv and the SDK stays import-light. The two are kept aligned
  by ``test_execution_ledger.py`` asserting the hashing construction.

What is genuinely NEW here and absent from the repo:
- FHIR ``Task`` as the external canonical view of agent workflow state
  (FR-LE-001) -- ABSENT in the repo today.
- Event replay that reconstructs identical state (FR-LE-001-AC01).
- Idempotent duplicate-event handling keyed on ``event_id`` (NFR-LE-001).

Requirements: FR-LE-001..004, NFR-LE-001..002
(``BulletTrain/docs/EXECUTION_LEDGER_REQUIREMENTS.md``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "ExecutionLedger",
    "LedgerError",
    "LedgerEvent",
    "LedgerHealth",
    "TaskState",
    "WorkflowState",
]


class LedgerError(Exception):
    """Raised on an illegal lifecycle transition or a ledger integrity failure."""


class WorkflowState(str, Enum):
    """Agent workflow lifecycle states (plan FR-LE-002).

    Richer than the engine's ``WorkflowStatus`` because agents need clinical
    checkpoints: waiting for input, awaiting consent, blocked, compensating,
    escalated to a human.
    """

    admitted = "admitted"
    running = "running"
    waiting_for_input = "waiting_for_input"
    needs_consent = "needs_consent"
    blocked = "blocked"
    compensating = "compensating"
    needs_human_review = "needs_human_review"  # WS11: terminal-but-resumable HITL
    completed = "completed"
    escalated = "escalated"
    cancelled = "cancelled"


# Allowed transitions. Terminal states (completed/cancelled) have no successors.
_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.admitted: frozenset(
        {WorkflowState.running, WorkflowState.cancelled, WorkflowState.escalated}
    ),
    WorkflowState.running: frozenset(
        {
            WorkflowState.waiting_for_input,
            WorkflowState.needs_consent,
            WorkflowState.blocked,
            WorkflowState.compensating,
            WorkflowState.needs_human_review,
            WorkflowState.completed,
            WorkflowState.escalated,
            WorkflowState.cancelled,
        }
    ),
    WorkflowState.waiting_for_input: frozenset(
        {WorkflowState.running, WorkflowState.escalated, WorkflowState.cancelled}
    ),
    WorkflowState.needs_consent: frozenset(
        {
            WorkflowState.running,
            WorkflowState.blocked,
            WorkflowState.escalated,
            WorkflowState.cancelled,
        }
    ),
    WorkflowState.blocked: frozenset(
        {
            WorkflowState.running,
            WorkflowState.needs_human_review,
            WorkflowState.escalated,
            WorkflowState.cancelled,
        }
    ),
    # WS11: terminal-but-resumable. One-click resume -> running; or cancelled.
    WorkflowState.needs_human_review: frozenset(
        {WorkflowState.running, WorkflowState.cancelled}
    ),
    WorkflowState.compensating: frozenset(
        {WorkflowState.cancelled, WorkflowState.completed, WorkflowState.escalated}
    ),
    WorkflowState.escalated: frozenset(
        {WorkflowState.running, WorkflowState.cancelled, WorkflowState.completed}
    ),
    WorkflowState.completed: frozenset(),
    WorkflowState.cancelled: frozenset(),
}

# FHIR R4 Task.status mapping for the external canonical view (FR-LE-001).
# Values are valid members of the FHIR Task.status value set.
_FHIR_TASK_STATUS: dict[WorkflowState, str] = {
    WorkflowState.admitted: "received",
    WorkflowState.running: "in-progress",
    WorkflowState.waiting_for_input: "on-hold",
    WorkflowState.needs_consent: "on-hold",
    WorkflowState.blocked: "on-hold",
    WorkflowState.compensating: "in-progress",
    WorkflowState.needs_human_review: "on-hold",
    WorkflowState.completed: "completed",
    WorkflowState.escalated: "on-hold",
    WorkflowState.cancelled: "cancelled",
}

_TERMINAL = frozenset({WorkflowState.completed, WorkflowState.cancelled})
_GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class LedgerEvent:
    """One appended event in a workflow's event stream.

    ``entry_hash`` chains to the previous event exactly as
    ``bullettrain/who/shared/hash_chain.py`` does, so the BulletTrain ledger
    service and this SDK produce identical chains for identical inputs.
    """

    seq: int
    event_id: str
    workflow_id: str
    to_state: WorkflowState
    timestamp: str
    payload: dict[str, Any]
    previous_hash: str
    entry_hash: str


@dataclass(frozen=True)
class TaskState:
    """The external canonical FHIR Task view projected from ledger state."""

    workflow_id: str
    state: WorkflowState
    fhir_status: str
    last_seq: int


@dataclass(frozen=True)
class LedgerHealth:
    """Queryable ledger health metrics (NFR-LE-002)."""

    workflows: int
    events: int
    stuck_workflows: int          # in a non-terminal wait state
    compensation_count: int       # events that entered compensating
    duplicate_events_ignored: int


def _data_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_hash(seq: int, timestamp: str, data_hash: str, previous_hash: str) -> str:
    payload = f"{seq}:{timestamp}:{data_hash}:{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_transition_allowed(src: WorkflowState, dst: WorkflowState) -> bool:
    """Whether ``src -> dst`` is a defined lifecycle transition (FR-LE-002)."""
    return dst in _TRANSITIONS.get(src, frozenset())


class ExecutionLedger:
    """An append-only, replayable, idempotent agent-workflow event store.

    State is never stored directly; it is reconstructed by replaying the event
    stream (event sourcing). The same event stream always reconstructs the same
    state (FR-LE-001-AC01). Re-injecting a committed ``event_id`` is a no-op
    (NFR-LE-001).
    """

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._seen_event_ids: set[str] = set()
        self._duplicates_ignored = 0
        self._compensation_count = 0

    # ---- append -------------------------------------------------------

    def admit(
        self, workflow_id: str, event_id: str, timestamp: str,
        payload: dict[str, Any] | None = None,
    ) -> LedgerEvent:
        """Open a new workflow in the ``admitted`` state."""
        if any(e.workflow_id == workflow_id for e in self._events):
            raise LedgerError(f"workflow '{workflow_id}' already admitted")
        return self._append(
            workflow_id, event_id, WorkflowState.admitted, timestamp, payload or {}
        )

    def record(
        self, workflow_id: str, event_id: str, to_state: WorkflowState,
        timestamp: str, payload: dict[str, Any] | None = None,
    ) -> LedgerEvent | None:
        """Record a transition for an existing workflow.

        Returns the appended event, or ``None`` if ``event_id`` was already
        committed (idempotent duplicate, NFR-LE-001). Raises ``LedgerError`` on
        an undefined transition (FR-LE-002-AC01).
        """
        if event_id in self._seen_event_ids:
            self._duplicates_ignored += 1
            return None
        current = self.current_state(workflow_id)
        if current is None:
            raise LedgerError(f"unknown workflow '{workflow_id}'")
        if not is_transition_allowed(current, to_state):
            raise LedgerError(
                f"illegal transition {current.value} -> {to_state.value} "
                f"for workflow '{workflow_id}'"
            )
        return self._append(workflow_id, event_id, to_state, timestamp, payload or {})

    def _append(
        self, workflow_id: str, event_id: str, to_state: WorkflowState,
        timestamp: str, payload: dict[str, Any],
    ) -> LedgerEvent:
        seq = len(self._events)
        previous_hash = self._events[-1].entry_hash if self._events else _GENESIS_HASH
        data = {
            "event_id": event_id,
            "workflow_id": workflow_id,
            "to_state": to_state.value,
            "payload": payload,
        }
        entry_hash = _entry_hash(seq, timestamp, _data_hash(data), previous_hash)
        event = LedgerEvent(
            seq=seq,
            event_id=event_id,
            workflow_id=workflow_id,
            to_state=to_state,
            timestamp=timestamp,
            payload=payload,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        self._events.append(event)
        self._seen_event_ids.add(event_id)
        if to_state is WorkflowState.compensating:
            self._compensation_count += 1
        return event

    # ---- replay / projection -----------------------------------------

    @property
    def events(self) -> list[LedgerEvent]:
        return list(self._events)

    def replay(self, workflow_id: str) -> list[WorkflowState]:
        """Reconstruct a workflow's state sequence by replaying its events."""
        return [e.to_state for e in self._events if e.workflow_id == workflow_id]

    def current_state(self, workflow_id: str) -> WorkflowState | None:
        """The current state, derived purely from the event stream."""
        states = self.replay(workflow_id)
        return states[-1] if states else None

    def last_seq(self, workflow_id: str) -> int:
        seqs = [e.seq for e in self._events if e.workflow_id == workflow_id]
        return seqs[-1] if seqs else -1

    def task_view(self, workflow_id: str) -> TaskState:
        """Project the FHIR Task external canonical view (FR-LE-001)."""
        state = self.current_state(workflow_id)
        if state is None:
            raise LedgerError(f"unknown workflow '{workflow_id}'")
        return TaskState(
            workflow_id=workflow_id,
            state=state,
            fhir_status=_FHIR_TASK_STATUS[state],
            last_seq=self.last_seq(workflow_id),
        )

    # ---- resume / verify / health ------------------------------------

    @classmethod
    def from_events(cls, events: list[LedgerEvent]) -> ExecutionLedger:
        """Rebuild a ledger from a persisted event list (FR-LE-004 resume).

        Used for crash recovery: the process restarts, reads committed events
        from durable storage, and resumes from the last committed event.
        """
        ledger = cls()
        for e in sorted(events, key=lambda x: x.seq):
            ledger._events.append(e)
            ledger._seen_event_ids.add(e.event_id)
            if e.to_state is WorkflowState.compensating:
                ledger._compensation_count += 1
        return ledger

    def verify_integrity(self) -> tuple[bool, int | None]:
        """Verify the hash chain end-to-end (tamper-evident, NFR-LE/audit).

        Returns ``(True, None)`` or ``(False, seq)`` of the first broken link.
        """
        previous_hash = _GENESIS_HASH
        for e in self._events:
            data = {
                "event_id": e.event_id,
                "workflow_id": e.workflow_id,
                "to_state": e.to_state.value,
                "payload": e.payload,
            }
            expected = _entry_hash(e.seq, e.timestamp, _data_hash(data), previous_hash)
            if e.previous_hash != previous_hash or e.entry_hash != expected:
                return (False, e.seq)
            previous_hash = e.entry_hash
        return (True, None)

    def health(self) -> LedgerHealth:
        """Queryable ledger health metrics (NFR-LE-002-AC01)."""
        workflow_ids = {e.workflow_id for e in self._events}
        stuck = 0
        for wid in workflow_ids:
            state = self.current_state(wid)
            if state in {
                WorkflowState.waiting_for_input,
                WorkflowState.needs_consent,
                WorkflowState.blocked,
            }:
                stuck += 1
        return LedgerHealth(
            workflows=len(workflow_ids),
            events=len(self._events),
            stuck_workflows=stuck,
            compensation_count=self._compensation_count,
            duplicate_events_ignored=self._duplicates_ignored,
        )
