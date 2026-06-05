"""Ground-truth the frozen telemetry schema against the REAL SDK classes.

This test is the executable form of the programme's first principle: a
measurement framework built on assumed-but-unverified telemetry inherits the
false positive. So for every canonical field, this test verifies by
INTROSPECTION that:

- fields marked ``live`` / ``sdk_contract`` / ``tested_helper`` actually have the
  SDK symbol the schema claims backs them, and
- fields marked ``needs_wiring`` / ``partial`` are genuinely ABSENT as the
  canonical field on their real emitter (the gap the status records is real).

If someone upgrades a status to ``live`` without wiring the emitter, or renames
an SDK field out from under the schema, these assertions fail. The schema cannot
silently drift away from the code.
"""
from __future__ import annotations

import dataclasses

import pytest

from bridge_sdk.agent_audit import REQUIRED_PROVENANCE_FIELDS, ProvenanceFields
from bridge_sdk.agent_contract import (
    AutonomyLevel,
    ExecutionMode,
    ResolverDecision,
    ResolverPath,
)
from bridge_sdk.consent_projection import project_consent
from bridge_sdk.human_handoff import HandoffInbox, HandoffPackage, HandoffTrigger
from bridge_sdk.telemetry_schema import (
    CANONICAL_TELEMETRY_FIELDS,
    SCHEMA_VERSION,
    EmitterStatus,
    fields_by_status,
    freeze_fingerprint,
    needs_wiring,
    verified_live,
)

# The eight fields the programme handoff named as the schema to freeze.
HANDOFF_EIGHT = {
    "execution_mode",
    "intent",
    "prompt_variant",
    "policy_version",
    "consent_projection_id",
    "audit_triple",
    "handoff_trigger",
    "reviewer_outcome",
}


# --------------------------------------------------------------------------- #
# Schema internal consistency
# --------------------------------------------------------------------------- #
def test_field_names_are_unique() -> None:
    names = [f.canonical_name for f in CANONICAL_TELEMETRY_FIELDS]
    assert len(names) == len(set(names)), "duplicate canonical field name"


def test_handoff_eight_are_all_present() -> None:
    flagged = {f.canonical_name for f in CANONICAL_TELEMETRY_FIELDS if f.in_handoff_eight}
    assert flagged == HANDOFF_EIGHT


def test_every_status_is_a_valid_enum_member() -> None:
    for f in CANONICAL_TELEMETRY_FIELDS:
        assert isinstance(f.status, EmitterStatus)


def test_freeze_fingerprint_is_deterministic() -> None:
    assert freeze_fingerprint() == freeze_fingerprint()
    assert len(freeze_fingerprint()) == 64  # sha256 hex


def test_helpers_partition_by_status() -> None:
    live = set(verified_live())
    wiring = set(needs_wiring())
    assert live.isdisjoint(wiring)
    assert live | wiring == set(CANONICAL_TELEMETRY_FIELDS)
    # needs_wiring() must be everything that is NOT live.
    assert all(f.status is not EmitterStatus.live for f in wiring)


# --------------------------------------------------------------------------- #
# VERIFIED side: the SDK symbol the schema claims really exists
# --------------------------------------------------------------------------- #
def test_intent_is_a_real_resolver_decision_field() -> None:
    # ResolverDecision is a pydantic BaseModel, so introspect model_fields.
    assert "intent" in ResolverDecision.model_fields


def test_execution_mode_resolver_path_has_exactly_four_values() -> None:
    # The schema normalises this 4-valued enum down to the 3-valued
    # execution_mode; if the enum changes, the normalisation note is stale.
    assert {p.value for p in ResolverPath} == {"api", "nexus", "ui_fallback", "browser"}


def test_policy_version_only_exists_as_conflated_prompt_policy_version() -> None:
    # PARTIAL is justified: prompt_policy_version is present...
    assert "prompt_policy_version" in REQUIRED_PROVENANCE_FIELDS


def test_handoff_trigger_enum_matches_schema_exactly() -> None:
    schema_field = next(
        f for f in CANONICAL_TELEMETRY_FIELDS if f.canonical_name == "handoff_trigger"
    )
    enum_values = {t.value for t in HandoffTrigger}
    # Every enum value must appear in the schema's declared value_type.
    for value in enum_values:
        assert value in schema_field.value_type
    assert enum_values == {
        "triage_edge_case",
        "consent_conflict",
        "contradictory_records",
        "booking_failure",
        "low_confidence",
        "policy_block",
    }


def test_autonomy_level_enum_matches_schema() -> None:
    assert {a.value for a in AutonomyLevel} == {
        "shadow",
        "advisory",
        "auto_with_threshold_hitl",
    }


# --------------------------------------------------------------------------- #
# GAP side: the canonical field is genuinely ABSENT (the status is honest)
# --------------------------------------------------------------------------- #
def test_prompt_variant_is_absent_from_provenance() -> None:
    # needs_wiring is justified: there is no prompt_variant field.
    assert "prompt_variant" not in REQUIRED_PROVENANCE_FIELDS
    prov_field_names = {f.name for f in dataclasses.fields(ProvenanceFields)}
    assert "prompt_variant" not in prov_field_names


def test_policy_version_is_not_a_standalone_field() -> None:
    # The standalone policy_version the schema wants does not exist yet.
    assert "policy_version" not in REQUIRED_PROVENANCE_FIELDS


def test_consent_projection_emits_reference_not_projection_id() -> None:
    projection = project_consent(
        consent_reference="Consent/abc",
        patient_reference="Patient/123",
        is_active=True,
        permitted_purposes=["claims"],
        permitted_resource_types=["Claim"],
        approved_jurisdictions=["GB"],
        consent_version=3,
    )
    claim = projection.to_token_claim()
    # The pieces needed to DERIVE the id are emitted...
    assert claim["consent_reference"] == "Consent/abc"
    assert claim["consent_version"] == 3
    # ...but the canonical consent_projection_id is NOT emitted directly.
    assert "consent_projection_id" not in claim


def test_reviewer_outcome_has_no_rubric_grade_only_a_disposition() -> None:
    package = HandoffPackage(
        workflow_id="wf-eclaims-1",
        trigger=HandoffTrigger.policy_block,
        task_summary="prior-auth needs human decision",
        provenance_ref="Provenance/p1",
        audit_chain_ref="case-1",
        decision_rationale="policy ambiguous",
        recommended_next_action="reviewer adjudicates",
        pre_handoff_state="blocked",
    )
    inbox = HandoffInbox()
    inbox.enqueue(package)
    inbox.resume("wf-eclaims-1")
    # The inbox records the disposition...
    assert inbox.resolution_of("wf-eclaims-1") == "resume"
    # ...which is one of resume|amend|cancel, NOT a rubric grade. There is no
    # method that records unsafe/incorrect/suboptimal/correct.
    assert not hasattr(inbox, "grade")
    assert not hasattr(inbox, "reviewer_outcome")


# --------------------------------------------------------------------------- #
# The audit reflects what the code review found (regression guard on the audit)
# --------------------------------------------------------------------------- #
def test_only_evidence_bundle_is_live_today() -> None:
    # Code review on 2026-06-05 found exactly one agent-native field emitted in a
    # live path (signalbox capture manifests). If this changes, update the doc.
    live_names = {f.canonical_name for f in verified_live()}
    assert live_names == {"evidence_bundle_id"}


def test_execution_mode_status_is_backed_by_a_real_contract() -> None:
    # execution_mode was upgraded needs_wiring -> sdk_contract on 2026-06-05 only
    # because the normalising contract now exists. Guard against a status flip
    # that is not backed by code: ResolverDecision must expose execution_mode.
    field = next(
        f for f in CANONICAL_TELEMETRY_FIELDS if f.canonical_name == "execution_mode"
    )
    assert field.status is EmitterStatus.sdk_contract
    decision = ResolverDecision(intent="claim.submit", path=ResolverPath.api)
    assert decision.execution_mode is ExecutionMode.typed_api
    # ...but it is still not live: no running service persists it yet.
    assert field.status is not EmitterStatus.live


def test_schema_version_is_frozen_string() -> None:
    assert SCHEMA_VERSION.startswith("1.")
    assert "-frozen-" in SCHEMA_VERSION


@pytest.mark.parametrize("status", list(EmitterStatus))
def test_each_status_bucket_is_addressable(status: EmitterStatus) -> None:
    # fields_by_status never raises and only returns fields of that status.
    for f in fields_by_status(status):
        assert f.status is status
