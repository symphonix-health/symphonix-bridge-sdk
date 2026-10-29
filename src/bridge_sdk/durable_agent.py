"""Durable Agent Execution Contract (DAEC 1.0.0) and SQLite WAL adapter (DA-03).

Composes:
- ``ExecutionLedger`` (WS2): 10-state workflow FSM, SHA-256 hash chain, FHIR R4 Task projection
- ``StepAuditRecords`` (WS4): linked Task + Provenance + AuditEvent triple
- ``PersonaExecutionBudget`` + ``SingleWriterLock`` (WS6): concurrency and writer fencing
- ``HandoffInbox`` + ``HandoffPackage`` (WS11): deferred HITL suspension and one-click resume

Adds durable file-backed SQLite WAL persistence (enforcing ADR-006 against
``:memory:`` paths), deterministic step-level idempotency deduplication with
SHA-256 payload-hash conflict detection, persistent ``HandoffInbox`` state across
process restarts, and ``DAEC 1.0.0`` envelope projection.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bridge_sdk.execution_ledger import (
    ExecutionLedger,
    LedgerError,
    LedgerEvent,
    WorkflowState,
)
from bridge_sdk.human_handoff import (
    HandoffError,
    HandoffInbox,
    HandoffPackage,
    HandoffTrigger,
    ReceiverObserverEvidence,
    ReviewerOutcome,
)

__all__ = [
    "DAEC_CONTRACT_VERSION",
    "CheckpointEnvelope",
    "DurableIdempotencyConflict",
    "DurableLedgerAdapter",
    "SideEffectReceipt",
    "canonical_payload_hash",
]

DAEC_CONTRACT_VERSION = "1.0.0"


class DurableIdempotencyConflict(LedgerError):
    """Raised when an idempotency key is reused with a mutated payload hash (HTTP 409)."""


def canonical_payload_hash(payload: Any) -> str:
    """Compute a deterministic SHA-256 hex digest over a JSON-serialisable payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SideEffectReceipt:
    """Persisted receipt for an idempotent workflow step or tool mutation."""

    step_id: str
    event_id: str
    idempotency_key: str
    payload_hash: str
    effect_digest: str
    recorded_at: str
    output: dict[str, Any] = field(default_factory=dict)
    replayed: bool = False

    def to_schema_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "event_id": self.event_id,
            "idempotency_key": self.idempotency_key,
            "payload_hash": self.payload_hash,
            "effect_digest": self.effect_digest,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True)
class CheckpointEnvelope:
    """Deterministic checkpoint snapshot of a durable workflow."""

    workflow_id: str
    tenant_id: str
    operator_subject: str
    checkpoint_id: str
    committed_at: str
    state: WorkflowState
    fhir_task_status: str
    last_seq: int
    head_hash: str
    completed_step_ids: list[str]
    pending_step_ids: list[str]
    side_effect_receipts: list[SideEffectReceipt]
    resumable: bool
    pre_task_head_sha: str | None = None
    encrypted_session_ref: str | None = None

    def to_checkpoint_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "checkpoint_id": self.checkpoint_id,
            "committed_at": self.committed_at,
            "completed_step_ids": list(self.completed_step_ids),
            "pending_step_ids": list(self.pending_step_ids),
            "resumable": self.resumable,
        }
        if self.pre_task_head_sha:
            out["pre_task_head_sha"] = self.pre_task_head_sha
        if self.encrypted_session_ref:
            out["encrypted_session_ref"] = self.encrypted_session_ref
        return out


def _assert_not_in_memory(db_path: Path | str) -> Path:
    raw = str(db_path).strip()
    if (
        not raw
        or raw == ":memory:"
        or "mode=memory" in raw.lower()
        or raw.startswith("file::memory:")
    ):
        raise RuntimeError(
            "In-memory database paths are forbidden by ADR-006; "
            "DurableLedgerAdapter requires a file-backed SQLite path."
        )
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class DurableLedgerAdapter:
    """File-backed SQLite WAL durable store for ``ExecutionLedger``, ``HandoffInbox``,
    and step-level ``SideEffectReceipt`` idempotency deduplication.

    Survives process crashes and restarts: instantiating a new
    ``DurableLedgerAdapter`` on the same ``db_path`` reconstructs the exact
    ``ExecutionLedger`` state, ``HandoffInbox`` pending/resolved packages, and
    committed ``SideEffectReceipt`` records.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = _assert_not_in_memory(db_path)
        self._lock = threading.RLock()
        self._init_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self._db_path), timeout=30.0, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS durable_ledger_events (
                        seq INTEGER PRIMARY KEY,
                        event_id TEXT NOT NULL UNIQUE,
                        workflow_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL DEFAULT 'local-dev',
                        operator_subject TEXT NOT NULL DEFAULT 'local-operator',
                        to_state TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        previous_hash TEXT NOT NULL,
                        entry_hash TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_durable_ledger_workflow
                    ON durable_ledger_events(workflow_id, seq)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS durable_step_receipts (
                        tenant_id TEXT NOT NULL,
                        operator_subject TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        workflow_id TEXT NOT NULL,
                        step_id TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        effect_digest TEXT NOT NULL,
                        output_json TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        duplicate_hits INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (tenant_id, operator_subject, idempotency_key)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS durable_handoff_packages (
                        workflow_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL DEFAULT 'local-dev',
                        operator_subject TEXT NOT NULL DEFAULT 'local-operator',
                        trigger_value TEXT NOT NULL,
                        task_summary TEXT NOT NULL,
                        provenance_ref TEXT NOT NULL,
                        audit_chain_ref TEXT NOT NULL,
                        decision_rationale TEXT NOT NULL,
                        recommended_next_action TEXT NOT NULL,
                        pre_handoff_state TEXT NOT NULL,
                        pending_inputs_json TEXT NOT NULL,
                        resolved INTEGER NOT NULL DEFAULT 0,
                        resolution TEXT,
                        resumed_to_state TEXT,
                        reviewer_outcome TEXT,
                        receiver_evidence_json TEXT,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def load_ledger(self) -> ExecutionLedger:
        """Reconstruct ``ExecutionLedger`` from persisted SQLite WAL events and verify integrity."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT seq, event_id, workflow_id, to_state, timestamp,
                       payload_json, previous_hash, entry_hash
                FROM durable_ledger_events
                ORDER BY seq ASC
                """
            ).fetchall()
            dup_row = conn.execute(
                "SELECT COALESCE(SUM(duplicate_hits), 0) AS total_dups FROM durable_step_receipts"
            ).fetchone()
        events = [
            LedgerEvent(
                seq=int(r["seq"]),
                event_id=str(r["event_id"]),
                workflow_id=str(r["workflow_id"]),
                to_state=WorkflowState(str(r["to_state"])),
                timestamp=str(r["timestamp"]),
                payload=json.loads(str(r["payload_json"])),
                previous_hash=str(r["previous_hash"]),
                entry_hash=str(r["entry_hash"]),
            )
            for r in rows
        ]
        ledger = ExecutionLedger.from_events(events)
        ledger._duplicates_ignored += int(dup_row["total_dups"]) if dup_row else 0
        ok, broken_seq = ledger.verify_integrity()
        if not ok:
            raise LedgerError(
                f"Durable ledger hash chain integrity failure at seq={broken_seq}"
            )
        return ledger

    def load_inbox(self) -> HandoffInbox:
        """Reconstruct ``HandoffInbox`` (both pending and resolved entries) from SQLite WAL."""
        inbox = HandoffInbox()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT workflow_id, trigger_value, task_summary, provenance_ref,
                       audit_chain_ref, decision_rationale, recommended_next_action,
                       pre_handoff_state, pending_inputs_json, resolved, resolution,
                       resumed_to_state, reviewer_outcome, receiver_evidence_json
                FROM durable_handoff_packages
                ORDER BY workflow_id ASC
                """
            ).fetchall()
        for r in rows:
            pkg = HandoffPackage(
                workflow_id=str(r["workflow_id"]),
                trigger=HandoffTrigger(str(r["trigger_value"])),
                task_summary=str(r["task_summary"]),
                provenance_ref=str(r["provenance_ref"]),
                audit_chain_ref=str(r["audit_chain_ref"]),
                decision_rationale=str(r["decision_rationale"]),
                recommended_next_action=str(r["recommended_next_action"]),
                pre_handoff_state=str(r["pre_handoff_state"]),
                pending_inputs=list(json.loads(str(r["pending_inputs_json"]))),
            )
            inbox.enqueue(pkg)
            if int(r["resolved"]):
                entry = inbox._entries[pkg.workflow_id]
                entry.resolved = True
                entry.resolution = (
                    str(r["resolution"]) if r["resolution"] is not None else None
                )
                entry.resumed_to_state = (
                    str(r["resumed_to_state"])
                    if r["resumed_to_state"] is not None
                    else None
                )
                if r["reviewer_outcome"]:
                    entry.reviewer_outcome = ReviewerOutcome(str(r["reviewer_outcome"]))
                if r["receiver_evidence_json"]:
                    ev_raw = json.loads(str(r["receiver_evidence_json"]))
                    entry.receiver_observer_evidence = ReceiverObserverEvidence(
                        receiver_ref=str(ev_raw["receiver_ref"]),
                        evidence_ref=str(ev_raw["evidence_ref"]),
                        accessible=bool(ev_raw.get("accessible", True)),
                        permitted=bool(ev_raw.get("permitted", True)),
                        attested=bool(ev_raw.get("attested", True)),
                    )
        return inbox

    def admit(
        self,
        workflow_id: str,
        event_id: str,
        timestamp: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        tenant_id: str = "local-dev",
        operator_subject: str = "local-operator",
    ) -> LedgerEvent:
        """Admit a workflow and persist the genesis/admission event to SQLite WAL."""
        ts = timestamp or _now_iso()
        with self._lock:
            ledger = self.load_ledger()
            event = ledger.admit(workflow_id, event_id, ts, payload or {})
            self._persist_event(event, tenant_id=tenant_id, operator_subject=operator_subject)
            return event

    def record(
        self,
        workflow_id: str,
        event_id: str,
        to_state: WorkflowState,
        timestamp: str | None = None,
        payload: dict[str, Any] | None = None,
        *,
        tenant_id: str = "local-dev",
        operator_subject: str = "local-operator",
    ) -> LedgerEvent | None:
        """Record a workflow transition idempotently in SQLite WAL."""
        ts = timestamp or _now_iso()
        with self._lock:
            ledger = self.load_ledger()
            event = ledger.record(workflow_id, event_id, to_state, ts, payload or {})
            if event is not None:
                self._persist_event(
                    event, tenant_id=tenant_id, operator_subject=operator_subject
                )
            return event

    def _persist_event(
        self,
        event: LedgerEvent,
        *,
        tenant_id: str,
        operator_subject: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT INTO durable_ledger_events (
                        seq, event_id, workflow_id, tenant_id, operator_subject,
                        to_state, timestamp, payload_json, previous_hash, entry_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.seq,
                        event.event_id,
                        event.workflow_id,
                        tenant_id,
                        operator_subject,
                        event.to_state.value,
                        event.timestamp,
                        json.dumps(event.payload, sort_keys=True),
                        event.previous_hash,
                        event.entry_hash,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def execute_idempotent_step(
        self,
        workflow_id: str,
        *,
        step_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
        fn: Callable[[], dict[str, Any]],
        tenant_id: str = "local-dev",
        operator_subject: str = "local-operator",
    ) -> SideEffectReceipt:
        """Execute ``fn`` at most once per ``(tenant_id, operator_subject, idempotency_key)``.

        - If the key already exists with the same ``payload_hash``, returns the
          stored ``SideEffectReceipt`` with ``replayed=True`` without calling ``fn``.
        - If the key already exists with a different ``payload_hash``, raises
          ``DurableIdempotencyConflict``.
        """
        if len(idempotency_key.strip()) < 8:
            raise ValueError("idempotency_key must be at least 8 characters")
        p_hash = canonical_payload_hash(payload)

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT step_id, event_id, payload_hash, effect_digest,
                           output_json, recorded_at
                    FROM durable_step_receipts
                    WHERE tenant_id = ? AND operator_subject = ? AND idempotency_key = ?
                    """,
                    (tenant_id, operator_subject, idempotency_key),
                ).fetchone()
                if row is not None:
                    if str(row["payload_hash"]) != p_hash:
                        raise DurableIdempotencyConflict(
                            f"Idempotency conflict for key {idempotency_key!r}: "
                            "payload_hash mismatch"
                        )
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute(
                        """
                        UPDATE durable_step_receipts
                        SET duplicate_hits = duplicate_hits + 1
                        WHERE tenant_id = ? AND operator_subject = ? AND idempotency_key = ?
                        """,
                        (tenant_id, operator_subject, idempotency_key),
                    )
                    conn.execute("COMMIT")
                    return SideEffectReceipt(
                        step_id=str(row["step_id"]),
                        event_id=str(row["event_id"]),
                        idempotency_key=idempotency_key,
                        payload_hash=p_hash,
                        effect_digest=str(row["effect_digest"]),
                        recorded_at=str(row["recorded_at"]),
                        output=json.loads(str(row["output_json"])),
                        replayed=True,
                    )

            # Not yet executed: invoke fn() and commit both ledger event and receipt
            output = fn() or {}
            effect_digest = canonical_payload_hash(output)
            recorded_at = _now_iso()
            event_id = f"{workflow_id}:{step_id}:{idempotency_key}"

            ledger = self.load_ledger()
            current = ledger.current_state(workflow_id)
            if current is None:
                ledger.admit(
                    workflow_id,
                    f"{workflow_id}:admit",
                    recorded_at,
                    {"tenant_id": tenant_id, "operator_subject": operator_subject},
                )
                self._persist_event(
                    ledger.events[-1],
                    tenant_id=tenant_id,
                    operator_subject=operator_subject,
                )
                current = WorkflowState.admitted

            if current != WorkflowState.running:
                ev = ledger.record(
                    workflow_id,
                    event_id,
                    WorkflowState.running,
                    recorded_at,
                    {"step_id": step_id, "idempotency_key": idempotency_key},
                )
                if ev is not None:
                    self._persist_event(
                        ev, tenant_id=tenant_id, operator_subject=operator_subject
                    )

            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        """
                        INSERT INTO durable_step_receipts (
                            tenant_id, operator_subject, idempotency_key,
                            workflow_id, step_id, event_id, payload_hash,
                            effect_digest, output_json, recorded_at, duplicate_hits
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (
                            tenant_id,
                            operator_subject,
                            idempotency_key,
                            workflow_id,
                            step_id,
                            event_id,
                            p_hash,
                            effect_digest,
                            json.dumps(output, sort_keys=True, default=str),
                            recorded_at,
                        ),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise

            return SideEffectReceipt(
                step_id=step_id,
                event_id=event_id,
                idempotency_key=idempotency_key,
                payload_hash=p_hash,
                effect_digest=effect_digest,
                recorded_at=recorded_at,
                output=output,
                replayed=False,
            )

    def list_receipts(self, workflow_id: str) -> list[SideEffectReceipt]:
        """Return all committed ``SideEffectReceipt`` records for ``workflow_id``."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT step_id, event_id, idempotency_key, payload_hash,
                       effect_digest, output_json, recorded_at
                FROM durable_step_receipts
                WHERE workflow_id = ?
                ORDER BY recorded_at ASC, step_id ASC
                """,
                (workflow_id,),
            ).fetchall()
        return [
            SideEffectReceipt(
                step_id=str(r["step_id"]),
                event_id=str(r["event_id"]),
                idempotency_key=str(r["idempotency_key"]),
                payload_hash=str(r["payload_hash"]),
                effect_digest=str(r["effect_digest"]),
                recorded_at=str(r["recorded_at"]),
                output=json.loads(str(r["output_json"])),
                replayed=False,
            )
            for r in rows
        ]

    def suspend_for_human_review(
        self,
        package: HandoffPackage,
        *,
        event_id: str | None = None,
        timestamp: str | None = None,
        tenant_id: str = "local-dev",
        operator_subject: str = "local-operator",
    ) -> LedgerEvent | None:
        """Validate ``package``, transition ``workflow_id`` to ``needs_human_review``,
        and persist the package in ``durable_handoff_packages``."""
        package.validate()
        ts = timestamp or _now_iso()
        ev_id = event_id or f"{package.workflow_id}-handoff-{package.trigger.value}"
        with self._lock:
            ledger = self.load_ledger()
            state = ledger.current_state(package.workflow_id)
            if state is None:
                admit_ev = ledger.admit(
                    package.workflow_id,
                    f"{package.workflow_id}-admit",
                    ts,
                    {"tenant_id": tenant_id},
                )
                self._persist_event(
                    admit_ev, tenant_id=tenant_id, operator_subject=operator_subject
                )
                run_ev = ledger.record(
                    package.workflow_id,
                    f"{package.workflow_id}-run",
                    WorkflowState.running,
                    ts,
                )
                if run_ev is not None:
                    self._persist_event(
                        run_ev, tenant_id=tenant_id, operator_subject=operator_subject
                    )
            elif state == WorkflowState.admitted:
                run_ev = ledger.record(
                    package.workflow_id,
                    f"{package.workflow_id}-run",
                    WorkflowState.running,
                    ts,
                )
                if run_ev is not None:
                    self._persist_event(
                        run_ev, tenant_id=tenant_id, operator_subject=operator_subject
                    )

            handoff_ev = ledger.record(
                package.workflow_id,
                ev_id,
                WorkflowState.needs_human_review,
                ts,
                payload={"trigger": package.trigger.value},
            )
            if handoff_ev is not None:
                self._persist_event(
                    handoff_ev, tenant_id=tenant_id, operator_subject=operator_subject
                )

            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        """
                        INSERT INTO durable_handoff_packages (
                            workflow_id, tenant_id, operator_subject, trigger_value,
                            task_summary, provenance_ref, audit_chain_ref,
                            decision_rationale, recommended_next_action,
                            pre_handoff_state, pending_inputs_json, resolved,
                            resolution, resumed_to_state, reviewer_outcome,
                            receiver_evidence_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, ?)
                        ON CONFLICT(workflow_id) DO UPDATE SET
                            trigger_value = excluded.trigger_value,
                            task_summary = excluded.task_summary,
                            provenance_ref = excluded.provenance_ref,
                            audit_chain_ref = excluded.audit_chain_ref,
                            decision_rationale = excluded.decision_rationale,
                            recommended_next_action = excluded.recommended_next_action,
                            pre_handoff_state = excluded.pre_handoff_state,
                            pending_inputs_json = excluded.pending_inputs_json,
                            resolved = 0,
                            resolution = NULL,
                            resumed_to_state = NULL,
                            updated_at = excluded.updated_at
                        """,
                        (
                            package.workflow_id,
                            tenant_id,
                            operator_subject,
                            package.trigger.value,
                            package.task_summary,
                            package.provenance_ref,
                            package.audit_chain_ref,
                            package.decision_rationale,
                            package.recommended_next_action,
                            package.pre_handoff_state,
                            json.dumps(list(package.pending_inputs)),
                            ts,
                        ),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
            return handoff_ev

    def resume_from_human_review(
        self,
        workflow_id: str,
        *,
        receiver_observer_evidence: ReceiverObserverEvidence,
        outcome: ReviewerOutcome | None = None,
        event_id: str | None = None,
        timestamp: str | None = None,
        tenant_id: str = "local-dev",
        operator_subject: str = "local-operator",
    ) -> str:
        """Resume a suspended workflow from ``HandoffInbox`` and persist both the
        inbox resolution and the ``needs_human_review -> running`` ledger event."""
        ts = timestamp or _now_iso()
        with self._lock:
            inbox = self.load_inbox()
            resumed_to = inbox.resume(
                workflow_id,
                receiver_observer_evidence=receiver_observer_evidence,
                outcome=outcome,
            )
            ev_id = event_id or f"{workflow_id}-resume-{ts}"
            ledger = self.load_ledger()
            ev = ledger.record(
                workflow_id,
                ev_id,
                WorkflowState(resumed_to),
                ts,
                payload={
                    "resumed_by": receiver_observer_evidence.receiver_ref,
                    "evidence_ref": receiver_observer_evidence.evidence_ref,
                },
            )
            if ev is not None:
                self._persist_event(
                    ev, tenant_id=tenant_id, operator_subject=operator_subject
                )
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        """
                        UPDATE durable_handoff_packages
                        SET resolved = 1,
                            resolution = 'resume',
                            resumed_to_state = ?,
                            reviewer_outcome = ?,
                            receiver_evidence_json = ?,
                            updated_at = ?
                        WHERE workflow_id = ?
                        """,
                        (
                            resumed_to,
                            outcome.value if outcome is not None else None,
                            json.dumps(receiver_observer_evidence.to_dict()),
                            ts,
                            workflow_id,
                        ),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
            return resumed_to

    def checkpoint_envelope(
        self,
        workflow_id: str,
        *,
        tenant_id: str = "local-dev",
        operator_subject: str = "local-operator",
        all_step_ids: list[str] | None = None,
        pre_task_head_sha: str | None = None,
    ) -> CheckpointEnvelope:
        """Build a deterministic ``CheckpointEnvelope`` from persisted SQLite WAL state."""
        with self._lock:
            ledger = self.load_ledger()
            task = ledger.task_view(workflow_id)
            wf_events = [e for e in ledger.events if e.workflow_id == workflow_id]
            head_event = wf_events[-1]
            receipts = self.list_receipts(workflow_id)
            completed = [r.step_id for r in receipts]
            ordered_steps = all_step_ids or completed
            pending = [s for s in ordered_steps if s not in set(completed)]
            resumable = task.state not in {
                WorkflowState.completed,
                WorkflowState.cancelled,
            }
            return CheckpointEnvelope(
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                operator_subject=operator_subject,
                checkpoint_id=f"ckpt-{workflow_id}-seq-{task.last_seq}",
                committed_at=head_event.timestamp,
                state=task.state,
                fhir_task_status=task.fhir_status,
                last_seq=task.last_seq,
                head_hash=head_event.entry_hash,
                completed_step_ids=completed,
                pending_step_ids=pending,
                side_effect_receipts=receipts,
                resumable=resumable,
                pre_task_head_sha=pre_task_head_sha,
            )
