"""WebSocket adapter — translates WebSocket frames to/from FHIR R4."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class WebSocketAdapter(ProtocolAdapter):
    protocol = ProtocolType.WEBSOCKET

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and raw.get("ws_frame"):
            return 0.9
        meta = metadata or {}
        if meta.get("protocol") == "WebSocket" or "ws://" in str(meta.get("url", "")):
            return 0.85
        return 0.0

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            raw_source=raw, raw_source_type="WebSocket",
        )
        frame = raw.get("ws_frame", raw) if isinstance(raw, dict) else {"data": raw}
        envelope.fhir_resources = [{
            "resourceType": "Communication",
            "id": f"ws-{envelope.envelope_id[:8]}",
            "status": "in-progress",
            "payload": [{"contentString": frame.get("query", frame.get("data", str(frame)))}],
            "sender": {"display": frame.get("clinician_id", "")},
            "extension": [{"url": "ws-session", "valueString": frame.get("session_id", "")}],
        }]
        return envelope

    async def from_canonical(self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None) -> Any:
        return {
            "type": "bridge_response",
            "correlation_id": envelope.correlation_id,
            "fhir_resources": envelope.fhir_resources,
            "hops": len(envelope.hops),
        }
