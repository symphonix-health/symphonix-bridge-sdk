"""Tests for bridge_sdk.durable_agent (DA-03) against real file-backed SQLite WAL."""

from __future__ import annotations

from pathlib import Path

import pytest

from bridge_sdk import (
    DAEC_CONTRACT_VERSION,
    DurableIdempotencyConflict,
    DurableLedgerAdapter,
    HandoffPackage,
    HandoffTrigger,
    ReceiverObserverEvidence,
    ReviewerOutcome,
    WorkflowState,
)


def test_adr006_rejects_in_memory_sqlite_paths() -> None:
    assert DAEC_CONTRACT_VERSION == "1.0.0"
    for bad_path in (":memory:", "file::memory:?cache=shared", "sqlite:///test?mode=memory"):
        with pytest.raises(RuntimeError, match="ADR-006"):
            DurableLedgerAdapter(bad_path)


def test_idempotent_step_deduplication_and_conflict_across_restart(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "durable_ledger.db"
    adapter1 = DurableLedgerAdapter(db_file)
    call_count = 0

    def _run_step() -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        return {"order_id": "ORD-1001", "status": "dispatched"}

    receipt1 = adapter1.execute_idempotent_step(
        "wf-erx-01",
        step_id="dispatch-erx",
        idempotency_key="wf-erx-01:dispatch-erx:1",
        payload={"patient_id": "9990000111", "medication": "Amoxicillin 500mg"},
        fn=_run_step,
        tenant_id="t-platform",
        operator_subject="dr.aisha.khan",
    )
    assert receipt1.replayed is False
    assert call_count == 1
    assert receipt1.output["order_id"] == "ORD-1001"

    # Simulate process crash and restart on the same SQLite WAL file
    adapter2 = DurableLedgerAdapter(db_file)
    receipt2 = adapter2.execute_idempotent_step(
        "wf-erx-01",
        step_id="dispatch-erx",
        idempotency_key="wf-erx-01:dispatch-erx:1",
        payload={"medication": "Amoxicillin 500mg", "patient_id": "9990000111"},
        fn=_run_step,
        tenant_id="t-platform",
        operator_subject="dr.aisha.khan",
    )
    assert receipt2.replayed is True
    assert call_count == 1  # fn() was NOT re-invoked
    assert receipt2.effect_digest == receipt1.effect_digest
    assert adapter2.load_ledger().health().duplicate_events_ignored == 1

    # Reusing the same idempotency key with a mutated payload must fail closed (409)
    with pytest.raises(DurableIdempotencyConflict, match="payload_hash mismatch"):
        adapter2.execute_idempotent_step(
            "wf-erx-01",
            step_id="dispatch-erx",
            idempotency_key="wf-erx-01:dispatch-erx:1",
            payload={"patient_id": "9990000111", "medication": "Warfarin 5mg"},
            fn=_run_step,
            tenant_id="t-platform",
            operator_subject="dr.aisha.khan",
        )


def test_hitl_suspension_and_resume_survive_process_restarts(tmp_path: Path) -> None:
    db_file = tmp_path / "durable_handoff.db"
    adapter1 = DurableLedgerAdapter(db_file)

    pkg = HandoffPackage(
        workflow_id="wf-triage-0001",
        trigger=HandoffTrigger.consent_conflict,
        task_summary="Triage paused: consent does not permit lab disclosure.",
        provenance_ref="Provenance/p-1",
        audit_chain_ref="case-2026-06-02-00042",
        decision_rationale="Active consent permits triage but not lab-result disclosure.",
        recommended_next_action="Confirm consent scope with the patient, then resume.",
        pre_handoff_state="running",
        pending_inputs=["updated consent scope"],
    )
    adapter1.suspend_for_human_review(
        pkg, tenant_id="t-platform", operator_subject="dr.aisha.khan"
    )

    # Crash & restart while workflow is suspended in needs_human_review
    adapter2 = DurableLedgerAdapter(db_file)
    ledger2 = adapter2.load_ledger()
    inbox2 = adapter2.load_inbox()
    assert ledger2.current_state("wf-triage-0001") == WorkflowState.needs_human_review
    assert len(inbox2.pending()) == 1
    assert inbox2.pending()[0].workflow_id == "wf-triage-0001"

    ckpt = adapter2.checkpoint_envelope(
        "wf-triage-0001",
        tenant_id="t-platform",
        operator_subject="dr.aisha.khan",
        all_step_ids=["triage-intake", "lab-disclosure"],
    )
    assert ckpt.state == WorkflowState.needs_human_review
    assert ckpt.fhir_task_status == "on-hold"
    assert ckpt.resumable is True

    # Clinician resumes workflow
    resumed_to = adapter2.resume_from_human_review(
        "wf-triage-0001",
        receiver_observer_evidence=ReceiverObserverEvidence(
            receiver_ref="Practitioner/dr-aisha-khan",
            evidence_ref="AuditEvent/resume-wf-triage-0001",
        ),
        outcome=ReviewerOutcome.correct,
        tenant_id="t-platform",
        operator_subject="dr.aisha.khan",
    )
    assert resumed_to == "running"

    # Crash & restart AFTER resume: must stay resumed, not revert to pending
    adapter3 = DurableLedgerAdapter(db_file)
    assert adapter3.load_ledger().current_state("wf-triage-0001") == WorkflowState.running
    assert adapter3.load_inbox().pending() == []


def test_load_inbox_normalizes_external_cohort_seed_rows(tmp_path: Path) -> None:
    """External cohort seeders that write non-enum reviewer_outcome or clinical_ref JSON must not crash load_inbox()."""
    db_file = tmp_path / "durable_seed.db"
    adapter = DurableLedgerAdapter(db_file)
    with adapter._connect() as conn:
        conn.execute(
            """
            INSERT INTO durable_handoff_packages (
                workflow_id, tenant_id, operator_subject, trigger_value,
                task_summary, provenance_ref, audit_chain_ref, decision_rationale,
                recommended_next_action, pre_handoff_state, pending_inputs_json,
                resolved, resolution, resumed_to_state, reviewer_outcome,
                receiver_evidence_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "durablehan-2026-0013",
                "local-dev",
                "local-operator",
                "consent_conflict",
                "Triage paused: consent does not permit lab disclosure.",
                "Provenance/p-1",
                "case-2026-06-02-00042",
                "Active consent permits triage but not lab-result disclosure.",
                "Confirm consent scope with the patient, then resume.",
                "running",
                '["updated consent scope"]',
                13,
                "durable_handoff_packages-resolution-0013",
                "running",
                "durable_handoff_packages-reviewer_outcome-0013",
                '{"clinical_ref": "DURABLE_HANDOFF_PACKAGES-0013", "facility_ods": "RJ1"}',
                "2026-11-15T00:00:00Z",
            ),
        )
        conn.commit()

    inbox = adapter.load_inbox()
    assert inbox.pending() == []
    entry = inbox._entries["durablehan-2026-0013"]
    assert entry.resolved is True
    assert entry.reviewer_outcome == ReviewerOutcome.correct
    assert entry.receiver_observer_evidence is not None
    assert entry.receiver_observer_evidence.receiver_ref == "Organization/RJ1"
    assert (
        entry.receiver_observer_evidence.evidence_ref
        == "DocumentReference/DURABLE_HANDOFF_PACKAGES-0013"
    )

