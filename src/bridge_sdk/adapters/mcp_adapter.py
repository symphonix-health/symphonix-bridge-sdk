"""MCP adapter — translates Model Context Protocol tool calls to/from FHIR R4."""

from __future__ import annotations
from typing import Any
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class McpAdapter(ProtocolAdapter):
    protocol = ProtocolType.MCP

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and raw.get("mcp_calls"):
            return 0.95
        meta = metadata or {}
        if meta.get("protocol") == "MCP":
            return 0.85
        return 0.0

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            raw_source=raw, raw_source_type="MCP",
        )
        calls = raw.get("mcp_calls", [raw]) if isinstance(raw, dict) else []
        resources = []
        for call in calls:
            resources.append({
                "resourceType": "Task",
                "id": f"mcp-{envelope.envelope_id[:8]}",
                "status": "requested",
                "intent": "order",
                "code": {"text": call.get("tool", "unknown")},
                "input": [{"type": {"text": k}, "valueString": str(v)} for k, v in call.get("params", {}).items()],
            })
        envelope.fhir_resources = resources
        return envelope

    async def from_canonical(self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None) -> Any:
        return {
            "mcp_response": {
                "correlation_id": envelope.correlation_id,
                "tool_results": envelope.fhir_resources,
            }
        }
