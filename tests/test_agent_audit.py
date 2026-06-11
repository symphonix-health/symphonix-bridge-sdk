"""Tests for the agent audit composer (Workstream 4, FR-AU-*/NFR-AU-*)."""

from __future__ import annotations

import pytest

from bridge_sdk.agent_audit import (
    REQUIRED_PROVENANCE_FIELDS,
    AuditCompositionError,
    ProvenanceFields,
    compose_step_audit,
    decision_card,
)

TS = "2026-06-02T12:00:00Z"


def _fields(**over) -> ProvenanceFields:
    base = dict(
        persona="triage-intake-agent",
        sponsor="user-clinician-1",
        consent_artefact="Consent/abc",
        route_admission="route-admission/xyz",
        prompt_policy_version="prompt-v12",
        model_version="model-2026-06",
        action_path="patient.intake.submit",
    )
    base.update(over)
    return ProvenanceFields(**base)


def _compose(**over):
    kwargs = dict(
        correlation_id="case-2026-06-02-00042",
        workflow_id="wf-1",
        task_status="completed",
        fields=_fields(),
        action="execute",
        outcome="success",
        timestamp=TS,
        patient_reference="Patient/123",
    )
    kwargs.update(over)
    return compose_step_audit(**kwargs)


def test_three_records_produced() -> None:
    # FR-AU-001: a step produces Task ref + Provenance + AuditEvent.
    r = _compose()
    assert r.task_ref["resourceType"] == "TaskReference"
    assert r.provenance["resourceType"] == "Provenance"
    assert r.audit_event["resourceType"] == "AuditEvent"


def test_execution_mode_recorded_on_task_ref_when_supplied() -> None:
    # The normalised telemetry mode lands on the persisted action record.
    r = _compose(execution_mode="typed_api")
    assert r.task_ref["execution_mode"] == "typed_api"
    # The link hash still verifies (the new field is inside the hashed triple).
    assert r.verify_link() is True


def test_execution_mode_omitted_keeps_task_ref_backward_compatible() -> None:
    # Optional: existing callers that do not pass it get no extra key.
    r = _compose()
    assert "execution_mode" not in r.task_ref


def test_records_share_correlation_id() -> None:
    # FR-AU-001-AC01: mutually cross-referenced by correlation id.
    r = _compose(correlation_id="cid-xyz")
    assert r.all_cross_referenced() is True
    assert r.task_ref["correlation_id"] == "cid-xyz"
    assert r.provenance["correlation_id"] == "cid-xyz"
    assert r.audit_event["correlation_id"] == "cid-xyz"


def test_all_seven_provenance_fields_present() -> None:
    # FR-AU-002: persona, sponsor, consent, route-admission, prompt/policy
    # version, model version, action path.
    assert set(REQUIRED_PROVENANCE_FIELDS) == {
        "persona",
        "sponsor",
        "consent_artefact",
        "route_admission",
        "prompt_policy_version",
        "model_version",
        "action_path",
    }
    r = _compose()
    ext = r.provenance["extension"]
    assert ext["consent_artefact"] == "Consent/abc"
    assert ext["route_admission"] == "route-admission/xyz"
    assert ext["prompt_policy_version"] == "prompt-v12"
    assert ext["model_version"] == "model-2026-06"
    assert ext["action_path"] == "patient.intake.submit"
    assert (
        r.provenance["agent"][0]["who"]["identifier"]["value"] == "triage-intake-agent"
    )
    assert (
        r.provenance["agent"][0]["onBehalfOf"]["identifier"]["value"]
        == "user-clinician-1"
    )


def test_split_prompt_variant_and_policy_version_land_in_extension() -> None:
    # Measurement backlog item 4: the split fields ride in the provenance
    # extension alongside the retained combined prompt_policy_version surrogate.
    r = _compose(
        fields=_fields(
            prompt_variant="appeal-letter-B", policy_version="policy-2026-06"
        )
    )
    ext = r.provenance["extension"]
    assert ext["prompt_variant"] == "appeal-letter-B"
    assert ext["policy_version"] == "policy-2026-06"
    assert ext["prompt_policy_version"] == "prompt-v12"  # combined surrogate kept


def test_split_fields_default_empty_and_are_not_required() -> None:
    # Additive + optional: an existing caller that omits them still validates.
    r = _compose()  # _fields() supplies no split fields
    assert r.provenance["extension"]["prompt_variant"] == ""
    assert r.provenance["extension"]["policy_version"] == ""


@pytest.mark.parametrize("missing_field", REQUIRED_PROVENANCE_FIELDS)
def test_missing_provenance_field_fails_validation(missing_field) -> None:
    # FR-AU-002-AC01: a provenance record missing any required field fails.
    with pytest.raises(AuditCompositionError):
        _compose(fields=_fields(**{missing_field: ""}))


def test_link_hash_verifies_intact() -> None:
    r = _compose()
    assert r.verify_link() is True


def test_tampering_breaks_link_hash() -> None:
    # NFR-AU-002-AC01: altering any record breaks the chain, detected by verifier.
    r = _compose()
    r.audit_event["outcome"] = "TAMPERED"
    assert r.verify_link() is False


def test_decision_card_carries_rationale_and_evidence() -> None:
    # FR-AU-003 / FR-AU-003-AC01: a completed action renders a decision card
    # with rationale + evidence references.
    r = _compose()
    card = decision_card(r, rationale="Urgency band 2; consent permits triage.")
    assert card.correlation_id == r.correlation_id
    assert card.persona == "triage-intake-agent"
    assert card.action_path == "patient.intake.submit"
    assert card.outcome == "success"
    assert card.rationale
    # Defaults to route-admission + consent artefact evidence.
    assert "route-admission/xyz" in card.evidence_references
    assert "Consent/abc" in card.evidence_references


def test_decision_card_explicit_evidence_overrides_default() -> None:
    r = _compose()
    card = decision_card(
        r, rationale="see attached", evidence_references=["signalbox://bundle/abc"]
    )
    assert card.evidence_references == ["signalbox://bundle/abc"]


def test_decision_card_serialisable() -> None:
    r = _compose()
    d = decision_card(r, rationale="ok").to_dict()
    assert set(d) == {
        "correlation_id",
        "persona",
        "action_path",
        "outcome",
        "rationale",
        "evidence_references",
    }
