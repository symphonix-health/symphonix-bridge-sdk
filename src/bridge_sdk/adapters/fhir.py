"""FHIR R4 adapter — passthrough for native FHIR resources."""

from __future__ import annotations

from typing import Any

import httpx

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


class FhirAdapter(ProtocolAdapter):
    protocol = ProtocolType.FHIR_R4
    governance_controls = REQUIRED_GOVERNANCE_CONTROLS

    def __init__(self, fhir_base_url: str = "http://localhost:8152/fhir/r4"):
        self.fhir_base_url = fhir_base_url

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and "resourceType" in raw:
            return 0.95
        meta = metadata or {}
        ct = meta.get("content_type", "")
        if "fhir" in ct.lower():
            return 0.9
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
            raw_source_type="FHIR_R4",
        )
        if isinstance(raw, dict):
            envelope.fhir_resources = [raw]
        elif isinstance(raw, list):
            envelope.fhir_resources = raw
        envelope.extract_loinc_codes()
        envelope.extract_snomed_codes()
        return envelope

    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        """Write FHIR resources to the FHIR server."""
        config = target_config or {}
        base = config.get("fhir_base_url", self.fhir_base_url)
        results = []
        async with httpx.AsyncClient(timeout=5) as client:
            for resource in envelope.fhir_resources:
                rtype = resource.get("resourceType", "Basic")
                headers = {
                    "Content-Type": "application/fhir+json",
                    "X-Correlation-ID": envelope.correlation_id,
                }
                if envelope.idempotency_key:
                    headers["X-Idempotency-Key"] = envelope.idempotency_key
                resp = await client.post(
                    f"{base}/{rtype}", json=resource, headers=headers
                )
                results.append(
                    {
                        "status": resp.status_code,
                        "resource_type": rtype,
                        "location": resp.headers.get("Location", ""),
                        "etag": resp.headers.get("ETag", ""),
                    }
                )
        return results
