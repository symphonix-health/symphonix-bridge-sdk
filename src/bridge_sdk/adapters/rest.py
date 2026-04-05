"""REST adapter — translates HTTP JSON payloads to/from FHIR R4 canonical.

Fixes: G5 (LOINC extraction from nested payload), G22 (FHIR R4 compliance).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class RestAdapter(ProtocolAdapter):
    protocol = ProtocolType.REST

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        meta = metadata or {}
        ct = meta.get("content_type", "")
        if "application/json" in ct:
            return 0.9
        if isinstance(raw, dict):
            if "resourceType" not in raw:
                return 0.7
        return 0.1

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            idempotency_key=meta.get("idempotency_key"),
            raw_source=raw,
            raw_source_type="REST/JSON",
        )
        if isinstance(raw, dict):
            patient = raw.get("patient", {})
            referral = raw.get("referral", {})

            # G22: Build FHIR R4 compliant ServiceRequest
            fhir_resource: dict[str, Any] = {
                "resourceType": "ServiceRequest",
                "id": envelope.envelope_id,
                "status": "active",
                "intent": "order",
                "authoredOn": datetime.now(UTC).isoformat(),
                "subject": {
                    "reference": f"Patient/{patient.get('patient_id', 'unknown')}",
                    "display": patient.get("name", ""),
                },
                "priority": _map_urgency(referral.get("urgency", "routine")),
            }

            if referral.get("reason"):
                fhir_resource["reasonCode"] = [{"text": referral["reason"]}]

            if patient.get("dob"):
                fhir_resource.setdefault("contained", []).append({
                    "resourceType": "Patient",
                    "id": patient.get("patient_id", "unknown"),
                    "birthDate": patient["dob"],
                    "name": [{"text": patient.get("name", "")}],
                })
            if patient.get("mrn"):
                fhir_resource["identifier"] = [{"system": "urn:mrn", "value": patient["mrn"]}]

            # G5: Extract LOINC/SNOMED codes from anywhere in the payload
            # and embed them as proper FHIR coding elements
            codes_found = _extract_codes_deep(raw)
            if codes_found:
                fhir_resource["code"] = {"coding": codes_found}
                # Also create Observation resources for lab codes
                for code_entry in codes_found:
                    if code_entry.get("system") == "http://loinc.org":
                        obs = {
                            "resourceType": "Observation",
                            "id": f"obs-{code_entry['code']}",
                            "status": "preliminary",
                            "code": {"coding": [code_entry]},
                            "subject": fhir_resource["subject"],
                        }
                        envelope.fhir_resources.append(obs)

            envelope.fhir_resources.insert(0, fhir_resource)

        # LOINC extraction happens on both FHIR resources AND raw_source
        envelope.extract_loinc_codes()
        return envelope

    async def from_canonical(self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None) -> Any:
        result: dict[str, Any] = {
            "correlation_id": envelope.correlation_id,
            "agent_response": "task_completed",
            "protocol_chain": [h["protocol"] for h in envelope.hops],
            "loinc_codes": envelope.loinc_codes,
        }
        if envelope.fhir_resources:
            result["resource_type"] = envelope.fhir_resources[0].get("resourceType")
            result["resource_id"] = envelope.fhir_resources[0].get("id")
        return result


def _map_urgency(urgency: str) -> str:
    return {"stat": "stat", "urgent": "urgent", "asap": "asap"}.get(urgency, "routine")


def _extract_codes_deep(obj: Any) -> list[dict[str, str]]:
    """Walk any dict/list looking for structured codes (LOINC, SNOMED, ICD, etc.)."""
    codes: list[dict[str, str]] = []
    _walk_for_codes(obj, codes)
    return codes


def _walk_for_codes(obj: Any, out: list[dict[str, str]]) -> None:
    if isinstance(obj, dict):
        # Standard FHIR coding: {system, code, display}
        if obj.get("system") and obj.get("code"):
            out.append({
                "system": str(obj["system"]),
                "code": str(obj["code"]),
                "display": str(obj.get("display", "")),
            })
        # Bare loinc_code pattern (Kafka events, flat REST)
        if obj.get("loinc_code"):
            out.append({
                "system": "http://loinc.org",
                "code": str(obj["loinc_code"]),
                "display": str(obj.get("loinc_display", "")),
            })
        # Bare observation_id pattern (HL7v2 JSON)
        obs_id = obj.get("observation_id")
        if isinstance(obs_id, dict) and obs_id.get("code"):
            out.append({
                "system": obs_id.get("system", "http://loinc.org"),
                "code": str(obs_id["code"]),
                "display": str(obs_id.get("display", "")),
            })
        for v in obj.values():
            _walk_for_codes(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_for_codes(item, out)
