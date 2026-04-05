"""SSE adapter — translates Server-Sent Events to/from FHIR R4."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class SseAdapter(ProtocolAdapter):
    protocol = ProtocolType.SSE

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and raw.get("sse_event"):
            return 0.9
        meta = metadata or {}
        if meta.get("content_type", "") == "text/event-stream":
            return 0.85
        return 0.0

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            raw_source=raw, raw_source_type="SSE",
        )
        event = raw.get("sse_event", raw) if isinstance(raw, dict) else {}
        envelope.fhir_resources = [{
            "resourceType": "Communication",
            "id": f"sse-{envelope.envelope_id[:8]}",
            "status": "completed",
            "topic": [{"text": event.get("event", "unknown")}],
            "payload": [{"contentString": str(event.get("data", {}))}],
        }]
        return envelope

    async def from_canonical(self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None) -> Any:
        return f"event: bridge_response\ndata: {envelope.model_dump_json()}\n\n"
