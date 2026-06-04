"""Per-persona/per-patient execution budgets, single-writer locks, urgency queue.

Workstream 6. Moves concurrency and rate controls from per-API-key to
per-persona and per-patient. Depends on WS2-3.

Design decision: build ON TOP of verified primitives, don't rebuild.

EXISTS (reused as the pattern / lower layer):
- `services/session_supervisor/budget.py:18` ``SessionBudget`` -- per-SERVICE
  acquire/release counter with a threading.Lock. Verified: it has NO persona or
  patient dimension. ``PersonaExecutionBudget`` here mirrors its acquire/release
  shape but keys on persona and adds the five budget dimensions the plan mandates.
- `bullettrain/resilience.py` ``Bulkhead`` + ``RateLimiter`` (token bucket).
- `services/api_gateway/signalbox_gateway_policy.py:143` ``reserve_or_load`` --
  pessimistic single-writer via ``BEGIN IMMEDIATE``. ``SingleWriterLock`` here is
  the in-process analogue for one mutable patient workflow; the BT service swaps
  in the SQLite ``BEGIN IMMEDIATE`` form for cross-replica use.
- `services/common/rbac.py:421` ``_break_glass_reason`` -- emits an audited
  override. Verified: it has NO approved-category whitelist. ``EmergencyOverride``
  here adds the category gate the plan requires (break-glass never blocks
  emergency care; approved categories only).

ABSENT (the genuine WS6 build, verified): per-persona/per-patient execution
budgets, single-writer for mutable patient workflows, urgency-partitioned queue,
and the break-glass approved-category gate.

Requirements: FR-CC-001..003, NFR-CC-001..002
(``BulletTrain/docs/CONCURRENCY_REQUIREMENTS.md``).
"""
from __future__ import annotations

import heapq
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

__all__ = [
    "BudgetExceeded",
    "ConcurrencyError",
    "EmergencyOverride",
    "ExecutionBudgetLimits",
    "PersonaExecutionBudget",
    "SingleWriterConflict",
    "SingleWriterLock",
    "Urgency",
    "UrgencyQueue",
]


class ConcurrencyError(Exception):
    """Base error for concurrency / isolation violations."""


class BudgetExceeded(ConcurrencyError):
    """Raised when a persona exceeds one of its execution budgets (FR-CC-001)."""

    def __init__(self, persona: str, dimension: str, limit: int) -> None:
        self.persona = persona
        self.dimension = dimension
        self.limit = limit
        super().__init__(
            f"persona '{persona}' exceeded budget '{dimension}' (limit {limit})"
        )


class SingleWriterConflict(ConcurrencyError):
    """Raised when a second writer targets a locked patient workflow (FR-CC-002)."""


@dataclass(frozen=True)
class ExecutionBudgetLimits:
    """The five per-persona execution budget dimensions the plan mandates."""

    max_concurrent_workflows: int = 5
    max_screen_actions_per_min: int = 120
    max_model_tokens: int = 200_000
    max_downstream_writes: int = 50
    max_unresolved_escalations: int = 3


class PersonaExecutionBudget:
    """Enforce per-persona execution budgets (FR-CC-001).

    Mirrors ``SessionBudget``'s acquire/release shape but keys on persona and
    tracks five dimensions. Thread-safe via a single lock, like the original.
    Exceeding any dimension raises ``BudgetExceeded`` and records the breach
    (queryable via :meth:`saturation`).
    """

    def __init__(self, limits: ExecutionBudgetLimits | None = None) -> None:
        self._limits = limits or ExecutionBudgetLimits()
        self._lock = threading.Lock()
        self._concurrent: dict[str, int] = {}
        self._actions: dict[str, int] = {}
        self._tokens: dict[str, int] = {}
        self._writes: dict[str, int] = {}
        self._escalations: dict[str, int] = {}
        self._breaches: dict[str, int] = {}

    def acquire_workflow(self, persona: str) -> None:
        """Start one workflow for ``persona``; raise if at the concurrency cap."""
        with self._lock:
            current = self._concurrent.get(persona, 0)
            if current >= self._limits.max_concurrent_workflows:
                self._breaches[persona] = self._breaches.get(persona, 0) + 1
                raise BudgetExceeded(
                    persona, "max_concurrent_workflows",
                    self._limits.max_concurrent_workflows,
                )
            self._concurrent[persona] = current + 1

    def release_workflow(self, persona: str) -> None:
        with self._lock:
            self._concurrent[persona] = max(0, self._concurrent.get(persona, 0) - 1)

    def _charge(
        self, store: dict[str, int], persona: str, amount: int,
        dimension: str, limit: int,
    ) -> None:
        with self._lock:
            new = store.get(persona, 0) + amount
            if new > limit:
                self._breaches[persona] = self._breaches.get(persona, 0) + 1
                raise BudgetExceeded(persona, dimension, limit)
            store[persona] = new

    def charge_action(self, persona: str, n: int = 1) -> None:
        self._charge(self._actions, persona, n, "max_screen_actions_per_min",
                     self._limits.max_screen_actions_per_min)

    def charge_tokens(self, persona: str, n: int) -> None:
        self._charge(self._tokens, persona, n, "max_model_tokens",
                     self._limits.max_model_tokens)

    def charge_write(self, persona: str, n: int = 1) -> None:
        self._charge(self._writes, persona, n, "max_downstream_writes",
                     self._limits.max_downstream_writes)

    def open_escalation(self, persona: str) -> None:
        self._charge(self._escalations, persona, 1, "max_unresolved_escalations",
                     self._limits.max_unresolved_escalations)

    def resolve_escalation(self, persona: str) -> None:
        with self._lock:
            self._escalations[persona] = max(0, self._escalations.get(persona, 0) - 1)

    def saturation(self, persona: str) -> dict[str, Any]:
        """Per-persona saturation + breach count (NFR-CC-002 contention metrics)."""
        with self._lock:
            lim = self._limits
            return {
                "persona": persona,
                "concurrent_workflows": self._concurrent.get(persona, 0),
                "max_concurrent_workflows": lim.max_concurrent_workflows,
                "screen_actions": self._actions.get(persona, 0),
                "model_tokens": self._tokens.get(persona, 0),
                "downstream_writes": self._writes.get(persona, 0),
                "unresolved_escalations": self._escalations.get(persona, 0),
                "breaches": self._breaches.get(persona, 0),
            }


class SingleWriterLock:
    """Single-writer semantics for mutable patient workflows (FR-CC-002).

    In-process analogue of the gateway's ``BEGIN IMMEDIATE`` reservation: a
    workflow key admits exactly one holder; a concurrent acquire raises
    ``SingleWriterConflict``. The BulletTrain Session Supervisor swaps the backing
    store for SQLite ``BEGIN IMMEDIATE`` so the guarantee holds across replicas.
    """

    def __init__(self) -> None:
        self._held: dict[str, str] = {}  # workflow_id -> holder token
        self._lock = threading.Lock()

    def acquire(self, workflow_id: str, holder: str) -> None:
        with self._lock:
            owner = self._held.get(workflow_id)
            if owner is not None and owner != holder:
                raise SingleWriterConflict(
                    f"workflow '{workflow_id}' is held by '{owner}', not '{holder}'"
                )
            self._held[workflow_id] = holder

    def release(self, workflow_id: str, holder: str) -> None:
        with self._lock:
            if self._held.get(workflow_id) == holder:
                del self._held[workflow_id]

    def holder(self, workflow_id: str) -> str | None:
        with self._lock:
            return self._held.get(workflow_id)


class Urgency(IntEnum):
    """Clinical urgency bands. Lower value = higher priority (dequeued first)."""

    critical = 0
    high = 1
    medium = 2
    low = 3


@dataclass(order=True)
class _QueueItem:
    sort_key: tuple[int, int]
    payload: Any = field(compare=False)


class UrgencyQueue:
    """Priority queue partitioned by clinical urgency (FR-CC-003).

    CRITICAL is always dequeued before HIGH, etc. Within a band, FIFO is
    preserved via a monotonic sequence tiebreaker. This is what lets break-glass
    emergencies never wait behind routine work.
    """

    def __init__(self) -> None:
        self._heap: list[_QueueItem] = []
        self._seq = 0
        self._lock = threading.Lock()

    def enqueue(self, payload: Any, urgency: Urgency) -> None:
        with self._lock:
            item = _QueueItem(sort_key=(int(urgency), self._seq), payload=payload)
            self._seq += 1
            heapq.heappush(self._heap, item)

    def dequeue(self) -> Any:
        with self._lock:
            if not self._heap:
                raise ConcurrencyError("queue is empty")
            return heapq.heappop(self._heap).payload

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)

    def depth_by_band(self) -> dict[str, int]:
        """Queue depth per urgency band (NFR-CC-002 monitoring)."""
        with self._lock:
            out = {u.name: 0 for u in Urgency}
            for item in self._heap:
                out[Urgency(item.sort_key[0]).name] += 1
            return out


# Approved break-glass categories (FR-CC-003). The repo's _break_glass_reason
# has NO category whitelist; this gate adds it. Emergency-care categories are
# never blocked; non-approved categories are denied even with a reason.
_APPROVED_OVERRIDE_CATEGORIES: frozenset[str] = frozenset(
    {"life_threatening", "critical_care", "emergency_admission"}
)


class EmergencyOverride:
    """Break-glass gate that honours 'never blocks emergency care' (FR-CC-003).

    Wraps the existing audited override (`services/common/rbac.py` semantics)
    with the approved-category whitelist the plan requires.
    """

    def __init__(self, approved: frozenset[str] | None = None) -> None:
        self._approved = approved or _APPROVED_OVERRIDE_CATEGORIES

    def is_approved(self, category: str) -> bool:
        return category in self._approved

    def authorise(self, *, category: str, reason: str) -> dict[str, Any]:
        """Authorise an override for an approved category, or deny.

        Raises ``ConcurrencyError`` for a non-approved category (deny), even when
        a reason is supplied. Approved categories always succeed -- emergency care
        is never blocked.
        """
        if not reason:
            raise ConcurrencyError("emergency override requires a reason")
        if not self.is_approved(category):
            raise ConcurrencyError(
                f"override category '{category}' is not approved; "
                f"approved: {sorted(self._approved)}"
            )
        return {"override": True, "category": category, "reason": reason}
