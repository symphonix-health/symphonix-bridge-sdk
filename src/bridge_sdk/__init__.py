"""Symphonix Protocol Bridge SDK — heterogeneous healthcare protocol translation."""

from bridge_sdk.engine import BridgeEngine
from bridge_sdk.canonical import CanonicalEnvelope
from bridge_sdk.patient_identity import (
    SYMPHONIX_PATIENT_ID_SYSTEM,
    PatientIdentifier,
    build_patient_identifier,
    build_patient_reference,
    extract_patient_id_from_fhir,
    format_patient_id,
    is_valid_patient_id,
    normalize_patient_id,
)
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType

__version__ = "0.1.0"
__all__ = [
    "BridgeEngine",
    "CanonicalEnvelope",
    "PatientIdentifier",
    "ProtocolAdapter",
    "ProtocolType",
    "SYMPHONIX_PATIENT_ID_SYSTEM",
    "build_patient_identifier",
    "build_patient_reference",
    "extract_patient_id_from_fhir",
    "format_patient_id",
    "is_valid_patient_id",
    "normalize_patient_id",
]
