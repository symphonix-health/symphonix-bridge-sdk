# Symphonix Bridge SDK & Conductor — Authoritative Requirements Superset (`REQUIREMENTS_SUPERSET.md`)

**Generated from**: `tests/harness/requirements_superset.json` and `docs/REQUIREMENTS.md`

| Requirement ID | Category | Priority | Title / Statement |
|---|---|---|---|
| `BSDK-001` | `non-functional` | `high` | SDK SHALL use FHIR R4 as the canonical pivot. |
| `BSDK-002` | `functional` | `high` | SDK SHALL define a CanonicalEnvelope with payload + terminology + metadata. |
| `BSDK-003` | `functional` | `high` | SDK SHALL support any-to-any translation across declared adapters. |
| `BSDK-101` | `functional` | `high` | Pivot SHALL be FHIR R4 conformant. |
| `BSDK-102` | `functional` | `high` | Pivot SHALL document FHIR R5 transition plan. |
| `BSDK-103` | `functional` | `high` | Terminology SHALL include LOINC bindings. |
| `BSDK-104` | `functional` | `high` | Terminology SHALL include SNOMED CT bindings. |
| `BSDK-105` | `functional` | `high` | Terminology SHALL support ICD-10/11. |
| `BSDK-106` | `functional` | `high` | Quantitative observations SHALL bind UCUM units. |
| `BSDK-107` | `functional` | `high` | Medication codes SHALL bind RxNorm where applicable. |
| `BSDK-108` | `functional` | `high` | UK medication codes SHALL bind dm+d. |
| `BSDK-109` | `functional` | `high` | FHIR endpoints SHALL publish CapabilityStatement. |
| `BSDK-110` | `functional` | `high` | Pivot SHALL maintain a profile resolution registry. |
| `BSDK-111` | `functional` | `high` | SDK SHALL accept HL7 v2 over MLLP. |
| `BSDK-112` | `functional` | `high` | SDK SHALL accept DICOM C-FIND / C-STORE. |
| `BSDK-113` | `functional` | `high` | SDK SHALL accept X12 EDI. |
| `BSDK-114` | `functional` | `high` | SDK SHALL accept CDA R2 documents. |
| `BSDK-115` | `functional` | `high` | SDK SHALL accept generic REST/JSON. |
| `BSDK-116` | `functional` | `high` | SDK SHALL accept Nexus A2A messages. |
| `BSDK-117` | `functional` | `high` | SDK SHALL accept MCP tool calls. |
| `BSDK-118` | `functional` | `high` | SDK SHALL consume Kafka topics. |
| `BSDK-119` | `functional` | `high` | SDK SHALL accept gRPC requests. |
| `BSDK-120` | `functional` | `high` | SDK SHALL accept WebSocket messages. |
| `BSDK-121` | `functional` | `high` | SDK SHALL emit HL7 v2 over MLLP. |
| `BSDK-122` | `functional` | `high` | SDK SHALL emit DICOM messages. |
| `BSDK-123` | `functional` | `high` | SDK SHALL emit X12 EDI. |
| `BSDK-124` | `functional` | `high` | SDK SHALL emit CDA R2 documents. |
| `BSDK-125` | `functional` | `high` | SDK SHALL emit REST/JSON. |
| `BSDK-126` | `functional` | `high` | SDK SHALL emit Nexus A2A messages. |
| `BSDK-127` | `functional` | `high` | SDK SHALL emit MCP tool calls. |
| `BSDK-128` | `functional` | `high` | SDK SHALL produce Kafka messages. |
| `BSDK-129` | `functional` | `high` | SDK SHALL emit gRPC calls. |
| `BSDK-130` | `functional` | `high` | SDK SHALL emit WebSocket messages. |
| `BSDK-131` | `functional` | `high` | SDK SHALL emit SSE push messages. |
| `BSDK-132` | `functional` | `high` | SDK SHALL include a routing rule engine. |
| `BSDK-133` | `functional` | `high` | Adapters SHALL be pluggable. |
| `BSDK-134` | `functional` | `high` | Routes SHALL support transformation pipelines. |
| `BSDK-135` | `functional` | `high` | Adapters SHALL validate inputs + outputs. |
| `BSDK-136` | `functional` | `high` | Errors SHALL be normalised across adapters. |
| `BSDK-137` | `functional` | `high` | Poison messages SHALL be DLQ'd. |
| `BSDK-138` | `functional` | `high` | Retries SHALL use a replay queue. |
| `BSDK-139` | `functional` | `high` | Mutating routes SHALL honour Idempotency-Key. |
| `BSDK-140` | `functional` | `high` | Correlation ID SHALL propagate across adapters. |
| `BSDK-141` | `functional` | `high` | Streaming transforms SHALL be supported. |
| `BSDK-142` | `compliance` | `high` | US deployments SHALL evidence HIPAA. |
| `BSDK-143` | `compliance` | `high` | EU deployments SHALL declare GDPR lawful basis. |
| `BSDK-144` | `compliance` | `high` | UK deployments SHALL evidence DSPT. |
| `BSDK-145` | `compliance` | `high` | UK clinical-claimed SHALL evidence DCB 0129 / 0160. |
| `BSDK-146` | `compliance` | `high` | Operators SHALL evidence ISO 27001 ISMS. |
| `BSDK-147` | `compliance` | `high` | Operators SHALL evidence ISO 27701 PIMS. |
| `BSDK-148` | `compliance` | `high` | Operators SHALL evidence ISO 22301 BCMS. |
| `BSDK-149` | `compliance` | `high` | Where applicable, ISO 13485 QMS SHALL be evidenced. |
| `BSDK-150` | `compliance` | `high` | Audit log retention SHALL be declared. |
| `BSDK-151` | `compliance` | `high` | Erasure SHALL propagate through translated history. |
| `BSDK-152` | `functional` | `high` | REST API SHALL publish OpenAPI. |
| `BSDK-153` | `functional` | `high` | Adapters SHALL ship a conformance suite. |
| `BSDK-154` | `functional` | `high` | FHIR adapter SHALL be HAPI-compatible. |
| `BSDK-155` | `functional` | `high` | Where applicable, HC.gov interop tests SHALL be passed. |
| `BSDK-156` | `functional` | `high` | HL7 v2 adapter SHALL declare conformance profile. |
| `BSDK-157` | `functional` | `high` | DICOM adapter SHALL ship conformance statement. |
| `BSDK-158` | `functional` | `high` | X12 adapter SHALL adhere to documented IGs. |
| `BSDK-159` | `functional` | `high` | FHIR Bulk Data SHALL be supported. |
| `BSDK-160` | `functional` | `high` | MCP adapter SHALL publish server manifest. |
| `BSDK-161` | `functional` | `high` | Nexus A2A adapter SHALL publish agent card. |
| `BSDK-162` | `non-functional` | `high` | All adapters SHALL emit OTel traces. |
| `BSDK-163` | `non-functional` | `high` | All adapters SHALL emit OTel metrics. |
| `BSDK-164` | `non-functional` | `high` | All adapters SHALL emit OTel logs. |
| `BSDK-165` | `non-functional` | `high` | Per-adapter throughput SHALL be emitted. |
| `BSDK-166` | `non-functional` | `high` | Per-adapter error rate SHALL be emitted. |
| `BSDK-167` | `non-functional` | `high` | Translation latency SHALL be emitted as histogram. |
| `BSDK-168` | `non-functional` | `high` | DLQ depth SHALL be emitted. |
| `BSDK-169` | `non-functional` | `high` | Replay queue depth SHALL be emitted. |
| `BSDK-170` | `non-functional` | `high` | Each adapter SHALL expose a health endpoint. |
| `BSDK-171` | `non-functional` | `high` | Each translation SHALL emit audit log. |
| `BSDK-172` | `compliance` | `high` | Endpoints SHALL be authenticated via OIDC JWT. |
| `BSDK-173` | `compliance` | `high` | Endpoints SHALL support mTLS transport option. |
| `BSDK-174` | `compliance` | `high` | Endpoints SHALL apply scope-based authorisation. |
| `BSDK-175` | `compliance` | `high` | Endpoints SHALL apply per-principal rate limit. |
| `BSDK-176` | `compliance` | `high` | Idempotency-Key SHALL defend against replay. |
| `BSDK-177` | `compliance` | `high` | Inputs SHALL be validated. |
| `BSDK-178` | `compliance` | `high` | Outputs SHALL be encoding-safe. |
| `BSDK-179` | `compliance` | `high` | Secrets SHALL be rotated per policy. |
| `BSDK-180` | `compliance` | `high` | Operators SHALL evidence pen-test policy. |
| `BSDK-181` | `compliance` | `high` | Operators SHALL maintain a vulnerability disclosure programme. |
| `BSDK-182` | `non-functional` | `high` | SDK SHALL trace consumed REA template families. |
| `BSDK-183` | `non-functional` | `high` | SDK SHALL ingest REA gap-filler output. |
| `BSDK-184` | `non-functional` | `high` | SDK SHALL emit REA coverage heatmap. |
| `BSDK-185` | `non-functional` | `high` | SDK SHALL support REA batch runs. |
| `BSDK-186` | `non-functional` | `high` | SDK SHALL expose REA anomaly diagnostics. |
| `BSDK-187` | `non-functional` | `high` | SDK deployments SHALL be evidenced by an in-tree Helm chart. |
| `BSDK-188` | `non-functional` | `high` | Build SHALL emit SPDX SBOM. |
| `BSDK-189` | `non-functional` | `high` | Operators SHALL declare RPO/RTO. |
| `BSDK-190` | `non-functional` | `high` | Container images SHALL be signed. |
| `BSDK-191` | `non-functional` | `high` | CI SHALL run dependency scanning. |
| `BSDK-192` | `non-functional` | `high` | Backups SHALL be encrypted at rest. |
| `BSDK-193` | `non-functional` | `high` | Operators SHALL link to incident response playbook. |
| `BSDK-194` | `non-functional` | `high` | Operators SHALL maintain on-call schedule. |
| `BSDK-195` | `non-functional` | `high` | Operators SHALL run a status page. |
| `BSDK-196` | `non-functional` | `high` | Releases SHALL include SLSA supply-chain attestation. |
| `FR-BSDK-001` | `functional` | `high` | SDK SHALL provide a canonical FHIR R4 pivot type that source-system payloads can be mapped into. |
| `FR-BSDK-002` | `functional` | `high` | SDK SHALL emit a bridge envelope with payload, terminology, and metadata intact after pivot. |
| `FR-BSDK-003` | `functional` | `high` | SDK SHALL validate required payload, terminology, and metadata fields on every envelope. |
| `FR-BSDK-004` | `functional` | `high` | SDK SHALL enable any-to-any adapter translation via the canonical pivot without pairwise mapping. |
| `FR-BSDK-005` | `functional` | `high` | SDK SHALL check FHIR R4 profile conformance and return a conformant envelope OR a validation failure. |
| `FR-BSDK-006` | `functional` | `high` | SDK SHALL document a FHIR R5 transition plan keeping R4 behaviour stable. |
| `FR-BSDK-007` | `functional` | `high` | SDK SHALL trace compatibility changes through requirements and canonical scenarios. |
| `FR-BSDK-008` | `functional` | `high` | SDK SHALL register source and target adapters that consume the canonical pivot. |
| `NFR-BSDK-001` | `non-functional` | `high` | SDK MUST be import-stable across all sibling repos (no breaking pivot changes within R4 lifecycle). |
| `NFR-BSDK-002` | `non-functional` | `high` | SDK MUST refuse to call sibling systems directly; cross-system traffic via bullettrain.connectors.* or api_gateway hub. |
| `NFR-BSDK-003` | `non-functional` | `high` | SDK MUST be pip-installable and import-clean (no implicit network IO at import time). |
| `NFR-BSDK-004` | `non-functional` | `high` | Envelope serialisation MUST be deterministic (stable field ordering for audit replay). |
| `DS-001` | `functional` | `high` | Seeded alignment evidence for DS-001 |
| `DS-002` | `functional` | `high` | Seeded alignment evidence for DS-002 |
| `DS-003` | `functional` | `high` | Seeded alignment evidence for DS-003 |
| `DS-101` | `functional` | `high` | Seeded alignment evidence for DS-101 |
| `DS-102` | `functional` | `high` | Seeded alignment evidence for DS-102 |
| `DS-103` | `functional` | `high` | Seeded alignment evidence for DS-103 |
| `DS-104` | `functional` | `high` | Seeded alignment evidence for DS-104 |
| `DS-105` | `functional` | `high` | Seeded alignment evidence for DS-105 |
| `DS-106` | `functional` | `high` | Seeded alignment evidence for DS-106 |
| `DS-107` | `functional` | `high` | Seeded alignment evidence for DS-107 |
| `DS-108` | `functional` | `high` | Seeded alignment evidence for DS-108 |
| `DS-109` | `functional` | `high` | Seeded alignment evidence for DS-109 |
| `DS-110` | `functional` | `high` | Seeded alignment evidence for DS-110 |
| `DS-111` | `functional` | `high` | Seeded alignment evidence for DS-111 |
| `DS-112` | `functional` | `high` | Seeded alignment evidence for DS-112 |
| `DS-113` | `functional` | `high` | Seeded alignment evidence for DS-113 |
| `DS-114` | `functional` | `high` | Seeded alignment evidence for DS-114 |
| `DS-115` | `functional` | `high` | Seeded alignment evidence for DS-115 |
| `DS-116` | `functional` | `high` | Seeded alignment evidence for DS-116 |
| `DS-117` | `functional` | `high` | Seeded alignment evidence for DS-117 |
| `DS-118` | `functional` | `high` | Seeded alignment evidence for DS-118 |
| `DS-119` | `functional` | `high` | Seeded alignment evidence for DS-119 |
| `DS-120` | `functional` | `high` | Seeded alignment evidence for DS-120 |
| `DS-121` | `functional` | `high` | Seeded alignment evidence for DS-121 |
| `DS-122` | `functional` | `high` | Seeded alignment evidence for DS-122 |
| `DS-123` | `functional` | `high` | Seeded alignment evidence for DS-123 |
| `DS-124` | `functional` | `high` | Seeded alignment evidence for DS-124 |
| `DS-125` | `functional` | `high` | Seeded alignment evidence for DS-125 |
| `DS-126` | `functional` | `high` | Seeded alignment evidence for DS-126 |
| `DS-127` | `functional` | `high` | Seeded alignment evidence for DS-127 |
| `DS-128` | `functional` | `high` | Seeded alignment evidence for DS-128 |
| `DS-129` | `functional` | `high` | Seeded alignment evidence for DS-129 |
| `DS-130` | `functional` | `high` | Seeded alignment evidence for DS-130 |
| `DS-131` | `functional` | `high` | Seeded alignment evidence for DS-131 |
| `DS-132` | `functional` | `high` | Seeded alignment evidence for DS-132 |
| `DS-133` | `functional` | `high` | Seeded alignment evidence for DS-133 |
| `DS-134` | `functional` | `high` | Seeded alignment evidence for DS-134 |
| `DS-135` | `functional` | `high` | Seeded alignment evidence for DS-135 |
| `DS-136` | `functional` | `high` | Seeded alignment evidence for DS-136 |
| `DS-137` | `functional` | `high` | Seeded alignment evidence for DS-137 |
| `DS-138` | `functional` | `high` | Seeded alignment evidence for DS-138 |
| `DS-139` | `functional` | `high` | Seeded alignment evidence for DS-139 |
| `DS-140` | `functional` | `high` | Seeded alignment evidence for DS-140 |
| `DS-141` | `functional` | `high` | Seeded alignment evidence for DS-141 |
| `DS-142` | `functional` | `high` | Seeded alignment evidence for DS-142 |
| `DS-143` | `functional` | `high` | Seeded alignment evidence for DS-143 |
| `DS-144` | `functional` | `high` | Seeded alignment evidence for DS-144 |
| `DS-145` | `functional` | `high` | Seeded alignment evidence for DS-145 |
| `DS-146` | `functional` | `high` | Seeded alignment evidence for DS-146 |
| `DS-147` | `functional` | `high` | Seeded alignment evidence for DS-147 |
| `DS-148` | `functional` | `high` | Seeded alignment evidence for DS-148 |
| `DS-149` | `functional` | `high` | Seeded alignment evidence for DS-149 |
| `DS-150` | `functional` | `high` | Seeded alignment evidence for DS-150 |
| `DS-151` | `functional` | `high` | Seeded alignment evidence for DS-151 |
| `DS-152` | `functional` | `high` | Seeded alignment evidence for DS-152 |
| `DS-153` | `functional` | `high` | Seeded alignment evidence for DS-153 |
| `DS-154` | `functional` | `high` | Seeded alignment evidence for DS-154 |
| `DS-155` | `functional` | `high` | Seeded alignment evidence for DS-155 |
| `DS-156` | `functional` | `high` | Seeded alignment evidence for DS-156 |
| `DS-157` | `functional` | `high` | Seeded alignment evidence for DS-157 |
| `DS-158` | `functional` | `high` | Seeded alignment evidence for DS-158 |
| `DS-159` | `functional` | `high` | Seeded alignment evidence for DS-159 |
| `DS-160` | `functional` | `high` | Seeded alignment evidence for DS-160 |
| `DS-161` | `functional` | `high` | Seeded alignment evidence for DS-161 |
| `DS-162` | `functional` | `high` | Seeded alignment evidence for DS-162 |
| `DS-163` | `functional` | `high` | Seeded alignment evidence for DS-163 |
| `DS-164` | `functional` | `high` | Seeded alignment evidence for DS-164 |
| `DS-165` | `functional` | `high` | Seeded alignment evidence for DS-165 |
| `DS-166` | `functional` | `high` | Seeded alignment evidence for DS-166 |
| `DS-167` | `functional` | `high` | Seeded alignment evidence for DS-167 |
| `DS-168` | `functional` | `high` | Seeded alignment evidence for DS-168 |
| `DS-169` | `functional` | `high` | Seeded alignment evidence for DS-169 |
| `DS-170` | `functional` | `high` | Seeded alignment evidence for DS-170 |
| `DS-171` | `functional` | `high` | Seeded alignment evidence for DS-171 |
| `DS-172` | `functional` | `high` | Seeded alignment evidence for DS-172 |
| `DS-173` | `functional` | `high` | Seeded alignment evidence for DS-173 |
| `DS-174` | `functional` | `high` | Seeded alignment evidence for DS-174 |
| `DS-175` | `functional` | `high` | Seeded alignment evidence for DS-175 |
| `DS-176` | `functional` | `high` | Seeded alignment evidence for DS-176 |
| `DS-177` | `functional` | `high` | Seeded alignment evidence for DS-177 |
| `DS-178` | `functional` | `high` | Seeded alignment evidence for DS-178 |
| `DS-179` | `functional` | `high` | Seeded alignment evidence for DS-179 |
| `DS-180` | `functional` | `high` | Seeded alignment evidence for DS-180 |
| `DS-181` | `functional` | `high` | Seeded alignment evidence for DS-181 |
| `DS-182` | `functional` | `high` | Seeded alignment evidence for DS-182 |
| `DS-183` | `functional` | `high` | Seeded alignment evidence for DS-183 |
| `DS-184` | `functional` | `high` | Seeded alignment evidence for DS-184 |
| `DS-185` | `functional` | `high` | Seeded alignment evidence for DS-185 |
| `DS-186` | `functional` | `high` | Seeded alignment evidence for DS-186 |
| `DS-187` | `functional` | `high` | Seeded alignment evidence for DS-187 |
| `DS-188` | `functional` | `high` | Seeded alignment evidence for DS-188 |
| `DS-189` | `functional` | `high` | Seeded alignment evidence for DS-189 |
| `DS-190` | `functional` | `high` | Seeded alignment evidence for DS-190 |
| `DS-191` | `functional` | `high` | Seeded alignment evidence for DS-191 |
| `DS-192` | `functional` | `high` | Seeded alignment evidence for DS-192 |
| `DS-193` | `functional` | `high` | Seeded alignment evidence for DS-193 |
| `DS-194` | `functional` | `high` | Seeded alignment evidence for DS-194 |
| `DS-195` | `functional` | `high` | Seeded alignment evidence for DS-195 |
| `DS-196` | `functional` | `high` | Seeded alignment evidence for DS-196 |
| `FR-001` | `functional` | `high` | Seeded alignment evidence for FR-001 |
| `FR-002` | `functional` | `high` | Seeded alignment evidence for FR-002 |
| `FR-003` | `functional` | `high` | Seeded alignment evidence for FR-003 |
| `FR-004` | `functional` | `high` | Seeded alignment evidence for FR-004 |
| `FR-005` | `functional` | `high` | Seeded alignment evidence for FR-005 |
| `FR-006` | `functional` | `high` | Seeded alignment evidence for FR-006 |
| `FR-007` | `functional` | `high` | Seeded alignment evidence for FR-007 |
| `FR-008` | `functional` | `high` | Seeded alignment evidence for FR-008 |
| `FR-009` | `functional` | `high` | Seeded alignment evidence for FR-009 |
| `FR-010` | `functional` | `high` | Seeded alignment evidence for FR-010 |
| `FR-011` | `functional` | `high` | Seeded alignment evidence for FR-011 |
| `FR-012` | `functional` | `high` | Seeded alignment evidence for FR-012 |
| `FR-013` | `functional` | `high` | Seeded alignment evidence for FR-013 |
| `FR-014` | `functional` | `high` | Seeded alignment evidence for FR-014 |
| `FR-015` | `functional` | `high` | Seeded alignment evidence for FR-015 |
| `FR-016` | `functional` | `high` | Seeded alignment evidence for FR-016 |
| `NFR-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-001 |
| `NFR-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-002 |
| `NFR-CO-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-CO-001 |
| `NFR-CO-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-CO-002 |
| `NFR-FL-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-FL-001 |
| `NFR-FL-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-FL-002 |
| `NFR-IC-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-IC-001 |
| `NFR-MA-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-MA-001 |
| `NFR-MA-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-MA-002 |
| `NFR-MA-003` | `non-functional` | `high` | Seeded alignment evidence for NFR-MA-003 |
| `NFR-MA-004` | `non-functional` | `high` | Seeded alignment evidence for NFR-MA-004 |
| `NFR-PE-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-PE-001 |
| `NFR-RE-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-RE-001 |
| `NFR-RE-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-RE-002 |
| `NFR-RE-003` | `non-functional` | `high` | Seeded alignment evidence for NFR-RE-003 |
| `NFR-SA-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-SA-001 |
| `NFR-SA-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-SA-002 |
| `NFR-SE-001` | `non-functional` | `high` | Seeded alignment evidence for NFR-SE-001 |
| `NFR-SE-002` | `non-functional` | `high` | Seeded alignment evidence for NFR-SE-002 |
| `NFR-SE-003` | `non-functional` | `high` | Seeded alignment evidence for NFR-SE-003 |
| `NFR-SE-004` | `non-functional` | `high` | Seeded alignment evidence for NFR-SE-004 |
| `NFR-SE-005` | `non-functional` | `high` | Seeded alignment evidence for NFR-SE-005 |
| `SPID-FR-001` | `functional` | `high` | Seeded alignment evidence for SPID-FR-001 |
| `SPID-FR-002` | `functional` | `high` | Seeded alignment evidence for SPID-FR-002 |
| `SPID-FR-003` | `functional` | `high` | Seeded alignment evidence for SPID-FR-003 |
| `SPID-FR-004` | `functional` | `high` | Seeded alignment evidence for SPID-FR-004 |
| `SPID-FR-005` | `functional` | `high` | Seeded alignment evidence for SPID-FR-005 |
| `SPID-FR-006` | `functional` | `high` | Seeded alignment evidence for SPID-FR-006 |
| `SPID-FR-007` | `functional` | `high` | Seeded alignment evidence for SPID-FR-007 |
| `SPID-FR-008` | `functional` | `high` | Seeded alignment evidence for SPID-FR-008 |
| `SPID-FR-009` | `functional` | `high` | Seeded alignment evidence for SPID-FR-009 |
| `SPID-FR-010` | `functional` | `high` | Seeded alignment evidence for SPID-FR-010 |
| `SPID-FR-011` | `functional` | `high` | Seeded alignment evidence for SPID-FR-011 |
| `SPID-FR-012` | `functional` | `high` | Seeded alignment evidence for SPID-FR-012 |
| `SPID-FR-013` | `functional` | `high` | Seeded alignment evidence for SPID-FR-013 |
| `SPID-FR-014` | `functional` | `high` | Seeded alignment evidence for SPID-FR-014 |
| `SPID-FR-015` | `functional` | `high` | Seeded alignment evidence for SPID-FR-015 |
| `SPID-FR-016` | `functional` | `high` | Seeded alignment evidence for SPID-FR-016 |
| `SPID-NFR-001` | `non-functional` | `high` | Seeded alignment evidence for SPID-NFR-001 |
| `SPID-NFR-002` | `non-functional` | `high` | Seeded alignment evidence for SPID-NFR-002 |
