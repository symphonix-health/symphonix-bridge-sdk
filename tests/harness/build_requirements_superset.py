"""symphonix-bridge-sdk — Heterogeneous protocol translation SDK.

13 adapters: FHIR, HL7v2, DICOM, X12, CDA, REST, nexus_a2a, MCP, Kafka,
gRPC, WebSocket, SSE. FHIR R4 canonical pivot.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OUT = ROOT / "tests" / "harness" / "requirements_superset.json"


def _build() -> list[dict]:
    reqs: list[dict] = [
        {"requirement_id": "BSDK-001", "family": "A_PROMPT_PRESERVED",
         "title": "FHIR R4 canonical pivot",
         "statement": "SDK SHALL use FHIR R4 as the canonical pivot.",
         "category": "non-functional", "source": "README.md"},
        {"requirement_id": "BSDK-002", "family": "A_PROMPT_PRESERVED",
         "title": "CanonicalEnvelope shape",
         "statement": "SDK SHALL define a CanonicalEnvelope with payload + terminology + metadata.",
         "category": "functional", "source": "README.md"},
        {"requirement_id": "BSDK-003", "family": "A_PROMPT_PRESERVED",
         "title": "Any-to-any translation",
         "statement": "SDK SHALL support any-to-any translation across declared adapters.",
         "category": "functional", "source": "README.md"},
    ]

    families: dict[str, list[tuple[str, str]]] = {
        "B_FHIR_PIVOT": [
            ("FHIR R4 base profile", "Pivot SHALL be FHIR R4 conformant."),
            ("FHIR R5 transition plan", "Pivot SHALL document FHIR R5 transition plan."),
            ("LOINC code binding", "Terminology SHALL include LOINC bindings."),
            ("SNOMED CT code binding", "Terminology SHALL include SNOMED CT bindings."),
            ("ICD-10/11 code binding", "Terminology SHALL support ICD-10/11."),
            ("UCUM unit binding", "Quantitative observations SHALL bind UCUM units."),
            ("RxNorm code binding", "Medication codes SHALL bind RxNorm where applicable."),
            ("dm+d code binding", "UK medication codes SHALL bind dm+d."),
            ("CapabilityStatement publication", "FHIR endpoints SHALL publish CapabilityStatement."),
            ("Profile resolution registry", "Pivot SHALL maintain a profile resolution registry."),
        ],
        "C_ADAPTERS_INBOUND": [
            ("HL7 v2 MLLP inbound", "SDK SHALL accept HL7 v2 over MLLP."),
            ("DICOM C-FIND/C-STORE inbound", "SDK SHALL accept DICOM C-FIND / C-STORE."),
            ("X12 EDI inbound", "SDK SHALL accept X12 EDI."),
            ("CDA R2 inbound", "SDK SHALL accept CDA R2 documents."),
            ("REST/JSON inbound", "SDK SHALL accept generic REST/JSON."),
            ("Nexus A2A inbound", "SDK SHALL accept Nexus A2A messages."),
            ("MCP tool-call inbound", "SDK SHALL accept MCP tool calls."),
            ("Kafka inbound", "SDK SHALL consume Kafka topics."),
            ("gRPC inbound", "SDK SHALL accept gRPC requests."),
            ("WebSocket inbound", "SDK SHALL accept WebSocket messages."),
        ],
        "D_ADAPTERS_OUTBOUND": [
            ("HL7 v2 MLLP outbound", "SDK SHALL emit HL7 v2 over MLLP."),
            ("DICOM outbound", "SDK SHALL emit DICOM messages."),
            ("X12 EDI outbound", "SDK SHALL emit X12 EDI."),
            ("CDA R2 outbound", "SDK SHALL emit CDA R2 documents."),
            ("REST/JSON outbound", "SDK SHALL emit REST/JSON."),
            ("Nexus A2A outbound", "SDK SHALL emit Nexus A2A messages."),
            ("MCP tool-call outbound", "SDK SHALL emit MCP tool calls."),
            ("Kafka outbound", "SDK SHALL produce Kafka messages."),
            ("gRPC outbound", "SDK SHALL emit gRPC calls."),
            ("WebSocket outbound", "SDK SHALL emit WebSocket messages."),
            ("SSE outbound", "SDK SHALL emit SSE push messages."),
        ],
        "E_ENGINE": [
            ("Routing rule engine", "SDK SHALL include a routing rule engine."),
            ("Pluggable adapter registry", "Adapters SHALL be pluggable."),
            ("Per-route transformation pipeline", "Routes SHALL support transformation pipelines."),
            ("Validation per adapter", "Adapters SHALL validate inputs + outputs."),
            ("Error envelope normalisation", "Errors SHALL be normalised across adapters."),
            ("Dead-letter for poison messages", "Poison messages SHALL be DLQ'd."),
            ("Replay queue for retries", "Retries SHALL use a replay queue."),
            ("Idempotency key honouring", "Mutating routes SHALL honour Idempotency-Key."),
            ("Correlation ID propagation", "Correlation ID SHALL propagate across adapters."),
            ("Streaming transform", "Streaming transforms SHALL be supported."),
        ],
        "F_REGULATORY": [
            ("HIPAA Privacy Rule", "US deployments SHALL evidence HIPAA."),
            ("GDPR lawful basis", "EU deployments SHALL declare GDPR lawful basis."),
            ("UK DSPT compliance", "UK deployments SHALL evidence DSPT."),
            ("DCB 0129 / 0160", "UK clinical-claimed SHALL evidence DCB 0129 / 0160."),
            ("ISO 27001 ISMS", "Operators SHALL evidence ISO 27001 ISMS."),
            ("ISO 27701 PIMS", "Operators SHALL evidence ISO 27701 PIMS."),
            ("ISO 22301 BCMS", "Operators SHALL evidence ISO 22301 BCMS."),
            ("ISO 13485 QMS", "Where applicable, ISO 13485 QMS SHALL be evidenced."),
            ("Audit log retention", "Audit log retention SHALL be declared."),
            ("Right to be forgotten", "Erasure SHALL propagate through translated history."),
        ],
        "G_INTEROP": [
            ("OpenAPI publication", "REST API SHALL publish OpenAPI."),
            ("Adapter conformance suite", "Adapters SHALL ship a conformance suite."),
            ("HAPI FHIR test compatibility", "FHIR adapter SHALL be HAPI-compatible."),
            ("Healthcare.gov interop tests", "Where applicable, HC.gov interop tests SHALL be passed."),
            ("HL7 v2 conformance profile", "HL7 v2 adapter SHALL declare conformance profile."),
            ("DICOM conformance statement", "DICOM adapter SHALL ship conformance statement."),
            ("X12 implementation guide adherence", "X12 adapter SHALL adhere to documented IGs."),
            ("Bulk Data conformance", "FHIR Bulk Data SHALL be supported."),
            ("MCP server manifest", "MCP adapter SHALL publish server manifest."),
            ("A2A agent card", "Nexus A2A adapter SHALL publish agent card."),
        ],
        "H_OBSERVABILITY": [
            ("OTel traces", "All adapters SHALL emit OTel traces."),
            ("OTel metrics", "All adapters SHALL emit OTel metrics."),
            ("OTel logs", "All adapters SHALL emit OTel logs."),
            ("Per-adapter throughput metric", "Per-adapter throughput SHALL be emitted."),
            ("Per-adapter error rate metric", "Per-adapter error rate SHALL be emitted."),
            ("Translation latency histogram", "Translation latency SHALL be emitted as histogram."),
            ("DLQ depth metric", "DLQ depth SHALL be emitted."),
            ("Replay queue depth metric", "Replay queue depth SHALL be emitted."),
            ("Adapter health endpoint", "Each adapter SHALL expose a health endpoint."),
            ("Audit log per translation", "Each translation SHALL emit audit log."),
        ],
        "I_SECURITY": [
            ("OIDC JWT auth", "Endpoints SHALL be authenticated via OIDC JWT."),
            ("mTLS transport", "Endpoints SHALL support mTLS transport option."),
            ("Scope-based auth", "Endpoints SHALL apply scope-based authorisation."),
            ("Per-principal rate limit", "Endpoints SHALL apply per-principal rate limit."),
            ("Replay attack defence", "Idempotency-Key SHALL defend against replay."),
            ("Input validation", "Inputs SHALL be validated."),
            ("Output encoding safe", "Outputs SHALL be encoding-safe."),
            ("Secret rotation policy", "Secrets SHALL be rotated per policy."),
            ("Pen-test policy", "Operators SHALL evidence pen-test policy."),
            ("VDP", "Operators SHALL maintain a vulnerability disclosure programme."),
        ],
        "J_REA_BASELINE": [
            ("REA template registry coverage", "SDK SHALL trace consumed REA template families."),
            ("REA gap-filler ingestion", "SDK SHALL ingest REA gap-filler output."),
            ("REA coverage heatmap export", "SDK SHALL emit REA coverage heatmap."),
            ("REA derive_all batch run", "SDK SHALL support REA batch runs."),
            ("REA anomaly diagnostics", "SDK SHALL expose REA anomaly diagnostics."),
        ],
        "K_CROSS_CUTTING_NFR": [
            ("Helm chart parity", "SDK deployments SHALL be evidenced by an in-tree Helm chart."),
            ("SBOM generation", "Build SHALL emit SPDX SBOM."),
            ("DR RPO/RTO", "Operators SHALL declare RPO/RTO."),
            ("Container image signing", "Container images SHALL be signed."),
            ("Dependency scanning", "CI SHALL run dependency scanning."),
            ("Backups encrypted at rest", "Backups SHALL be encrypted at rest."),
            ("Incident response playbook", "Operators SHALL link to incident response playbook."),
            ("On-call schedule", "Operators SHALL maintain on-call schedule."),
            ("Status page", "Operators SHALL run a status page."),
            ("SLSA attestation", "Releases SHALL include SLSA supply-chain attestation."),
        ],
    }

    next_id = 1
    used = {r["requirement_id"] for r in reqs}
    for family, items in families.items():
        for title, statement in items:
            while True:
                rid = f"BSDK-{next_id + 100:03d}"
                next_id += 1
                if rid not in used:
                    break
            used.add(rid)
            reqs.append({
                "requirement_id": rid, "family": family,
                "title": title, "statement": statement,
                "category": "compliance" if family.startswith(("F_", "I_")) else
                            "functional" if family.startswith(("B_", "C_", "D_", "E_", "G_")) else
                            "non-functional",
                "source": family.split("_", 1)[1].replace("_", " ").title(),
            })
    return reqs


def main() -> None:
    reqs = _build()
    payload = {
        "schema_version": "BT_REQUIREMENTS_SUPERSET_V1",
        "metadata": {
            "subsystem": "symphonix-bridge-sdk",
            "requirement_count": len(reqs),
            "families": sorted({r["family"] for r in reqs}),
        },
        "requirements": reqs,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {OUT.name} — {len(reqs)} reqs across {len(payload['metadata']['families'])} families")


if __name__ == "__main__":
    main()
