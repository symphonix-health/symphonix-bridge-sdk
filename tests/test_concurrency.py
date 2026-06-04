"""Tests for concurrency/budgets/isolation (Workstream 6, FR-CC-*/NFR-CC-*)."""
from __future__ import annotations

import threading

import pytest

from bridge_sdk.concurrency import (
    BudgetExceeded,
    ConcurrencyError,
    EmergencyOverride,
    ExecutionBudgetLimits,
    PersonaExecutionBudget,
    SingleWriterConflict,
    SingleWriterLock,
    Urgency,
    UrgencyQueue,
)


# ---- FR-CC-001: per-persona execution budgets --------------------------

def test_concurrent_workflow_budget_blocks_over_limit() -> None:
    b = PersonaExecutionBudget(ExecutionBudgetLimits(max_concurrent_workflows=2))
    b.acquire_workflow("p1")
    b.acquire_workflow("p1")
    with pytest.raises(BudgetExceeded):
        b.acquire_workflow("p1")
    # Release frees a slot.
    b.release_workflow("p1")
    b.acquire_workflow("p1")  # ok again


def test_budget_is_per_persona_not_global() -> None:
    b = PersonaExecutionBudget(ExecutionBudgetLimits(max_concurrent_workflows=1))
    b.acquire_workflow("p1")
    b.acquire_workflow("p2")  # different persona, own budget
    with pytest.raises(BudgetExceeded):
        b.acquire_workflow("p1")


@pytest.mark.parametrize(
    "charge,dimension,limits",
    [
        (lambda b: b.charge_action("p", 200), "max_screen_actions_per_min",
         ExecutionBudgetLimits(max_screen_actions_per_min=120)),
        (lambda b: b.charge_tokens("p", 300_000), "max_model_tokens",
         ExecutionBudgetLimits(max_model_tokens=200_000)),
        (lambda b: b.charge_write("p", 100), "max_downstream_writes",
         ExecutionBudgetLimits(max_downstream_writes=50)),
    ],
)
def test_each_budget_dimension_blocks(charge, dimension, limits) -> None:
    b = PersonaExecutionBudget(limits)
    with pytest.raises(BudgetExceeded) as ei:
        charge(b)
    assert ei.value.dimension == dimension


def test_unresolved_escalation_budget() -> None:
    b = PersonaExecutionBudget(ExecutionBudgetLimits(max_unresolved_escalations=1))
    b.open_escalation("p")
    with pytest.raises(BudgetExceeded):
        b.open_escalation("p")
    b.resolve_escalation("p")
    b.open_escalation("p")  # resolving frees the slot


def test_saturation_reports_breaches() -> None:
    b = PersonaExecutionBudget(ExecutionBudgetLimits(max_concurrent_workflows=1))
    b.acquire_workflow("p")
    with pytest.raises(BudgetExceeded):
        b.acquire_workflow("p")
    sat = b.saturation("p")
    assert sat["concurrent_workflows"] == 1
    assert sat["breaches"] == 1


# ---- FR-CC-002: single-writer for mutable patient workflows ------------

def test_single_writer_blocks_second_writer() -> None:
    lock = SingleWriterLock()
    lock.acquire("wf-1", holder="agent-A")
    with pytest.raises(SingleWriterConflict):
        lock.acquire("wf-1", holder="agent-B")
    assert lock.holder("wf-1") == "agent-A"


def test_single_writer_reentrant_for_same_holder() -> None:
    lock = SingleWriterLock()
    lock.acquire("wf-1", holder="agent-A")
    lock.acquire("wf-1", holder="agent-A")  # same holder, no conflict
    lock.release("wf-1", holder="agent-A")
    lock.acquire("wf-1", holder="agent-B")  # now free


def test_single_writer_concurrent_race_yields_one_winner() -> None:
    # NFR-CC-001: a real concurrency race resolves to one consistent outcome.
    lock = SingleWriterLock()
    winners: list[str] = []
    barrier = threading.Barrier(8)

    def contend(name: str) -> None:
        barrier.wait()
        try:
            lock.acquire("wf-hot", holder=name)
            winners.append(name)
        except SingleWriterConflict:
            pass

    threads = [threading.Thread(target=contend, args=(f"a{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(winners) == 1  # exactly one writer won


# ---- FR-CC-003: urgency queue + emergency override ---------------------

def test_urgency_queue_dequeues_critical_first() -> None:
    q = UrgencyQueue()
    q.enqueue("routine-1", Urgency.low)
    q.enqueue("urgent-1", Urgency.high)
    q.enqueue("crit-1", Urgency.critical)
    q.enqueue("routine-2", Urgency.low)
    assert q.dequeue() == "crit-1"
    assert q.dequeue() == "urgent-1"
    assert q.dequeue() == "routine-1"  # FIFO within band
    assert q.dequeue() == "routine-2"


def test_urgency_queue_fifo_within_band() -> None:
    q = UrgencyQueue()
    for i in range(5):
        q.enqueue(f"m{i}", Urgency.medium)
    assert [q.dequeue() for _ in range(5)] == ["m0", "m1", "m2", "m3", "m4"]


def test_urgency_queue_depth_by_band() -> None:
    q = UrgencyQueue()
    q.enqueue("a", Urgency.critical)
    q.enqueue("b", Urgency.low)
    q.enqueue("c", Urgency.low)
    depth = q.depth_by_band()
    assert depth["critical"] == 1
    assert depth["low"] == 2


def test_empty_queue_raises() -> None:
    with pytest.raises(ConcurrencyError):
        UrgencyQueue().dequeue()


def test_emergency_override_allows_approved_category() -> None:
    ov = EmergencyOverride()
    result = ov.authorise(category="life_threatening", reason="cardiac arrest")
    assert result["override"] is True
    assert result["category"] == "life_threatening"


def test_emergency_override_denies_non_approved_category() -> None:
    # FR-CC-003-AC01: override on a non-approved category is denied even with reason.
    ov = EmergencyOverride()
    with pytest.raises(ConcurrencyError):
        ov.authorise(category="routine_convenience", reason="faster please")


def test_emergency_override_requires_reason() -> None:
    ov = EmergencyOverride()
    with pytest.raises(ConcurrencyError):
        ov.authorise(category="life_threatening", reason="")
