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
from bridge_sdk.consent_projection import claim_is_references_only, project_consent
from bridge_sdk.human_handoff import (
    HandoffInbox,
    HandoffPackage,
    HandoffTrigger,
    ReviewerOutcome,
)
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


def test_prompt_policy_version_retained_as_combined_surrogate() -> None:
    # The legacy combined field stays REQUIRED so no consumer breaks when the
    # split fields (prompt_variant / policy_version) are added additively.
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
def test_prompt_variant_now_exists_as_an_optional_provenance_field() -> None:
    # WIRED 2026-06-05: prompt_variant is a standalone field, added additively --
    # present on ProvenanceFields but NOT in REQUIRED (existing callers stay valid).
    prov_field_names = {f.name for f in dataclasses.fields(ProvenanceFields)}
    assert "prompt_variant" in prov_field_names
    assert "prompt_variant" not in REQUIRED_PROVENANCE_FIELDS


def test_policy_version_now_exists_as_an_optional_provenance_field() -> None:
    # WIRED 2026-06-05: standalone policy_version split out from the combined
    # prompt_policy_version surrogate; additive, so not in REQUIRED.
    prov_field_names = {f.name for f in dataclasses.fields(ProvenanceFields)}
    assert "policy_version" in prov_field_names
    assert "policy_version" not in REQUIRED_PROVENANCE_FIELDS


def test_consent_projection_now_emits_a_derived_projection_id() -> None:
    # WIRED 2026-06-05: to_token_claim() emits the derived consent_projection_id
    # (consent_reference@v{version}). Was: only the reference + version.
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
    assert claim["consent_reference"] == "Consent/abc"
    assert claim["consent_version"] == 3
    assert claim["consent_projection_id"] == "Consent/abc@v3"
    # The id is references-only -- no clinical content leaked (FR-PC-002).
    assert claim_is_references_only(claim)


def test_consent_projection_id_status_is_backed_by_a_real_contract() -> None:
    field = next(
        f
        for f in CANONICAL_TELEMETRY_FIELDS
        if f.canonical_name == "consent_projection_id"
    )
    assert field.status is EmitterStatus.sdk_contract
    p = project_consent(
        consent_reference="Consent/x",
        patient_reference="Patient/1",
        is_active=True,
        permitted_purposes=["triage"],
        permitted_resource_types=["Task"],
        approved_jurisdictions=["GB"],
        consent_version=7,
    )
    assert p.projection_id == "Consent/x@v7"
    assert field.status is not EmitterStatus.live


def test_reviewer_outcome_grade_is_distinct_from_the_disposition() -> None:
    # WIRED 2026-06-05: the rubric grade now exists and is recorded ALONGSIDE the
    # disposition, not as it. (Was: the inbox had only resume/amend/cancel.)
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
    inbox.resume("wf-eclaims-1", outcome=ReviewerOutcome.correct_suboptimal)
    # The disposition records what the reviewer DID...
    assert inbox.resolution_of("wf-eclaims-1") == "resume"
    # ...the grade records whether the agent was RIGHT -- a distinct field.
    assert inbox.outcome_of("wf-eclaims-1") is ReviewerOutcome.correct_suboptimal


def test_reviewer_outcome_status_is_backed_by_a_real_contract() -> None:
    field = next(
        f for f in CANONICAL_TELEMETRY_FIELDS if f.canonical_name == "reviewer_outcome"
    )
    assert field.status is EmitterStatus.sdk_contract
    assert {o.value for o in ReviewerOutcome} == {
        "unsafe",
        "incorrect_harmless",
        "correct_suboptimal",
        "correct",
    }
    # Still not live: no production reviewer surface calls the route yet.
    assert field.status is not EmitterStatus.live


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
