"""Tests for the Agent Execution Ledger (Workstream 2, FR-LE-*/NFR-LE-*).

The hash-chain-alignment test imports BulletTrain's REAL
``bullettrain.who.shared.hash_chain.HashChain`` when importable and asserts the
SDK ledger builds an identical chain for identical inputs, so the two ledger
faces cannot silently diverge. It skips (honestly) only when BulletTrain is not
on the path in the current interpreter.
"""
from __future__ import annotations

import importlib.util
import sys

import pytest

from bridge_sdk.execution_ledger import (
    ExecutionLedger,
    LedgerError,
    WorkflowState,
    is_transition_allowed,
)

TS = "2026-06-01T12:00:00Z"


def _seed_running(ledger: ExecutionLedger, wid: str = "wf-1") -> None:
    ledger.admit(wid, f"{wid}-e0", TS)
    ledger.record(wid, f"{wid}-e1", WorkflowState.running, TS)


def test_admit_opens_workflow_in_admitted_state() -> None:
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    assert led.current_state("wf-1") is WorkflowState.admitted


def test_double_admit_rejected() -> None:
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    with pytest.raises(LedgerError):
        led.admit("wf-1", "e0b", TS)


def test_all_lifecycle_states_present() -> None:
    # FR-LE-002: the agent lifecycle states the plan specifies, PLUS the WS11
    # needs_human_review terminal-but-resumable HITL state (FR-HH-001).
    assert {s.value for s in WorkflowState} == {
        "admitted", "running", "waiting_for_input", "needs_consent", "blocked",
        "compensating", "needs_human_review", "completed", "escalated", "cancelled",
    }


def test_defined_transition_accepted() -> None:
    led = ExecutionLedger()
    _seed_running(led)
    ev = led.record("wf-1", "e2", WorkflowState.waiting_for_input, TS)
    assert ev is not None
    assert led.current_state("wf-1") is WorkflowState.waiting_for_input


def test_undefined_transition_rejected_and_not_recorded() -> None:
    # FR-LE-002-AC01: an undefined transition is rejected and logged (raised).
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)  # admitted
    # admitted -> completed is NOT a defined transition.
    with pytest.raises(LedgerError):
        led.record("wf-1", "e1", WorkflowState.completed, TS)
    assert led.current_state("wf-1") is WorkflowState.admitted  # unchanged


def test_terminal_states_have_no_successor() -> None:
    led = ExecutionLedger()
    _seed_running(led)
    led.record("wf-1", "e2", WorkflowState.completed, TS)
    assert not is_transition_allowed(WorkflowState.completed, WorkflowState.running)
    with pytest.raises(LedgerError):
        led.record("wf-1", "e3", WorkflowState.running, TS)


def test_replay_reconstructs_identical_state_sequence() -> None:
    # FR-LE-001-AC01: replaying the event stream reconstructs identical state.
    led = ExecutionLedger()
    _seed_running(led)
    led.record("wf-1", "e2", WorkflowState.waiting_for_input, TS)
    led.record("wf-1", "e3", WorkflowState.running, TS)
    led.record("wf-1", "e4", WorkflowState.completed, TS)
    assert led.replay("wf-1") == [
        WorkflowState.admitted,
        WorkflowState.running,
        WorkflowState.waiting_for_input,
        WorkflowState.running,
        WorkflowState.completed,
    ]


def test_resume_from_events_after_restart_matches_state() -> None:
    # FR-LE-004-AC01: resume from the last committed event after a restart.
    led = ExecutionLedger()
    _seed_running(led)
    led.record("wf-1", "e2", WorkflowState.waiting_for_input, TS)
    persisted = led.events

    # Simulate a process restart: rebuild purely from persisted events.
    resumed = ExecutionLedger.from_events(persisted)
    assert resumed.current_state("wf-1") is WorkflowState.waiting_for_input
    assert resumed.last_seq("wf-1") == led.last_seq("wf-1")
    # And it continues from exactly where it left off.
    ev = resumed.record("wf-1", "e3", WorkflowState.running, TS)
    assert ev is not None and ev.seq == 3


def test_duplicate_event_injection_is_idempotent() -> None:
    # NFR-LE-001-AC01: re-injecting a committed event_id => no state change.
    led = ExecutionLedger()
    _seed_running(led)
    led.record("wf-1", "dup", WorkflowState.waiting_for_input, TS)
    before = led.replay("wf-1")
    result = led.record("wf-1", "dup", WorkflowState.running, TS)  # same event_id
    assert result is None
    assert led.replay("wf-1") == before
    assert led.health().duplicate_events_ignored == 1


def test_task_view_projects_fhir_status() -> None:
    # FR-LE-001: FHIR Task is the external canonical view.
    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    assert led.task_view("wf-1").fhir_status == "received"
    led.record("wf-1", "e1", WorkflowState.running, TS)
    assert led.task_view("wf-1").fhir_status == "in-progress"
    led.record("wf-1", "e2", WorkflowState.completed, TS)
    assert led.task_view("wf-1").fhir_status == "completed"


def test_all_states_map_to_valid_fhir_task_status() -> None:
    valid = {"draft", "requested", "received", "accepted", "rejected", "ready",
             "cancelled", "in-progress", "on-hold", "failed", "completed",
             "entered-in-error"}
    for s in WorkflowState:
        led = ExecutionLedger()
        led.admit(f"wf-{s.value}", "e0", TS)
        # Walk to the state where reachable; assert mapping is a valid code.
        from bridge_sdk.execution_ledger import _FHIR_TASK_STATUS  # type: ignore
        assert _FHIR_TASK_STATUS[s] in valid


def test_chain_integrity_holds_then_breaks_on_tamper() -> None:
    led = ExecutionLedger()
    _seed_running(led)
    led.record("wf-1", "e2", WorkflowState.completed, TS)
    ok, idx = led.verify_integrity()
    assert ok is True and idx is None

    # Tamper with a committed event's payload; chain must detect it.
    from dataclasses import replace
    led._events[1] = replace(led._events[1], payload={"tampered": True})  # type: ignore
    ok2, idx2 = led.verify_integrity()
    assert ok2 is False and idx2 == 1


def test_health_metrics_queryable() -> None:
    # NFR-LE-002-AC01: lag/stuck/compensation are queryable.
    led = ExecutionLedger()
    _seed_running(led, "wf-a")
    led.record("wf-a", "wf-a-e2", WorkflowState.waiting_for_input, TS)  # stuck
    _seed_running(led, "wf-b")
    led.record("wf-b", "wf-b-e2", WorkflowState.compensating, TS)
    h = led.health()
    assert h.workflows == 2
    assert h.stuck_workflows == 1
    assert h.compensation_count == 1


@pytest.mark.skipif(
    importlib.util.find_spec("bullettrain") is None,
    reason="BulletTrain not importable in this interpreter",
)
def test_sdk_chain_matches_real_bullettrain_hashchain() -> None:
    # The SDK ledger's chain construction must equal BulletTrain's real
    # HashChain for identical inputs, so the two ledger faces never diverge.
    from bullettrain.who.shared.hash_chain import HashChain  # type: ignore

    led = ExecutionLedger()
    led.admit("wf-1", "e0", TS)
    sdk_event = led.events[0]

    chain = HashChain()
    data = {
        "event_id": "e0",
        "workflow_id": "wf-1",
        "to_state": "admitted",
        "payload": {},
    }
    bt_entry = chain.append(data, timestamp=TS)
    assert sdk_event.entry_hash == bt_entry.entry_hash
    assert sdk_event.previous_hash == bt_entry.previous_hash


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
