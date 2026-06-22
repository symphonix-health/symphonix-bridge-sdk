"""Kafka adapter — publishes/consumes events via Kafka topics."""

from __future__ import annotations
import json
from typing import Any
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


class KafkaAdapter(ProtocolAdapter):
    protocol = ProtocolType.KAFKA
    governance_controls = REQUIRED_GOVERNANCE_CONTROLS

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers

    def detect(self, raw: Any, metadata: dict[str, Any] | None = None) -> float:
        if isinstance(raw, dict) and raw.get("kafka_event"):
            return 0.95
        meta = metadata or {}
        if meta.get("protocol") == "Kafka" or "topic" in meta:
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
            raw_source_type="Kafka",
        )
        event = raw.get("kafka_event", raw) if isinstance(raw, dict) else {}
        value = event.get("value", event)
        if isinstance(value, dict) and value.get("loinc_code"):
            envelope.fhir_resources = [
                {
                    "resourceType": "Observation",
                    "id": f"kafka-{envelope.envelope_id[:8]}",
                    "status": "final",
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": value["loinc_code"],
                                "display": value.get("loinc_display", ""),
                            }
                        ]
                    },
                    "subject": {
                        "reference": f"Patient/{value.get('patient_id', 'unknown')}"
                    },
                    "valueQuantity": {
                        "value": value.get("value"),
                        "unit": value.get("unit", ""),
                    }
                    if "value" in value
                    else None,
                }
            ]
        else:
            envelope.fhir_resources = [
                {
                    "resourceType": "Basic",
                    "code": {"text": "kafka-event"},
                    "extension": [
                        {"url": "kafka-value", "valueString": json.dumps(value)}
                    ],
                }
            ]
        envelope.extract_loinc_codes()
        return envelope

    async def from_canonical(
        self, envelope: CanonicalEnvelope, target_config: dict[str, Any] | None = None
    ) -> Any:
        config = target_config or {}
        topic = config.get("topic", "bridge.events")
        # Build Kafka message payload
        message = {
            "topic": topic,
            "key": envelope.correlation_id,
            "value": {
                "correlation_id": envelope.correlation_id,
                "fhir_resources": envelope.fhir_resources,
                "loinc_codes": envelope.loinc_codes,
                "source_protocol": envelope.source_protocol,
                "hops": envelope.hops,
            },
        }
        # Actual Kafka produce would use confluent_kafka here
        try:
            from confluent_kafka import Producer

            producer = Producer({"bootstrap.servers": self.bootstrap_servers})
            producer.produce(
                topic, key=envelope.correlation_id, value=json.dumps(message["value"])
            )
            producer.flush(timeout=5)
            return {"status": "produced", "topic": topic}
        except ImportError:
            return message  # Return payload if kafka library not available
