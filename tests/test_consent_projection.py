"""Tests for the consent projection (Workstream 9, FR-PC-*/NFR-PC-*)."""

from __future__ import annotations

import pytest

from bridge_sdk.consent_projection import (
    ConsentDenied,
    ConsentProjectionError,
    claim_is_references_only,
    consent_projection_id,
    project_consent,
)


def _proj(**over):
    kw = dict(
        consent_reference="Consent/abc",
        patient_reference="Patient/123",
        is_active=True,
        permitted_purposes=["treatment", "triage"],
        permitted_resource_types=["Task", "Observation"],
        approved_jurisdictions=["GB", "IE"],
        consent_version=3,
    )
    kw.update(over)
    return project_consent(**kw)


# ---- FR-PC-001: projection + attach + authorise ------------------------


def test_projection_carries_references_and_permissions() -> None:
    p = _proj()
    claim = p.to_token_claim()
    assert claim["consent_reference"] == "Consent/abc"
    assert claim["patient_reference"] == "Patient/123"
    assert set(claim["purposes"]) == {"treatment", "triage"}
    assert claim["consent_version"] == 3


def test_authorise_allows_permitted_action() -> None:
    p = _proj()
    p.authorise(
        purpose_of_use="triage",
        resource_type="Task",
        target_jurisdiction="GB",
        current_consent_version=3,
    )  # no raise
    assert p.permits(
        purpose_of_use="treatment",
        resource_type="Observation",
        target_jurisdiction="IE",
        current_consent_version=3,
    )


# ---- FR-PC-002: references only, no clinical content -------------------


def test_token_claim_is_references_only() -> None:
    p = _proj()
    assert claim_is_references_only(p.to_token_claim()) is True


def test_claim_with_clinical_content_is_flagged() -> None:
    bad = {"consent_reference": "Consent/abc", "diagnosis": "I21.9"}
    assert claim_is_references_only(bad) is False


# ---- FR-PC-003 + NFR-PC-001: fail-closed paths -------------------------


def test_purpose_mismatch_denied() -> None:
    p = _proj()
    with pytest.raises(ConsentDenied) as ei:
        p.authorise(
            purpose_of_use="research",
            resource_type="Task",
            target_jurisdiction="GB",
            current_consent_version=3,
        )
    assert ei.value.reason == "purpose_mismatch"


def test_resource_not_permitted_denied() -> None:
    p = _proj()
    with pytest.raises(ConsentDenied) as ei:
        p.authorise(
            purpose_of_use="triage",
            resource_type="DiagnosticReport",
            target_jurisdiction="GB",
            current_consent_version=3,
        )
    assert ei.value.reason == "resource_not_permitted"


def test_cross_border_non_approved_jurisdiction_denied() -> None:
    # FR-PC-003: patient-data tasks route only to approved jurisdictions.
    p = _proj()
    with pytest.raises(ConsentDenied) as ei:
        p.authorise(
            purpose_of_use="triage",
            resource_type="Task",
            target_jurisdiction="US",
            current_consent_version=3,
        )
    assert ei.value.reason == "jurisdiction_not_approved"


def test_mid_task_revocation_denied() -> None:
    # NFR-PC-001: consent revoked mid-task -> version moves -> fail closed.
    p = _proj(consent_version=3)
    with pytest.raises(ConsentDenied) as ei:
        p.authorise(
            purpose_of_use="triage",
            resource_type="Task",
            target_jurisdiction="GB",
            current_consent_version=4,  # withdrew -> v4
        )
    assert ei.value.reason == "consent_revoked"


def test_inactive_projection_denies_everything() -> None:
    p = _proj()
    object.__setattr__(p, "active", False)  # simulate revocation flag
    with pytest.raises(ConsentDenied) as ei:
        p.authorise(
            purpose_of_use="triage",
            resource_type="Task",
            target_jurisdiction="GB",
            current_consent_version=3,
        )
    assert ei.value.reason == "consent_revoked"


def test_withdrawn_source_consent_yields_no_projection() -> None:
    # A withdrawn/absent consent can never produce a usable projection.
    with pytest.raises(ConsentDenied) as ei:
        _proj(is_active=False)
    assert ei.value.reason == "no_active_consent"


def test_projection_requires_at_least_one_purpose() -> None:
    with pytest.raises(ConsentProjectionError):
        _proj(permitted_purposes=[])


# ---- NFR-PC-002: denial reasons are queryable (machine-readable) -------


@pytest.mark.parametrize(
    "kw,reason",
    [
        (
            dict(
                purpose_of_use="research",
                resource_type="Task",
                target_jurisdiction="GB",
                current_consent_version=3,
            ),
            "purpose_mismatch",
        ),
        (
            dict(
                purpose_of_use="triage",
                resource_type="X",
                target_jurisdiction="GB",
                current_consent_version=3,
            ),
            "resource_not_permitted",
        ),
        (
            dict(
                purpose_of_use="triage",
                resource_type="Task",
                target_jurisdiction="US",
                current_consent_version=3,
            ),
            "jurisdiction_not_approved",
        ),
        (
            dict(
                purpose_of_use="triage",
                resource_type="Task",
                target_jurisdiction="GB",
                current_consent_version=9,
            ),
            "consent_revoked",
        ),
    ],
)
def test_denial_reasons_are_machine_readable(kw, reason) -> None:
    p = _proj()
    with pytest.raises(ConsentDenied) as ei:
        p.authorise(**kw)
    assert ei.value.reason == reason


# ---- consent_projection_id (measurement backlog item 5) ----------------


def test_projection_id_is_reference_at_version() -> None:
    assert _proj(consent_version=3).projection_id == "Consent/abc@v3"
    assert consent_projection_id("Consent/xyz", 9) == "Consent/xyz@v9"


def test_projection_id_changes_with_version() -> None:
    # A mid-task revocation bumps the version -> a new projection id, so a denial
    # joins to the right projection generation.
    assert (
        _proj(consent_version=3).projection_id != _proj(consent_version=4).projection_id
    )


def test_token_claim_includes_projection_id_and_stays_references_only() -> None:
    claim = _proj(consent_version=3).to_token_claim()
    assert claim["consent_projection_id"] == "Consent/abc@v3"
    # FR-PC-002: the id is a reference, not clinical content.
    assert claim_is_references_only(claim)
