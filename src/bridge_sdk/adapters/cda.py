"""CDA adapter — translates HL7 CDA/C-CDA documents to/from FHIR R4."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class CdaAdapter(ProtocolAdapter):
    protocol = ProtocolType.CDA

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, str) and "<ClinicalDocument" in raw:
            return 0.99
        if isinstance(raw, dict) and raw.get("cda_document"):
            return 0.9
        return 0.0

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            raw_source=raw, raw_source_type="CDA",
        )
        cda = raw.get("cda_document", raw) if isinstance(raw, dict) else {"raw": raw}
        patient = cda.get("patient", {})
        sections = cda.get("sections", [])

        doc_ref = {
            "resourceType": "DocumentReference",
            "id": f"cda-{envelope.envelope_id[:8]}",
            "status": "current",
            "type": {"text": cda.get("type", "CCD")},
            "subject": {"display": patient.get("name", ""), "reference": f"Patient/{patient.get('id', 'unknown')}"},
            "content": [{"attachment": {"contentType": "text/xml"}}],
            "context": {"related": [{"display": s} for s in sections]},
        }
        envelope.fhir_resources = [doc_ref]
        envelope.extract_loinc_codes()
        return envelope

    async def from_canonical(self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None) -> Any:
        # Generate CDA XML skeleton
        sections_xml = ""
        for r in envelope.fhir_resources:
            rtype = r.get("resourceType", "")
            sections_xml += f'<component><section><title>{rtype}</title></section></component>\n'
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>
  <id root="{envelope.envelope_id}"/>
  <code code="34133-9" codeSystem="2.16.840.1.113883.6.1" displayName="Summarization of Episode Note"/>
  <recordTarget><patientRole><id root="{envelope.correlation_id}"/></patientRole></recordTarget>
  <component><structuredBody>{sections_xml}</structuredBody></component>
</ClinicalDocument>"""
