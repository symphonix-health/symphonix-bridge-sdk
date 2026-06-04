"""Tests for the Agent Execution Contract manifests (Workstream 1, FR-AEC-*)."""
from __future__ import annotations

import pytest

from bridge_sdk.agent_contract import (
    REFERENCE_MANIFESTS,
    ActionIntent,
    AutonomyLevel,
    FieldSpec,
    FieldType,
    IOContract,
    ManifestError,
    ResolverPath,
    SafetyClass,
    reference_manifest,
    resolve_intent,
)

FIVE_INTENTS = {
    "triage.start",
    "appointment.book",
    "claim.submit",
    "lab.order",
    "result.retrieve",
}


def _all_intents() -> list[ActionIntent]:
    return [i for m in REFERENCE_MANIFESTS.values() for i in m.intents]


def test_reference_manifest_covers_the_five_intents() -> None:
    # FR-AEC-003: the five top workflows are exposed as typed intents.
    names = {i.intent for i in _all_intents()}
    assert FIVE_INTENTS <= names


def test_every_intent_has_fhir_task_code_and_safety_class() -> None:
    for i in _all_intents():
        assert i.fhir_task_code
        assert isinstance(i.safety_class, SafetyClass)


def test_intent_names_are_globally_unique() -> None:
    names = [i.intent for i in _all_intents()]
    assert len(names) == len(set(names))


def test_manifest_capabilities_match_intents() -> None:
    m = reference_manifest("triage-api")
    assert m.capabilities() == m.intent_names()
    assert "triage.start" in m.capabilities()


def test_agent_card_exposes_capabilities() -> None:
    # FR-AEC-002: the component publishes its capabilities for GHARRA discovery.
    card = reference_manifest("lis").agent_card(endpoint="http://lis.local")
    assert card["id"] == "lis"
    assert set(card["capabilities"]) == {"lab.order", "result.retrieve"}
    assert card["endpoint"] == "http://lis.local"


def test_get_unknown_intent_raises_manifest_error() -> None:
    m = reference_manifest("triage-api")
    with pytest.raises(ManifestError):
        m.get("does.not.exist")


def test_reference_manifest_unknown_component_raises() -> None:
    with pytest.raises(ManifestError):
        reference_manifest("no-such-component")


def test_validate_payload_accepts_valid_payload() -> None:
    intent = reference_manifest("appointment-system").get("appointment.book")
    out = intent.validate_payload({"patient": "Patient/123", "slot": "slot-1"})
    assert out["slot"] == "slot-1"


def test_validate_payload_rejects_missing_required_field() -> None:
    # FR-AEC-001-AC02: malformed payload -> typed error, not a browser fallback.
    intent = reference_manifest("appointment-system").get("appointment.book")
    with pytest.raises(ManifestError):
        intent.validate_payload({"patient": "Patient/123"})  # missing slot


def test_validate_payload_rejects_unknown_field() -> None:
    intent = reference_manifest("appointment-system").get("appointment.book")
    with pytest.raises(ManifestError):
        intent.validate_payload({"patient": "Patient/123", "slot": "s", "x": 1})


def test_validate_payload_rejects_type_mismatch() -> None:
    intent = ActionIntent(
        intent="x.y",
        title="t",
        component="c",
        safety_class=SafetyClass.routine,
        input=IOContract(fields=[FieldSpec(name="n", type=FieldType.integer)]),
        fhir_task_code="agent-x-y",
    )
    with pytest.raises(ManifestError):
        intent.validate_payload({"n": "not-an-int"})
    with pytest.raises(ManifestError):
        intent.validate_payload({"n": True})  # bool is not an int here


def test_to_fhir_task_shape() -> None:
    # FR-AEC-003: each intent is backed by a FHIR Task representation.
    intent = reference_manifest("triage-api").get("triage.start")
    task = intent.to_fhir_task(
        {"patient": "Patient/123", "presenting_complaint": "chest pain"},
        persona="triage-intake-agent",
        patient_reference="Patient/123",
        autonomy=AutonomyLevel.advisory,
        evidence_bundle="signalbox://bundle/abc123",
    )
    assert task["resourceType"] == "Task"
    assert task["code"]["text"] == "agent-triage-start"
    assert task["for"]["reference"] == "Patient/123"
    personas = [e for e in task["input"] if e["type"]["text"] == "AgentPersona"]
    assert personas and personas[0]["valueString"] == "triage-intake-agent"
    autonomy = [e for e in task["extension"] if e["url"].endswith("autonomy-level")]
    assert autonomy and autonomy[0]["valueCode"] == "advisory"
    evidence = [e for e in task["extension"] if e["url"].endswith("evidence-bundle")]
    assert evidence and evidence[0]["valueUri"] == "signalbox://bundle/abc123"


def test_to_fhir_task_validates_before_projection() -> None:
    intent = reference_manifest("appointment-system").get("appointment.book")
    with pytest.raises(ManifestError):
        intent.to_fhir_task({"patient": "Patient/1"}, persona="booking-agent")


def test_resolve_intent_picks_typed_path_when_manifest_backed() -> None:
    # FR-AEC-001-AC01: a manifest-backed intent resolves to a typed path.
    d = resolve_intent("triage.start", REFERENCE_MANIFESTS)
    assert d.manifest_backed is True
    assert d.path is ResolverPath.api
    assert d.component == "triage-api"


def test_resolve_intent_falls_back_to_ui_with_reason() -> None:
    # FR-AEC-004-AC01: no manifest entry -> ui_fallback with a recorded reason.
    d = resolve_intent("legacy.screen.action", REFERENCE_MANIFESTS)
    assert d.manifest_backed is False
    assert d.path is ResolverPath.ui_fallback
    assert d.reason


def test_resolve_intent_prefers_nexus_when_requested() -> None:
    d = resolve_intent("lab.order", REFERENCE_MANIFESTS, prefer_nexus=True)
    assert d.path is ResolverPath.nexus
    assert d.component == "lis"


def test_resolve_intent_accepts_list_of_manifests() -> None:
    d = resolve_intent("claim.submit", list(REFERENCE_MANIFESTS.values()))
    assert d.component == "insurance-eclaims"
    assert d.path is ResolverPath.api
