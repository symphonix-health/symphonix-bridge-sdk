# symphonix-bridge-sdk — Requirements

**Derived from**: [`docs/USE_CASES.md`](USE_CASES.md) (8 documented use cases UC-BSDK-001..008) + [`docs/architecture/patient-identity-closed-loop.md`](architecture/patient-identity-closed-loop.md) + repository code.

This is the **canonical, version-pinned** requirements catalogue for the symphonix-bridge-sdk. Each requirement is traced to a use case and to implementation evidence in this repo.

## Functional requirements

| ID | Requirement | Use Case | Code evidence |
|---|---|---|---|
| FR-BSDK-001 | SDK SHALL provide a canonical FHIR R4 pivot type that source-system payloads can be mapped into. | UC-BSDK-001 | `src/bridge/canonical.py` (FHIR R4 envelope) |
| FR-BSDK-002 | SDK SHALL emit a bridge envelope with payload, terminology, and metadata intact after pivot. | UC-BSDK-001 | bridge envelope schema |
| FR-BSDK-003 | SDK SHALL validate required payload, terminology, and metadata fields on every envelope. | UC-BSDK-002 | envelope validator |
| FR-BSDK-004 | SDK SHALL enable any-to-any adapter translation via the canonical pivot without pairwise mapping between every service pair. | UC-BSDK-003 | adapter registration + translation API |
| FR-BSDK-005 | SDK SHALL check FHIR R4 profile conformance and return a conformant envelope OR a validation failure. | UC-BSDK-004 | FHIR profile validators |
| FR-BSDK-006 | SDK SHALL document a FHIR R5 transition plan keeping R4 behaviour stable while documenting future compatibility work. | UC-BSDK-005 | R5 transition ADR |
| FR-BSDK-007 | SDK SHALL trace compatibility changes through requirements and canonical scenarios. | UC-BSDK-005 | traceability matrix |
| FR-BSDK-008 | SDK SHALL register source and target adapters that consume the canonical pivot. | UC-BSDK-003 | adapter registry |

## Use case → FR map

| Use case | Title | Maps to FR |
|---|---|---|
| UC-BSDK-001 | Canonical FHIR pivot | FR-BSDK-001, FR-BSDK-002 |
| UC-BSDK-002 | Canonical envelope contract | FR-BSDK-003 |
| UC-BSDK-003 | Any-to-any adapter translation | FR-BSDK-004, FR-BSDK-008 |
| UC-BSDK-004 | FHIR profile conformance | FR-BSDK-005 |
| UC-BSDK-005 | FHIR R5 transition readiness | FR-BSDK-006, FR-BSDK-007 |

## Non-functional requirements

| ID | Requirement | Rationale |
|---|---|---|
| NFR-BSDK-001 | SDK MUST be import-stable across all sibling repos (no breaking pivot changes within R4 lifecycle). | Consumer count = 26+ sibling repos |
| NFR-BSDK-002 | SDK MUST refuse to call sibling systems directly — all cross-system traffic via `bullettrain.connectors.*` or api_gateway hub per BulletTrain Integration Constitution. | [CLAUDE.md](../CLAUDE.md) |
| NFR-BSDK-003 | SDK MUST be pip-installable and import-clean (no implicit network IO at import time). | Library invariant |
| NFR-BSDK-004 | Envelope serialisation MUST be deterministic (stable field ordering for audit replay). | Audit invariant |

## Use cases

Full preconditions, main flow, postconditions for UC-BSDK-001 through UC-BSDK-005 are in [USE_CASES.md](USE_CASES.md).

## Gate compatibility

This file allows the canonical gate at `caid-agent/scripts/check_seeding_alignment.py` to detect requirements at its default `docs/REQUIREMENTS.md` path. Use-case fidelity remains in [USE_CASES.md](USE_CASES.md).
