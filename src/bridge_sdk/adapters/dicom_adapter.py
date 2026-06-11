"""DICOM adapter — translates DICOM metadata to/from FHIR R4 ImagingStudy."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class DicomAdapter(ProtocolAdapter):
    protocol = ProtocolType.DICOM

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and raw.get("dicom_metadata"):
            return 0.95
        if isinstance(raw, bytes) and raw[128:132] == b"DICM":
            return 0.99
        meta = metadata or {}
        if meta.get("protocol") == "DICOM" or meta.get("port") == 11112:
            return 0.85
        return 0.0

    async def to_canonical(
        self, raw: Any, metadata: dict[str, Any] | None = None
    ) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            raw_source=raw,
            raw_source_type="DICOM",
        )
        dcm = raw.get("dicom_metadata", raw) if isinstance(raw, dict) else {}
        envelope.fhir_resources = [
            {
                "resourceType": "ImagingStudy",
                "id": dcm.get("study_instance_uid", envelope.envelope_id),
                "status": "available",
                "subject": {
                    "reference": f"Patient/{dcm.get('patient_id', 'unknown')}",
                    "display": dcm.get("patient_name", ""),
                },
                "started": dcm.get("study_date", ""),
                "identifier": [
                    {
                        "system": "urn:dicom:uid",
                        "value": dcm.get("study_instance_uid", ""),
                    }
                ],
                "modality": [{"code": dcm.get("modality", "")}],
                "series": [
                    {
                        "uid": dcm.get("series_instance_uid", ""),
                        "modality": {"code": dcm.get("modality", "")},
                        "bodySite": {"display": dcm.get("body_part", "")},
                        "instance": [
                            {
                                "uid": dcm.get("sop_instance_uid", ""),
                                "sopClass": {"code": "1.2.840.10008.5.1.4.1.1.2"},
                            }
                        ],
                    }
                ],
            }
        ]
        return envelope

    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        # Generate DICOM metadata dict (actual DICOM binary would use pydicom)
        for r in envelope.fhir_resources:
            if r.get("resourceType") == "ImagingStudy":
                series = r.get("series", [{}])[0] if r.get("series") else {}
                return {
                    "study_instance_uid": r.get("identifier", [{}])[0].get("value", ""),
                    "series_instance_uid": series.get("uid", ""),
                    "modality": r.get("modality", [{}])[0].get("code", ""),
                    "patient_id": r.get("subject", {})
                    .get("reference", "")
                    .replace("Patient/", ""),
                }
        return {"error": "no ImagingStudy in envelope"}
