"""HL7v2 adapter — translates HL7v2 pipe-delimited messages to/from FHIR R4."""

from __future__ import annotations

from typing import Any

from bridge_sdk.adapters.base import (
    REQUIRED_GOVERNANCE_CONTROLS,
    ProtocolAdapter,
    ProtocolType,
)
from bridge_sdk.canonical import CanonicalEnvelope


GOVERNANCE_DECLARATION = (
    "audit, schema validation, retry policy, timeout policy, "
    "error normalisation / normalize, observability/tracing, security policy"
)


class Hl7v2Adapter(ProtocolAdapter):
    protocol = ProtocolType.HL7V2
    governance_controls = REQUIRED_GOVERNANCE_CONTROLS

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, str) and raw.startswith("MSH|"):
            return 0.99
        if isinstance(raw, dict):
            if (
                raw.get("hl7v2_message")
                or raw.get("type", "").startswith("ADT")
                or raw.get("type", "").startswith("ORU")
            ):
                return 0.9
        meta = metadata or {}
        if meta.get("protocol") == "HL7v2" or meta.get("port") == 2575:
            return 0.85
        return 0.0

    async def to_canonical(
        self, raw: Any, metadata: dict[str, Any] | None = None
    ) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            idempotency_key=meta.get("idempotency_key"),
            raw_source=raw,
            raw_source_type="HL7v2",
        )

        msg = raw if isinstance(raw, dict) else {"raw": raw}
        hl7 = msg.get("hl7v2_message", msg)
        msg_type = hl7.get("type", "")

        if msg_type.startswith("ADT"):
            envelope.fhir_resources = self._adt_to_fhir(hl7)
        elif msg_type.startswith("ORU"):
            envelope.fhir_resources = self._oru_to_fhir(hl7)
        elif msg_type.startswith("ORM"):
            envelope.fhir_resources = self._orm_to_fhir(hl7)
        else:
            # Generic — wrap as Basic
            envelope.fhir_resources = [
                {
                    "resourceType": "Basic",
                    "code": {"text": msg_type},
                    "extension": [{"url": "hl7v2-payload", "valueString": str(hl7)}],
                }
            ]

        envelope.extract_loinc_codes()
        from bridge_sdk.system1_reflex import Hl7v2SemanticReflex

        triage = Hl7v2SemanticReflex.evaluate(
            {"hl7v2_message": hl7, "fhir_resources": envelope.fhir_resources}
        )
        envelope.system1_triage = {
            "quarantine_required": triage.quarantine_required,
            "requires_human_review": triage.requires_human_review,
            "risk_score": triage.risk_score,
            "reason_codes": list(triage.reason_codes),
            "anomalies": [
                {
                    "code": a.code,
                    "loinc_code": a.loinc_code,
                    "severity": a.severity,
                    "category": a.category,
                    "message": a.message,
                    "suggested_unit": a.suggested_unit,
                    "conversion_factor": a.conversion_factor,
                }
                for a in triage.anomalies
            ],
            "latency_ms": triage.latency_ms,
        }
        return envelope

    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        """Generate HL7v2 message from FHIR resources."""
        config = target_config or {}
        msg_type = config.get("message_type", "ADT^A08")

        segments = []
        segments.append(self._build_msh(envelope, msg_type))

        for resource in envelope.fhir_resources:
            rtype = resource.get("resourceType", "")
            if rtype == "Patient":
                segments.append(self._fhir_patient_to_pid(resource))
            elif rtype in ("Encounter", "ServiceRequest"):
                segments.append(
                    f"PV1|1|{resource.get('class', {}).get('code', 'I')}|||||||||||||||"
                )
            elif rtype == "Observation":
                segments.append(self._fhir_observation_to_obx(resource))

        return "\r".join(segments)

    # --- HL7v2 -> FHIR mappings ---

    def _adt_to_fhir(self, hl7: dict) -> list[dict]:
        pid = hl7.get("pid", {})
        pv1 = hl7.get("pv1", {})
        patient = {
            "resourceType": "Patient",
            "id": pid.get("patient_id", "unknown"),
            "name": [{"text": pid.get("name", "")}],
            "birthDate": pid.get("dob", ""),
            "gender": {"M": "male", "F": "female"}.get(pid.get("sex", ""), "unknown"),
            "identifier": [{"system": "urn:mrn", "value": pid.get("patient_id", "")}],
        }
        encounter = {
            "resourceType": "Encounter",
            "id": f"enc-{pid.get('patient_id', 'unknown')}",
            "status": "in-progress",
            "class": {"code": pv1.get("patient_class", "IMP")},
            "subject": {"reference": f"Patient/{pid.get('patient_id', 'unknown')}"},
            "participant": [
                {"individual": {"display": pv1.get("attending_doctor", "")}}
            ]
            if pv1.get("attending_doctor")
            else [],
        }
        return [patient, encounter]

    def _oru_to_fhir(self, hl7: dict) -> list[dict]:
        pid = hl7.get("pid", hl7.get("msh", {}))
        obx_list = hl7.get("obx", [])
        if isinstance(obx_list, dict):
            obx_list = [obx_list]

        resources: list[dict] = []
        for obx in obx_list:
            obs_id = obx.get("observation_id", {})
            observation = {
                "resourceType": "Observation",
                "id": f"obs-{obs_id.get('code', 'unknown')}",
                "status": "final" if obx.get("status") == "F" else "preliminary",
                "code": {
                    "coding": [
                        {
                            "system": obs_id.get("system", "http://loinc.org"),
                            "code": obs_id.get("code", ""),
                            "display": obs_id.get("display", ""),
                        }
                    ]
                },
                "subject": {
                    "reference": f"Patient/{pid.get('patient_id', hl7.get('pid', {}).get('patient_id', 'unknown'))}"
                },
            }
            if "value" in obx:
                if isinstance(obx["value"], (int, float)):
                    observation["valueQuantity"] = {
                        "value": obx["value"],
                        "unit": obx.get("unit", ""),
                    }
                else:
                    observation["valueString"] = str(obx["value"])
            if obx.get("abnormal_flag"):
                observation["interpretation"] = [
                    {"coding": [{"code": obx["abnormal_flag"]}]}
                ]
            resources.append(observation)
        return resources

    def _orm_to_fhir(self, hl7: dict) -> list[dict]:
        return [
            {"resourceType": "ServiceRequest", "status": "active", "intent": "order"}
        ]

    # --- FHIR -> HL7v2 mappings ---

    def _build_msh(self, envelope: CanonicalEnvelope, msg_type: str) -> str:
        return f"MSH|^~\\&|BRIDGE|BULLETTRAIN|TARGET|TARGET_FAC|{envelope.timestamp[:14].replace('-', '').replace('T', '').replace(':', '')}||{msg_type}|{envelope.correlation_id}|P|2.5.1"

    def _fhir_patient_to_pid(self, patient: dict) -> str:
        pid = patient.get("id", "")
        name = ""
        names = patient.get("name", [])
        if names:
            n = names[0]
            family = n.get("family", n.get("text", ""))
            given = n.get("given", [""])[0] if n.get("given") else ""
            name = f"{family}^{given}"
        dob = patient.get("birthDate", "").replace("-", "")
        sex = {"male": "M", "female": "F"}.get(patient.get("gender", ""), "U")
        return f"PID|1||{pid}||{name}||{dob}|{sex}|||"

    def _fhir_observation_to_obx(self, obs: dict) -> str:
        coding = obs.get("code", {}).get("coding", [{}])[0]
        code = coding.get("code", "")
        display = coding.get("display", "")
        value = ""
        unit = ""
        vq = obs.get("valueQuantity")
        if vq:
            value = str(vq.get("value", ""))
            unit = vq.get("unit", "")
        elif obs.get("valueString"):
            value = obs["valueString"]
        status = "F" if obs.get("status") == "final" else "P"
        return f"OBX|1|NM|{code}^{display}^LN||{value}|{unit}|||{obs.get('interpretation', [{}])[0].get('coding', [{}])[0].get('code', 'N') if obs.get('interpretation') else 'N'}|||{status}"
