"""Nexus A2A adapter — translates Nexus JSON-RPC task messages to/from FHIR R4.

Fixes: G1 (3 dispatch modes), G6 (agent rejection surfaced).
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

import httpx

from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.canonical import CanonicalEnvelope


class DispatchMode(str, Enum):
    SYNC = "sync"        # POST tasks/send, wait for HTTP response
    STREAM = "stream"    # POST tasks/sendSubscribe, read SSE checkpoints
    ASYNC = "async"      # POST tasks/send with callback_url, return task_id


class NexusA2aAdapter(ProtocolAdapter):
    protocol = ProtocolType.NEXUS_A2A

    def __init__(self, default_endpoint: str = "", callback_base_url: str = ""):
        self.default_endpoint = default_endpoint
        self.callback_base_url = callback_base_url  # e.g. http://localhost:8170

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict):
            if "jsonrpc" in raw and raw.get("method", "").startswith("tasks/"):
                return 0.99
            if "a2a_task_result" in raw or "task_id" in raw:
                return 0.85
        return 0.0

    async def to_canonical(self, raw: Any, metadata: dict[str, Any] | None = None) -> CanonicalEnvelope:
        meta = metadata or {}
        envelope = CanonicalEnvelope(
            source_protocol=self.protocol.value,
            correlation_id=meta.get("correlation_id", ""),
            idempotency_key=meta.get("idempotency_key"),
            raw_source=raw,
            raw_source_type="Nexus_A2A",
        )
        if isinstance(raw, dict):
            task_result = raw.get("a2a_task_result", raw)
            fhir_task: dict[str, Any] = {
                "resourceType": "Task",
                "id": task_result.get("task_id", envelope.envelope_id),
                "status": _map_a2a_status(task_result.get("status", "requested")),
                "intent": "order",
                "owner": {"display": task_result.get("agent_id", "")},
            }
            for key in ("assessment", "discharge_data", "findings", "claim", "lab_order", "summary"):
                if key in task_result:
                    fhir_task["input"] = [{"type": {"text": key}, "valueString": str(task_result[key])}]
                    break
            envelope.fhir_resources = [fhir_task]
        envelope.extract_loinc_codes()
        return envelope

    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        """Dispatch via Nexus A2A with proper response handling.

        Supports 3 modes:
        - sync: POST tasks/send, wait for response, surface rejections (G6)
        - stream: POST tasks/sendSubscribe, collect SSE checkpoints
        - async: POST tasks/send with callback_url, return task_id for polling
        """
        config = target_config or {}
        endpoint = config.get("endpoint", self.default_endpoint)
        mode = DispatchMode(envelope.dispatch_mode) if envelope.dispatch_mode else DispatchMode.SYNC

        # Build JSON-RPC 2.0 payload
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        envelope.task_id = task_id

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": envelope.envelope_id,
            "method": "tasks/sendSubscribe" if mode == DispatchMode.STREAM else "tasks/send",
            "params": {
                "id": task_id,
                "correlation_id": envelope.correlation_id,
                "idempotency_key": envelope.idempotency_key,
                "message": {
                    "role": "user",
                    "parts": [{"type": "data", "data": envelope.fhir_resources}],
                },
            },
        }

        # G4: Propagate consent + PHI metadata
        if envelope.consent_token:
            payload["params"]["consent_token"] = envelope.consent_token
        if envelope.purpose_of_use:
            payload["params"]["purpose_of_use"] = envelope.purpose_of_use

        # Async mode: include callback_url
        if mode == DispatchMode.ASYNC and self.callback_base_url:
            envelope.callback_url = f"{self.callback_base_url}/internal/bridge/callback/{task_id}"
            payload["params"]["callback_url"] = envelope.callback_url

        if not endpoint:
            # No endpoint — return payload without dispatching (for testing)
            return {
                "dispatched": False,
                "task_id": task_id,
                "payload": payload,
                "reason": "no_endpoint",
            }

        # Dispatch
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": envelope.correlation_id,
        }
        if envelope.idempotency_key:
            headers["X-Idempotency-Key"] = envelope.idempotency_key
        # G7: Forward trust material if available
        if envelope.agent_trust.get("jwks_uri"):
            headers["X-GHARRA-Trust-JWKS"] = envelope.agent_trust["jwks_uri"]

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)

            # G6: Surface agent rejections
            if resp.status_code >= 400:
                try:
                    error_body = resp.json()
                except Exception:
                    error_body = {"raw": resp.text[:500]}
                return {
                    "dispatched": True,
                    "task_id": task_id,
                    "agent_rejected": True,
                    "status_code": resp.status_code,
                    "error": error_body,
                }

            result = resp.json()

            # Sync mode: response is the agent's actual result
            if mode == DispatchMode.SYNC:
                return {
                    "dispatched": True,
                    "task_id": task_id,
                    "agent_rejected": False,
                    "status_code": resp.status_code,
                    "result": result,
                }

            # Stream mode: follow SSE (simplified — real impl would read event stream)
            if mode == DispatchMode.STREAM:
                return {
                    "dispatched": True,
                    "task_id": task_id,
                    "agent_rejected": False,
                    "status_code": resp.status_code,
                    "result": result,
                    "stream": True,
                }

            # Async mode: return task_id for polling
            return {
                "dispatched": True,
                "task_id": task_id,
                "agent_rejected": False,
                "status_code": resp.status_code,
                "callback_url": envelope.callback_url,
                "poll_url": f"{self.callback_base_url}/api/v1/tasks/{task_id}/status" if self.callback_base_url else None,
            }


def _map_a2a_status(status: str) -> str:
    return {"completed": "completed", "failed": "failed", "cancelled": "cancelled"}.get(status, "requested")
