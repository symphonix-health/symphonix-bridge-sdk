"""X12 EDI adapter — translates X12 270/271/837/835 to/from FHIR R4."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class X12Adapter(ProtocolAdapter):
    protocol = ProtocolType.X12

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, str) and raw.startswith("ISA*"):
            return 0.99
        if isinstance(raw, dict) and raw.get("x12_transaction"):
            return 0.9
        return 0.0

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            idempotency_key=meta.get("idempotency_key"),
            raw_source=raw, raw_source_type="X12",
        )
        txn = raw.get("x12_transaction", raw) if isinstance(raw, dict) else {"raw": raw}
        txn_type = txn.get("type", "")
        subscriber = txn.get("subscriber", {})

        if txn_type in ("270", "271"):
            envelope.fhir_resources = [{
                "resourceType": "CoverageEligibilityRequest" if txn_type == "270" else "CoverageEligibilityResponse",
                "id": f"x12-{txn_type}-{envelope.envelope_id[:8]}",
                "status": "active",
                "patient": {"display": subscriber.get("name", "")},
                "identifier": [{"system": "urn:x12:member", "value": subscriber.get("member_id", "")}],
            }]
        elif txn_type in ("837", "835"):
            envelope.fhir_resources = [{
                "resourceType": "Claim" if txn_type == "837" else "ExplanationOfBenefit",
                "id": f"x12-{txn_type}-{envelope.envelope_id[:8]}",
                "status": "active",
            }]
        return envelope

    async def from_canonical(self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None) -> Any:
        config = target_config or {}
        txn_type = config.get("transaction_type", "271")
        isa = f"ISA*00*          *00*          *ZZ*BRIDGE         *ZZ*TARGET         *260327*1200*^*00501*{envelope.correlation_id[:9]}*0*P*:~"
        gs = f"GS*HS*BRIDGE*TARGET*20260327*1200*1*X*005010X279A1~"
        st = f"ST*{txn_type}*0001*005010X279A1~"
        se = "SE*3*0001~"
        ge = "GE*1*1~"
        iea = f"IEA*1*{envelope.correlation_id[:9]}~"
        return "\n".join([isa, gs, st, se, ge, iea])
