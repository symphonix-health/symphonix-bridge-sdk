"""gRPC adapter — translates gRPC payloads to/from FHIR R4."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class GrpcAdapter(ProtocolAdapter):
    protocol = ProtocolType.GRPC

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and raw.get("grpc_request"):
            return 0.9
        meta = metadata or {}
        if meta.get("protocol") == "gRPC" or meta.get("content_type", "").startswith(
            "application/grpc"
        ):
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
            raw_source_type="gRPC",
        )
        grpc = raw.get("grpc_request", raw) if isinstance(raw, dict) else {}
        envelope.fhir_resources = [
            {
                "resourceType": "ServiceRequest",
                "id": f"grpc-{envelope.envelope_id[:8]}",
                "status": "active",
                "intent": "order",
                "code": {"text": f"{grpc.get('service', '')}.{grpc.get('method', '')}"},
                "note": [{"text": str(grpc.get("body", {}))}],
            }
        ]
        return envelope

    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        return {
            "grpc_response": {
                "correlation_id": envelope.correlation_id,
                "resources": envelope.fhir_resources,
                "status": "OK",
            }
        }
