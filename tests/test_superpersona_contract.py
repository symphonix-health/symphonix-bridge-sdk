"""Tests for superpersona execution contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bridge_sdk.agent_contract import SafetyClass
from bridge_sdk.persona_delegation import PersonaScope
from bridge_sdk.superpersona_contract import (
    SuperpersonaContract,
    build_superpersona_contract,
    reference_superpersona_contract,
)


def test_reference_doctor_contract_binds_persona_to_manifests_and_scopes() -> None:
    contract = reference_superpersona_contract("doctor")

    assert contract.persona_key == "doctor"
    assert contract.safety_class is SafetyClass.high_risk
    assert "triage.start" in contract.action_intent_ids
    assert "result.retrieve" in contract.action_intent_ids
    assert PersonaScope.api_read in contract.required_token_scopes
    assert PersonaScope.task_execute in contract.required_token_scopes
    assert contract.runtime_budget.budget_class == "clinical_high_risk"
    assert contract.runtime_budget.max_concurrency == 1


def test_contract_exports_gharra_a2a_and_mcp_shapes_without_token_material() -> None:
    contract = reference_superpersona_contract("nurse")

    gharra = contract.to_gharra_contract()
    a2a = contract.a2a_card_extension()["x-symphonix-superpersona"]
    mcp = contract.mcp_tool_policy()
    audit = contract.audit_evidence_ref(token_id="jti-123", token_hash="sha256:abc")

    assert gharra["contract_id"] == contract.contract_id
    assert gharra["persona_key"] == "nurse"
    assert a2a["runtime_budget_class"] == contract.runtime_budget.budget_class
    assert mcp["persona_key"] == "nurse"
    assert mcp["allowed_tools"]
    assert audit == {
        "contract_id": contract.contract_id,
        "contract_version": contract.version,
        "persona_key": "nurse",
        "safety_class": contract.safety_class.value,
        "runtime_budget_class": contract.runtime_budget.budget_class,
        "persona_token_id": "jti-123",
        "persona_token_hash": "sha256:abc",
    }
    assert "jwt" not in str(audit).lower()


def test_build_contract_projects_registry_capabilities_to_tool_policy() -> None:
    contract = build_superpersona_contract(
        persona_key="scheduler",
        role_title="Scheduler",
        role_category="operations",
        allowed_purposes=["operations"],
        toolset=["Appointment manager"],
        capabilities=[
            {"domain": "scheduling", "actions": ["book", "view"]},
            {"domain": "form_input", "actions": ["fill", "submit"]},
        ],
    )

    policy = contract.mcp_tool_policy()
    assert contract.action_intent_ids == [
        "appointment.book",
        "claim.submit",
        "result.retrieve",
    ]
    assert PersonaScope.ui_fill in contract.required_token_scopes
    assert PersonaScope.ui_submit in contract.required_token_scopes
    assert any(tool["component"] == "appointment-system" for tool in policy["allowed_tools"])
    assert contract.intuition.selected_framework == "soap"
    assert contract.execution_modes


def test_contract_policy_includes_signalbox_for_governed_execution() -> None:
    contract = reference_superpersona_contract("auditor")

    policy = contract.mcp_tool_policy()
    tool_ids = {tool["tool_id"] for tool in policy["allowed_tools"]}

    assert "signalbox.capture-session" in tool_ids
    assert "signalbox-mcp.invoke-tool" in tool_ids
    assert "signalbox-mcp.computer-use-headed" in tool_ids
    assert "signalbox-mcp.capture-attestation" in tool_ids
    assert PersonaScope.ui_navigate in contract.required_token_scopes
    assert PersonaScope.task_escalate in contract.required_token_scopes
    headed = next(
        tool
        for tool in policy["allowed_tools"]
        if tool["tool_id"] == "signalbox-mcp.computer-use-headed"
    )
    assert headed["protocol"] == "browser"


def test_high_risk_clinical_contract_can_use_signalbox_when_needed() -> None:
    contract = reference_superpersona_contract("doctor")

    policy = contract.mcp_tool_policy()
    signalbox_tools = [
        tool for tool in policy["allowed_tools"] if tool["component"] == "signalbox-mcp"
    ]

    assert signalbox_tools
    assert all("triage.start" in tool["intent_ids"] for tool in signalbox_tools)
    assert any(
        tool["tool_id"] == "signalbox-mcp.computer-use-headed"
        and tool["protocol"] == "browser"
        for tool in signalbox_tools
    )


def test_contract_validation_rejects_unknown_intent() -> None:
    with pytest.raises(ValidationError):
        SuperpersonaContract.model_validate(
            {
                "contract_id": "spc-bad",
                "persona_key": "doctor",
                "role_title": "Doctor",
                "role_category": "clinical",
                "jurisdiction_pack": "IE",
                "allowed_purposes": ["treatment"],
                "tool_bindings": [],
                "action_intent_ids": ["does.not.exist"],
                "runtime_budget": {
                    "budget_class": "routine",
                    "provider_policy": "general",
                    "latency_slo_ms": 1000,
                    "token_budget": 1000,
                    "cost_class": "low",
                    "max_concurrency": 1,
                },
                "required_token_scopes": ["api:read"],
                "intuition": {
                    "selected_framework": "soap",
                    "confidence": 0.5,
                    "risk_score": 0.1,
                },
            }
        )
