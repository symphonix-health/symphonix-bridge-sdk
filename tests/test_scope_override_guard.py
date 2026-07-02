"""Tests for the safety-scope override guard.

The tests use real file-backed approval and audit stores. No internal mock is
counted as readiness evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from bridge_sdk import (
    FileDualControlApprovalStore,
    FileScopeOverrideAuditSink,
    ScopeOverrideGuard,
    ScopeOverrideMetrics,
    ScopeOverrideRequest,
    make_scope_override_metrics_router,
    token_sha256,
)

APPROVER = "clinical-safety-officer-1"
TOKEN = "scope-approval-token-2026-06"
PERSONA = "bridge-coordination-agent"


def _approval_store(path: Path) -> FileDualControlApprovalStore:
    path.write_text(
        json.dumps(
            {
                "approvers": [
                    {
                        "actor_id": APPROVER,
                        "token_sha256": token_sha256(TOKEN),
                        "active": True,
                        "allowed_personas": [PERSONA],
                        "allowed_scopes": ["api:write", "task:escalate"],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return FileDualControlApprovalStore(path)


def _guard(tmp_path: Path, metrics: ScopeOverrideMetrics | None = None) -> ScopeOverrideGuard:
    return ScopeOverrideGuard(
        approval_store=_approval_store(tmp_path / "approvals.json"),
        audit_sink=FileScopeOverrideAuditSink(tmp_path / "scope-override-audit.jsonl"),
        permitted_override_scopes=("api:write", "task:escalate"),
        metrics=metrics,
    )


def _request(**over) -> ScopeOverrideRequest:
    base = dict(
        persona=PERSONA,
        primary_actor="bridge-agent-operator-1",
        requested_scopes=("api:read", "api:write"),
        granted_scopes=("api:read",),
        rationale="Named clinical safety officer approved bounded write scope.",
        secondary_actor=APPROVER,
        secondary_approval_token=TOKEN,
        safety_case_ref="safety/CLINICAL_SAFETY_CASE_REPORT.md#scope-overrides",
        correlation_id="corr-scope-override-001",
        action_path="bridge.route.contract.write",
        clinical_context_ref="Task/route-contract-1",
        trajectory_ref="signalbox://verified-replay/route-contract-1",
    )
    base.update(over)
    return ScopeOverrideRequest(**base)


def _audit_sink(guard: ScopeOverrideGuard) -> FileScopeOverrideAuditSink:
    return guard.audit_sink


def test_scope_expansion_without_dual_control_is_rejected_and_audited(
    tmp_path: Path,
) -> None:
    guard = _guard(tmp_path)
    decision = guard.evaluate(
        _request(secondary_actor=None, secondary_approval_token=None)
    )

    assert decision.permitted is False
    assert decision.reason == "missing_secondary_approval"
    assert decision.audit_hash
    assert _audit_sink(guard).verify_chain() is True
    records = _audit_sink(guard).records()
    assert len(records) == 1
    assert records[0]["decision"]["reason"] == "missing_secondary_approval"


def test_valid_dual_control_override_is_allowed_and_hash_chained(
    tmp_path: Path,
) -> None:
    guard = _guard(tmp_path)
    decision = guard.evaluate(_request())

    assert decision.permitted is True
    assert decision.reason == "dual_control_confirmed"
    assert decision.excess_scopes == ["api:write"]
    assert decision.audit_hash
    assert _audit_sink(guard).verify_chain() is True
    event = _audit_sink(guard).records()[0]
    assert event["request"]["secondary_actor"] == APPROVER
    assert event["request"]["secondary_approval_token_sha256"] == token_sha256(TOKEN)


def test_same_actor_cannot_satisfy_dual_control(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    decision = guard.evaluate(
        _request(primary_actor=APPROVER, secondary_actor=APPROVER)
    )

    assert decision.permitted is False
    assert decision.reason == "dual_control_not_distinct"
    assert _audit_sink(guard).verify_chain() is True


def test_unknown_scope_fails_closed_and_is_audited(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    decision = guard.evaluate(_request(requested_scopes=("api:read", "root:all")))

    assert decision.permitted is False
    assert decision.reason == "unknown_scope"
    assert "unknown scope" in decision.detail
    assert _audit_sink(guard).verify_chain() is True


def test_fp_fn_counter_accuracy_on_balanced_labeled_set(tmp_path: Path) -> None:
    metrics = ScopeOverrideMetrics()
    guard = _guard(tmp_path, metrics=metrics)

    for i in range(50):
        decision = guard.evaluate(
            _request(correlation_id=f"corr-valid-{i:03d}"),
            expected_permitted=True,
        )
        assert decision.permitted is True

    invalid_cases = [
        {"secondary_approval_token": "wrong-token"},
        {"secondary_actor": None, "secondary_approval_token": None},
        {"safety_case_ref": None},
        {"rationale": "too short"},
        {"primary_actor": APPROVER, "secondary_actor": APPROVER},
    ]
    for i in range(50):
        mutation = invalid_cases[i % len(invalid_cases)]
        decision = guard.evaluate(
            _request(correlation_id=f"corr-invalid-{i:03d}", **mutation),
            expected_permitted=False,
        )
        assert decision.permitted is False

    summary = metrics.summary()
    assert summary["total"] == 100
    assert summary["permitted_total"] == 50
    assert summary["rejected_total"] == 50
    assert summary["false_positive_total"] == 0
    assert summary["false_negative_total"] == 0
    assert summary["false_positive_rate"] == 0.0
    assert summary["false_negative_rate"] == 0.0
    assert _audit_sink(guard).verify_chain() is True


def test_adversarial_payloads_never_reach_permitted_state(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    mutations = [
        {"secondary_approval_token": "wrong-token"},
        {"secondary_actor": "unknown-approver"},
        {"secondary_actor": None, "secondary_approval_token": None},
        {"safety_case_ref": None},
        {"rationale": "short"},
        {"primary_actor": APPROVER, "secondary_actor": APPROVER},
        {"requested_scopes": ("api:read", "ui:submit")},
        {"requested_scopes": ("api:read", "root:all")},
        {"persona": "unapproved-persona"},
    ]

    for i in range(200):
        mutation = mutations[i % len(mutations)]
        decision = guard.evaluate(
            _request(correlation_id=f"corr-adversarial-{i:03d}", **mutation)
        )
        assert decision.permitted is False

    assert len(_audit_sink(guard).records()) == 200
    assert _audit_sink(guard).verify_chain() is True


def test_metrics_endpoint_exposes_scope_override_summary(tmp_path: Path) -> None:
    metrics = ScopeOverrideMetrics()
    guard = _guard(tmp_path, metrics=metrics)
    guard.evaluate(_request(), expected_permitted=True)
    guard.evaluate(
        _request(correlation_id="corr-bad-token", secondary_approval_token="bad"),
        expected_permitted=False,
    )

    app = FastAPI()
    app.include_router(make_scope_override_metrics_router(metrics))
    response = TestClient(app).get("/metrics/scope-override-guard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["false_positive_total"] == 0
    assert payload["false_negative_total"] == 0
    assert payload["reason_counts"]["dual_control_confirmed"] == 1
    assert payload["reason_counts"]["secondary_approval_invalid"] == 1


def test_scope_override_guard_p99_latency_stays_below_five_ms(
    tmp_path: Path,
) -> None:
    metrics = ScopeOverrideMetrics()
    guard = _guard(tmp_path, metrics=metrics)

    for i in range(1000):
        decision = guard.evaluate(
            _request(correlation_id=f"corr-latency-{i:04d}"),
            expected_permitted=True,
        )
        assert decision.permitted is True

    summary = metrics.summary()
    assert summary["false_negative_total"] == 0
    assert summary["latency_p99_ms"] < 5.0
    assert _audit_sink(guard).verify_chain() is True
