"""Protocol adapters — each translates between a specific protocol and the FHIR R4 canonical."""

from bridge_sdk.adapters.base import ProtocolAdapter, ProtocolType
from bridge_sdk.adapters.rest import RestAdapter
from bridge_sdk.adapters.fhir import FhirAdapter
from bridge_sdk.adapters.hl7v2 import Hl7v2Adapter
from bridge_sdk.adapters.nexus_a2a import NexusA2aAdapter
from bridge_sdk.adapters.kafka_adapter import KafkaAdapter
from bridge_sdk.adapters.websocket_adapter import WebSocketAdapter
from bridge_sdk.adapters.x12 import X12Adapter
from bridge_sdk.adapters.dicom_adapter import DicomAdapter
from bridge_sdk.adapters.cda import CdaAdapter
from bridge_sdk.adapters.grpc_adapter import GrpcAdapter
from bridge_sdk.adapters.mcp_adapter import McpAdapter
from bridge_sdk.adapters.sse import SseAdapter

ADAPTER_REGISTRY: dict[ProtocolType, type[ProtocolAdapter]] = {
    ProtocolType.REST: RestAdapter,
    ProtocolType.FHIR_R4: FhirAdapter,
    ProtocolType.HL7V2: Hl7v2Adapter,
    ProtocolType.NEXUS_A2A: NexusA2aAdapter,
    ProtocolType.KAFKA: KafkaAdapter,
    ProtocolType.WEBSOCKET: WebSocketAdapter,
    ProtocolType.X12: X12Adapter,
    ProtocolType.DICOM: DicomAdapter,
    ProtocolType.CDA: CdaAdapter,
    ProtocolType.GRPC: GrpcAdapter,
    ProtocolType.MCP: McpAdapter,
    ProtocolType.SSE: SseAdapter,
}

__all__ = [
    "ADAPTER_REGISTRY",
    "ProtocolAdapter",
    "ProtocolType",
    "RestAdapter",
    "FhirAdapter",
    "Hl7v2Adapter",
    "NexusA2aAdapter",
    "KafkaAdapter",
    "WebSocketAdapter",
    "X12Adapter",
    "DicomAdapter",
    "CdaAdapter",
    "GrpcAdapter",
    "McpAdapter",
    "SseAdapter",
]
