# Non-functional requirements specification

Repository: `symphonix-bridge-sdk`.

## Scope

This specification records the repo-specific non-functional requirements observed from requirement IDs, code ownership paths, seeded healthcare profiles, and canonical use-case coverage. It uses the REA Agent quality scope model: ISO/IEC 25010-style quality attributes, healthcare safety and privacy overlays, traceability, and feedback from audit evidence into future requirement refinement.

## Source evidence

- Requirement ledger: `seeded_alignment_trace.py`
- Healthcare superset profile: `tests/harness/healthcare_requirements_superset.json`
- Canonical matrix: `tests/harness/reduced_json_matrices/seeded_alignment_trace.14col.json`
- Seed evidence: `seed_data/seeded_requirement_traceability.json`
- Framework and tooling evidence: fastapi, pydantic, pytest, ruff.

Observed implementation paths:
- `brand/index.html`
- `conftest.py`
- `outputs/patient_identity/build_patient_identity_docx.py`
- `seeded_alignment_trace.py`
- `src/bridge_sdk/__init__.py`
- `src/bridge_sdk/adapters/__init__.py`
- `src/bridge_sdk/adapters/base.py`
- `src/bridge_sdk/adapters/cda.py`
- `src/bridge_sdk/adapters/dicom_adapter.py`
- `src/bridge_sdk/adapters/fhir.py`
- `src/bridge_sdk/adapters/grpc_adapter.py`
- `src/bridge_sdk/adapters/hl7v2.py`

## Non-functional requirement IDs

- `NFR-001`, `NFR-002`, `NFR-BSDK-001`, `NFR-BSDK-002`, `NFR-BSDK-003`, `NFR-BSDK-004`, `NFR-CO-001`, `NFR-CO-002`
- `NFR-FL-001`, `NFR-FL-002`, `NFR-IC-001`, `NFR-MA-001`, `NFR-MA-002`, `NFR-MA-003`, `NFR-MA-004`, `NFR-PE-001`
- `NFR-RE-001`, `NFR-RE-002`, `NFR-RE-003`, `NFR-SA-001`, `NFR-SA-002`, `NFR-SE-001`, `NFR-SE-002`, `NFR-SE-003`
- `NFR-SE-004`, `NFR-SE-005`, `SPID-NFR-001`, `SPID-NFR-002`

## Non-functional requirement clauses

| Requirement ID | Canonical use-case evidence | Specification obligation |
|---|---|---|
| `NFR-001` | `SA-SBS-00223`, `SA-SBS-SRC-00223` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-002` | `SA-SBS-00224`, `SA-SBS-SRC-00224` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-BSDK-001` | `compliance-policy_scenarios-compliance_policy_NEG_0086`, `compliance-policy_scenarios-compliance_policy_NEG_0090`, `compliance-policy_scenarios-compliance_policy_NEG_0094` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-BSDK-002` | `compliance-policy_scenarios-compliance_policy_NEG_0087`, `compliance-policy_scenarios-compliance_policy_NEG_0091`, `compliance-policy_scenarios-compliance_policy_NEG_0095` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-BSDK-003` | `compliance-policy_scenarios-compliance_policy_NEG_0088`, `compliance-policy_scenarios-compliance_policy_NEG_0092`, `compliance_policy_canonical-compliance_policy_NEG_0088` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-BSDK-004` | `compliance-policy_scenarios-compliance_policy_NEG_0089`, `compliance-policy_scenarios-compliance_policy_NEG_0093`, `compliance_policy_canonical-compliance_policy_NEG_0089` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-CO-001` | `SA-SBS-00229`, `SA-SBS-SRC-00229` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-CO-002` | `SA-SBS-00230`, `SA-SBS-SRC-00230` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-FL-001` | `SA-SBS-00231`, `SA-SBS-SRC-00231` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-FL-002` | `SA-SBS-00232`, `SA-SBS-SRC-00232` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-IC-001` | `SA-SBS-00233`, `SA-SBS-SRC-00233` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-MA-001` | `SA-SBS-00234`, `SA-SBS-SRC-00234` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-MA-002` | `SA-SBS-00235`, `SA-SBS-SRC-00235` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-MA-003` | `SA-SBS-00236`, `SA-SBS-SRC-00236` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-MA-004` | `SA-SBS-00237`, `SA-SBS-SRC-00237` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-PE-001` | `SA-SBS-00238`, `SA-SBS-SRC-00238` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-RE-001` | `SA-SBS-00239`, `SA-SBS-SRC-00239` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-RE-002` | `SA-SBS-00240`, `SA-SBS-SRC-00240` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-RE-003` | `SA-SBS-00241`, `SA-SBS-SRC-00241` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SA-001` | `SA-SBS-00242`, `SA-SBS-SRC-00242` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SA-002` | `SA-SBS-00243`, `SA-SBS-SRC-00243` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SE-001` | `SA-SBS-00244`, `SA-SBS-SRC-00244` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SE-002` | `SA-SBS-00245`, `SA-SBS-SRC-00245` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SE-003` | `SA-SBS-00246`, `SA-SBS-SRC-00246` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SE-004` | `SA-SBS-00247`, `SA-SBS-SRC-00247` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `NFR-SE-005` | `SA-SBS-00248`, `SA-SBS-SRC-00248` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-NFR-001` | `SA-SBS-00265`, `SA-SBS-SRC-00265` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-NFR-002` | `SA-SBS-00266`, `SA-SBS-SRC-00266` | Maintain repo-owned quality attribute evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |

## Quality model

| Quality area | Repo obligation | Verification evidence |
|---|---|---|
| Safety and clinical governance | Preserve auditable decisions, role-aware workflows, and escalation paths for clinical or operational use. | Requirement IDs, canonical matrices, and repo-local traceability tests. |
| Security and privacy | Keep tenant, role, and data-scope boundaries explicit. Do not use internal mocks as readiness evidence. | Traceability ledger, seed profiles, and FP/FN audit output. |
| Reliability and observability | Keep failures inspectable through logs, metrics, reports, or documented operational evidence where applicable. | Architecture specification, tests, and audit reports. |
| Performance and scalability | Treat throughput and latency targets as deployment-profile constraints unless the repo owns concrete runtime thresholds. | Repo tests, harness matrices, and deployment documentation. |
| Accessibility and usability | Clinical and administrative surfaces must remain keyboard-operable and readable under the Symphonix Health design guidance. | Design specification and UI/accessibility tests where present. |

## Acceptance rule

Every non-functional requirement above must remain traceable to the canonical matrix and seeded evidence. Any repo change that affects safety, privacy, reliability, performance, accessibility, or operational posture must update this specification and the aligned test evidence.
