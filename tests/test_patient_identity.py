from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bridge_sdk.patient_identity import (  # noqa: E402
    NHS_NUMBER_SYSTEM,
    SYMPHONIX_PATIENT_ID_SYSTEM,
    PatientIdentityError,
    assert_not_nhs_identifier,
    build_patient_identifier,
    build_patient_reference,
    extract_patient_id_from_fhir,
    format_patient_id,
    is_valid_patient_id,
    normalize_patient_id,
)


def test_patient_id_uses_nhs_style_shape_without_nhs_namespace() -> None:
    assert normalize_patient_id("900 000 0009") == "9000000009"
    assert format_patient_id("900-000-0009") == "900 000 0009"
    assert build_patient_reference("9000000009") == "Patient/9000000009"

    identifier = build_patient_identifier("9000000009").as_fhir_identifier()

    assert identifier == {
        "system": SYMPHONIX_PATIENT_ID_SYSTEM,
        "value": "9000000009",
        "use": "official",
    }
    assert identifier["system"] != NHS_NUMBER_SYSTEM


@pytest.mark.parametrize(
    "value",
    [
        "9000000009",
        "900 000 0009",
        "900-000-0017",
        9434765919,
    ],
)
def test_patient_id_accepts_modulus_11_valid_values(value: str | int) -> None:
    assert is_valid_patient_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "9000000000",
        "1111111111",
        "1234567890",
        "PAT-001",
        "CR-100001",
        "not-a-patient",
    ],
)
def test_patient_id_rejects_non_canonical_values(value: str) -> None:
    assert not is_valid_patient_id(value)
    with pytest.raises(PatientIdentityError):
        normalize_patient_id(value)


def test_extract_patient_id_from_fhir_patient_and_subject_references() -> None:
    patient = {
        "resourceType": "Patient",
        "id": "local-row-id",
        "identifier": [
            {"system": NHS_NUMBER_SYSTEM, "value": "9434765919"},
            {"system": SYMPHONIX_PATIENT_ID_SYSTEM, "value": "9000000009"},
        ],
    }
    observation = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/9000000009"},
    }

    assert extract_patient_id_from_fhir(patient) == "9000000009"
    assert extract_patient_id_from_fhir(observation) == "9000000009"


def test_nhs_number_system_is_blocked_as_internal_identifier() -> None:
    with pytest.raises(PatientIdentityError):
        assert_not_nhs_identifier({"system": NHS_NUMBER_SYSTEM, "value": "9434765919"})

    assert_not_nhs_identifier({"system": SYMPHONIX_PATIENT_ID_SYSTEM, "value": "9000000009"})

