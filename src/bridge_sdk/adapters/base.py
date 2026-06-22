"""ProtocolAdapter ABC — the contract every protocol adapter must implement."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from bridge_sdk.canonical import CanonicalEnvelope, TranslationDirection


class ProtocolType(str, Enum):
    REST = "REST"
    FHIR_R4 = "FHIR_R4"
    HL7V2 = "HL7v2"
    NEXUS_A2A = "Nexus_A2A"
    KAFKA = "Kafka"
    WEBSOCKET = "WebSocket"
    X12 = "X12"
    DICOM = "DICOM"
    CDA = "CDA"
    GRPC = "gRPC"
    MCP = "MCP"
    SSE = "SSE"


REQUIRED_GOVERNANCE_CONTROLS: tuple[str, ...] = (
    "audit",
    "schema validation",
    "retry policy",
    "timeout policy",
    "error normalisation",
    "observability/tracing",
    "security policy",
)


class ProtocolAdapter(ABC):
    """Abstract base for all protocol adapters.

    Each adapter knows how to:
    1. detect() — identify if a raw payload belongs to this protocol
    2. to_canonical() — translate raw payload → CanonicalEnvelope (FHIR R4)
    3. from_canonical() — translate CanonicalEnvelope → protocol-native output
    """

    protocol: ProtocolType
    governance_controls: tuple[str, ...] = REQUIRED_GOVERNANCE_CONTROLS

    @abstractmethod
    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        """Return confidence 0.0-1.0 that this raw payload is our protocol.

        Args:
            raw: The raw payload (bytes, str, dict, etc.)
            metadata: Optional hints (content-type, port, headers)

        Returns:
            Confidence score. >0.8 means strong match.
        """
        ...

    @abstractmethod
    async def to_canonical(
        self, raw: Any, metadata: dict[str, Any] | None = None
    ) -> CanonicalEnvelope:
        """Translate raw protocol payload to FHIR R4 canonical envelope.

        Args:
            raw: Protocol-native payload
            metadata: Headers, content-type, source info

        Returns:
            CanonicalEnvelope with fhir_resources populated
        """
        ...

    @abstractmethod
    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        """Translate FHIR R4 canonical envelope back to protocol-native format.

        Args:
            envelope: The canonical envelope
            target_config: Target endpoint configuration

        Returns:
            Protocol-native payload ready for dispatch
        """
        ...

    def _timed_to_canonical(
        self, raw: Any, metadata: dict[str, Any] | None = None
    ) -> CanonicalEnvelope:
        """Synchronous wrapper that times the translation."""
        import asyncio

        start = time.monotonic()
        envelope = asyncio.get_event_loop().run_until_complete(
            self.to_canonical(raw, metadata)
        )
        elapsed = (time.monotonic() - start) * 1000
        envelope.translation_ms = elapsed
        envelope.source_protocol = self.protocol.value
        envelope.direction = TranslationDirection.INBOUND
        envelope.add_hop(self.protocol.value, self.__class__.__name__, elapsed)
        return envelope
