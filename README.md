<p align="center">
  <img src="brand/symphonix-bridge-sdk-logo.svg" alt="symphonix-bridge-sdk logo" width="420">
</p>

<!-- tagline:start -->
<p align="center"><em>12 protocol adapters around a FHIR R4 pivot.</em></p>
<!-- tagline:end -->
# Symphonix Bridge SDK


## Recent Enhancements

- `b80d7be` Add V-model L2/L3 integration tests

_Updated 2026-05-09 — generated from `git log` since last README revision. Filtered to feature/architecture commits; chore/test/wip omitted._

## Supported protocols

| Adapter | Direction | Notes |
|---|---|---|
| `fhir` | in / out | FHIR R4 REST (pivot representation) |
| `hl7v2` | in / out | HL7 v2 MLLP (ADT, ORM, ORU, …) |
| `dicom` | in / out | DICOM C-FIND / C-STORE / WADO metadata |
| `x12` | in / out | X12 EDI (837, 835, 270/271, 278, 850, …) |
| `cda` | in / out | CDA R2 clinical documents |
| `rest` | in / out | Generic REST / JSON |
| `nexus_a2a` | in / out | Nexus Agent-to-Agent protocol (BulletTrain) |
| `mcp` | in / out | Model Context Protocol (AI agent tool calls) |
| `kafka` | in / out | Apache Kafka message streams |
| `grpc` | in / out | gRPC service calls |
| `websocket` | in / out | WebSocket bidirectional |
| `sse` | out | Server-Sent Events push |

## Installation

```bash
# Minimal (FHIR R4 REST + Nexus A2A only)
pip install symphonix-bridge-sdk

# With all protocol adapters
pip install "symphonix-bridge-sdk[all]"

# BulletTrain HIE integration (FastAPI mount)
pip install "symphonix-bridge-sdk[bullettrain]"

# From source (dev)
git clone https://github.com/symphonix-health/symphonix-bridge-sdk
cd symphonix-bridge-sdk
pip install -e .[all,dev]
```

## Quick example

```python
import asyncio
from bridge_sdk.engine import BridgeEngine
from bridge_sdk.adapters.hl7v2 import Hl7v2Adapter
from bridge_sdk.adapters.fhir import FhirAdapter

engine = BridgeEngine()
engine.register("hl7v2", Hl7v2Adapter())
engine.register("fhir", FhirAdapter(base_url="http://hapi.fhir.org/baseR4"))

async def main():
    # Translate an HL7 v2 ADT^A01 admission to FHIR R4 Encounter
    envelope = await engine.translate(
        source_protocol="hl7v2",
        target_protocol="fhir",
        raw_payload=b"MSH|^~\\&|SENDING|...",
    )
    print(envelope.fhir_resources)

asyncio.run(main())
```

## Engine features

| Feature | Detail |
|---|---|
| FHIR R4 canonical pivot | All adapters translate to/from `CanonicalEnvelope` |
| LOINC / SNOMED preservation | Terminology codes survive every protocol hop |
| Circuit breaker | Per-endpoint with configurable failure threshold + half-open recovery |
| Backpressure semaphore | Per-endpoint concurrency limiter (G21) |
| Retry / fallback (G11) | Automatic retry with exponential back-off |
| Consent propagation (G4) | Data-sharing consent flags forwarded on every hop |
| Priority routing (G10) | Critical findings / STAT messages routed ahead of routine |
| Data residency (G17) | Envelope rejected if target region violates residency policy |
| Idempotency | `idempotency_key` prevents duplicate delivery |
| Correlation | `correlation_id` links request/response across hops |

## CanonicalEnvelope

```python
class CanonicalEnvelope(BaseModel):
    envelope_id: str          # UUID
    correlation_id: str       # COR-<hex12>
    idempotency_key: str | None
    timestamp: str            # ISO-8601 UTC
    source_protocol: str
    target_protocol: str
    direction: TranslationDirection   # inbound | outbound
    fhir_resources: list[dict]        # FHIR R4 resource list
    loinc_codes: list[dict[str, str]]
    snomed_codes: list[dict[str, str]]
    raw_source: Any                   # original payload (dead-letter / debug)
```

## Tests

```bash
cd symphonix-bridge-sdk
python -m pytest -q
```

## Requirements

- Python ≥ 3.11
- Core: `httpx`, `pydantic ≥ 2.0`
- Optional adapters: `hl7`, `pydicom`, `confluent-kafka`, `grpcio`, `websockets`, `mcp`
