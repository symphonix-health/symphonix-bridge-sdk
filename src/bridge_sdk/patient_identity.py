"""Canonical Symphonix patient identifier helpers.

The Symphonix Patient Identifier deliberately uses the same 10-digit,
modulus-11 shape as a UK NHS number because the format is familiar and has a
useful check digit. It is not an NHS number and must not be emitted with the
NHS Number FHIR identifier system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SYMPHONIX_PATIENT_ID_SYSTEM = "https://fhir.symphonix.health/Id/patient"
NHS_NUMBER_SYSTEM = "https://fhir.nhs.uk/Id/nhs-number"
PATIENT_REFERENCE_PREFIX = "Patient/"

_DIGIT_RE = re.compile(r"\D+")


class PatientIdentityError(ValueError):
    """Raised when a patient identifier cannot satisfy the Symphonix contract."""


@dataclass(frozen=True)
class PatientIdentifier:
    """FHIR-ready representation of the canonical Symphonix patient identifier."""

    value: str
    system: str = SYMPHONIX_PATIENT_ID_SYSTEM
    use: str = "official"

    def as_fhir_identifier(self) -> dict[str, str]:
        return {"system": self.system, "value": self.value, "use": self.use}


def normalize_patient_id(value: str | int) -> str:
    """Normalize and validate a Symphonix Patient Identifier.

    Spaces and hyphens are accepted on input. The returned value is the
    canonical 10-digit storage form.
    """

    digits = _DIGIT_RE.sub("", str(value or ""))
    if not is_valid_patient_id(digits):
        raise PatientIdentityError(
            "Symphonix Patient Identifier must be 10 digits and pass modulus-11 validation"
        )
    return digits


def is_valid_patient_id(value: str | int) -> bool:
    """Return whether value satisfies the Symphonix patient-id checksum."""

    digits = _DIGIT_RE.sub("", str(value or ""))
    if len(digits) != 10 or not digits.isdigit():
        return False
    if len(set(digits)) == 1:
        return False

    total = sum(
        int(digit) * weight
        for digit, weight in zip(digits[:9], range(10, 1, -1), strict=True)
    )
    check_digit = 11 - (total % 11)
    if check_digit == 11:
        check_digit = 0
    if check_digit == 10:
        return False
    return check_digit == int(digits[-1])


def format_patient_id(value: str | int) -> str:
    """Format a canonical identifier in the human-readable 3-3-4 grouping."""

    digits = normalize_patient_id(value)
    return f"{digits[:3]} {digits[3:6]} {digits[6:]}"


def build_patient_identifier(value: str | int) -> PatientIdentifier:
    """Build the canonical FHIR identifier for a Symphonix patient."""

    return PatientIdentifier(value=normalize_patient_id(value))


def build_patient_reference(value: str | int) -> str:
    """Build a FHIR Patient reference using the canonical Symphonix identifier."""

    return f"{PATIENT_REFERENCE_PREFIX}{normalize_patient_id(value)}"


def extract_patient_id_from_fhir(resource: dict[str, Any]) -> str | None:
    """Extract the canonical Symphonix patient id from a FHIR-like resource.

    Supported inputs include Patient resources, resources with a ``subject``
    reference, and resources with a direct ``patient_id`` projection.
    """

    direct_value = resource.get("patient_id") or resource.get("patientId")
    if direct_value and is_valid_patient_id(direct_value):
        return normalize_patient_id(direct_value)

    if resource.get("resourceType") == "Patient":
        patient_id = resource.get("id")
        if patient_id and is_valid_patient_id(patient_id):
            return normalize_patient_id(patient_id)
        for identifier in resource.get("identifier", []):
            if identifier.get("system") == SYMPHONIX_PATIENT_ID_SYSTEM:
                return normalize_patient_id(identifier.get("value", ""))
        return None

    subject = resource.get("subject") or {}
    reference = subject.get("reference") if isinstance(subject, dict) else None
    if isinstance(reference, str) and reference.startswith(PATIENT_REFERENCE_PREFIX):
        candidate = reference.removeprefix(PATIENT_REFERENCE_PREFIX)
        if is_valid_patient_id(candidate):
            return normalize_patient_id(candidate)

    for key in ("patient", "beneficiary"):
        nested = resource.get(key)
        if isinstance(nested, dict):
            reference = nested.get("reference")
            if isinstance(reference, str) and reference.startswith(
                PATIENT_REFERENCE_PREFIX
            ):
                candidate = reference.removeprefix(PATIENT_REFERENCE_PREFIX)
                if is_valid_patient_id(candidate):
                    return normalize_patient_id(candidate)

    return None


def assert_not_nhs_identifier(identifier: dict[str, Any]) -> None:
    """Guard against accidentally treating a real NHS Number as the internal id."""

    if identifier.get("system") == NHS_NUMBER_SYSTEM:
        raise PatientIdentityError(
            "NHS Number identifiers are external aliases and must not be used as the Symphonix Patient Identifier"
        )
