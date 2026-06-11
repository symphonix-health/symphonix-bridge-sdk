"""BridgeEngine — the core protocol translation orchestrator.

Fixes: G1 (response mechanism), G4 (consent propagation), G6 (agent rejection),
       G10 (priority ranking), G11 (retry/fallback), G17 (residency enforcement),
       G21 (backpressure).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from bridge_sdk.canonical import TranslationDirection
from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType

logger = logging.getLogger(__name__)


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BridgeCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout_s: float = 30.0):
        self.failure_threshold = failure_threshold
        self.timeout_s = timeout_s
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker OPENED after %d failures", self.failure_count
            )

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.timeout_s:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True


class _BackpressureSemaphore:
    """G21: Per-endpoint concurrency limiter."""

    def __init__(self, max_concurrency: int):
        self._sem = asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else None

    async def __aenter__(self):
        if self._sem:
            await self._sem.acquire()
        return self

    async def __aexit__(self, *args):
        if self._sem:
            self._sem.release()


class BridgeEngine:
    """Protocol Bridge Engine — the SDK's main entry point."""

    def __init__(
        self,
        adapters: dict[ProtocolType, type[ProtocolAdapter]] | None = None,
        discovery: Any = None,
        audit_callback: Any = None,
        callback_base_url: str = "",
        max_retries: int = 3,
    ):
        self._adapter_classes = adapters or {}
        self._adapter_instances: dict[ProtocolType, ProtocolAdapter] = {}
        self._discovery = discovery
        self._audit_callback = audit_callback
        self._circuit_breakers: dict[str, BridgeCircuitBreaker] = {}
        self._backpressure: dict[str, _BackpressureSemaphore] = {}
        self._last_hash = ""
        self._callback_base_url = callback_base_url
        self._max_retries = max_retries

        # G1: In-memory task result store for async callback mode
        self._task_results: dict[str, dict[str, Any]] = {}

        for ptype, cls in self._adapter_classes.items():
            try:
                if ptype == ProtocolType.NEXUS_A2A:
                    self._adapter_instances[ptype] = cls(
                        callback_base_url=callback_base_url
                    )
                else:
                    self._adapter_instances[ptype] = cls()
            except TypeError:
                self._adapter_instances[ptype] = cls()

    def get_adapter(self, protocol: ProtocolType) -> ProtocolAdapter:
        if protocol not in self._adapter_instances:
            raise ValueError(f"No adapter registered for {protocol}")
        return self._adapter_instances[protocol]

    def detect_protocol(
        self, raw: Any, metadata: dict[str, Any] | None = None
    ) -> ProtocolType:
        best_score = 0.0
        best_protocol = ProtocolType.REST
        for ptype, adapter in self._adapter_instances.items():
            try:
                score = adapter.detect(raw, metadata)
                if score > best_score:
                    best_score = score
                    best_protocol = ptype
            except Exception:
                pass
        return best_protocol

    def store_task_result(self, task_id: str, result: dict[str, Any]) -> None:
        """G1: Store async callback result for polling."""
        self._task_results[task_id] = {**result, "received_at": time.time()}

    def get_task_result(self, task_id: str) -> dict[str, Any] | None:
        return self._task_results.get(task_id)

    async def translate(
        self,
        raw: Any,
        metadata: dict[str, Any] | None = None,
        source_protocol: ProtocolType | None = None,
        target_protocol: ProtocolType | None = None,
        target_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = metadata or {}
        start = time.monotonic()

        # 1. Detect protocol (FR-001)
        if source_protocol is None:
            source_protocol = self.detect_protocol(raw, meta)

        # 2. Translate to canonical (FR-002)
        source_adapter = self.get_adapter(source_protocol)
        envelope = await source_adapter.to_canonical(raw, meta)
        envelope.source_protocol = source_protocol.value

        # Preserve LOINC codes (FR-011) — G5: walk raw_source too
        envelope.extract_loinc_codes()
        envelope.extract_snomed_codes()

        # Set correlation from metadata
        if meta.get("correlation_id") and not envelope.correlation_id:
            envelope.correlation_id = meta["correlation_id"]
        if meta.get("idempotency_key"):
            envelope.idempotency_key = meta["idempotency_key"]

        # G4: Propagate consent + PHI + residency
        if meta.get("consent_token"):
            envelope.consent_token = meta["consent_token"]
        if meta.get("phi_classification"):
            envelope.phi_classification = meta["phi_classification"]
        if meta.get("data_residency"):
            envelope.data_residency = meta["data_residency"]
        if meta.get("purpose_of_use"):
            envelope.purpose_of_use = meta["purpose_of_use"]
        if meta.get("dispatch_mode"):
            envelope.dispatch_mode = meta["dispatch_mode"]

        # 3. Audit chain (NFR-015)
        envelope.previous_hash = self._last_hash
        envelope.compute_hash()
        self._last_hash = envelope.envelope_hash

        # 4. GHARRA discovery (FR-003)
        agent_info = None
        discovery_result = None
        if self._discovery and target_protocol in (
            ProtocolType.NEXUS_A2A,
            ProtocolType.FHIR_R4,
            ProtocolType.GRPC,
        ):
            capability = meta.get("target_capability", "")
            if capability:
                try:
                    # Use enhanced discover_and_resolve if available (G10, G7)
                    if hasattr(self._discovery, "discover_and_resolve"):
                        discovery_result = await self._discovery.discover_and_resolve(
                            capability=capability,
                            jurisdiction=meta.get("jurisdiction"),
                            preferred_protocol=target_protocol.value
                            if target_protocol
                            else None,
                            correlation_id=envelope.correlation_id,
                            purpose_of_use=envelope.purpose_of_use,
                        )
                        if discovery_result:
                            agent_info = discovery_result.agent
                            target_config = target_config or {}
                            target_config["endpoint"] = discovery_result.url
                            # G7: Attach trust material to envelope
                            envelope.agent_trust = discovery_result.trust
                            # G17: Check data residency
                            if envelope.data_residency and discovery_result.residency:
                                allowed = set(envelope.data_residency) & set(
                                    discovery_result.residency
                                )
                                if not allowed:
                                    envelope.error = "DATA_RESIDENCY_VIOLATION"
                                    envelope.error_code = "DATA_RESIDENCY_VIOLATION"
                                    logger.warning(
                                        "Residency violation: patient=%s, agent=%s",
                                        envelope.data_residency,
                                        discovery_result.residency,
                                    )
                    else:
                        # Fallback to simple discover
                        agents = await self._discovery.discover(capability=capability)
                        if agents:
                            agent_info = agents[0]
                            target_config = target_config or {}
                            endpoints = agent_info.get("endpoints", [])
                            if endpoints:
                                target_config["endpoint"] = endpoints[0].get("url", "")
                except Exception as e:
                    logger.warning("GHARRA discovery failed: %s", e)

        # 5. Translate to target protocol (FR-004) with retry (G11)
        dispatch_result = None
        if target_protocol and not envelope.error:
            target_adapter = self.get_adapter(target_protocol)
            envelope.target_protocol = target_protocol.value
            envelope.direction = TranslationDirection.OUTBOUND

            cb_key = f"{target_protocol.value}:{target_config.get('endpoint', '') if target_config else ''}"
            cb = self._circuit_breakers.setdefault(cb_key, BridgeCircuitBreaker())

            if not cb.allow_request():
                envelope.error = "CIRCUIT_OPEN"
                envelope.error_code = "CIRCUIT_OPEN"
            else:
                # G21: Backpressure
                bp_key = target_config.get("endpoint", "") if target_config else ""
                if bp_key and bp_key not in self._backpressure:
                    max_conc = 0
                    if discovery_result:
                        max_conc = discovery_result.endpoint.max_concurrency
                    self._backpressure[bp_key] = _BackpressureSemaphore(max_conc)

                bp = self._backpressure.get(bp_key, _BackpressureSemaphore(0))

                # G11: Retry with exponential backoff, try alternatives on failure
                endpoints_to_try = [target_config or {}]
                if discovery_result and discovery_result.alternatives:
                    for alt in discovery_result.alternatives:
                        endpoints_to_try.append({"endpoint": alt.url})

                last_error = None
                for attempt, ep_config in enumerate(
                    endpoints_to_try[: self._max_retries]
                ):
                    try:
                        async with bp:
                            dispatch_start = time.monotonic()
                            dispatch_result = await target_adapter.from_canonical(
                                envelope, ep_config
                            )
                            dispatch_ms = (time.monotonic() - dispatch_start) * 1000
                            envelope.add_hop(
                                target_protocol.value,
                                target_adapter.__class__.__name__,
                                dispatch_ms,
                            )

                        # G6: Check for agent rejection in dispatch result
                        if isinstance(dispatch_result, dict) and dispatch_result.get(
                            "agent_rejected"
                        ):
                            envelope.error = (
                                f"Agent rejected: {dispatch_result.get('error', '')}"
                            )
                            envelope.error_code = "AGENT_REJECTED"
                            cb.record_failure()
                        else:
                            cb.record_success()
                        last_error = None
                        break  # Success — stop retrying

                    except Exception as e:
                        last_error = e
                        cb.record_failure()
                        logger.warning("Dispatch attempt %d failed: %s", attempt + 1, e)
                        if attempt < len(endpoints_to_try) - 1:
                            await asyncio.sleep(
                                0.5 * (2**attempt)
                            )  # Exponential backoff

                if last_error:
                    envelope.error = str(last_error)
                    envelope.error_code = "DISPATCH_FAILED"

        total_ms = (time.monotonic() - start) * 1000
        envelope.translation_ms = total_ms

        # 6. Audit callback
        if self._audit_callback:
            try:
                await self._audit_callback(envelope)
            except Exception as e:
                logger.error("Audit callback failed: %s", e)

        return {
            "correlation_id": envelope.correlation_id,
            "source_protocol": envelope.source_protocol,
            "target_protocol": envelope.target_protocol,
            "translation_ms": total_ms,
            "hop_count": envelope.hop_count,
            "hops": envelope.hops,
            "loinc_codes": envelope.loinc_codes,
            "envelope_hash": envelope.envelope_hash,
            "agent_info": agent_info,
            "dispatch_result": dispatch_result,
            "error": envelope.error,
            "error_code": envelope.error_code,
            "fhir_resource_count": len(envelope.fhir_resources),
            "fhir_resources": envelope.fhir_resources,
            "task_id": envelope.task_id,
            "callback_url": envelope.callback_url,
            "consent_propagated": bool(envelope.consent_token),
            "phi_classification": envelope.phi_classification,
            "data_residency": envelope.data_residency,
            "envelope": envelope.model_dump(),
        }
