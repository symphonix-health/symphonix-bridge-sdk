# Architecture specification

Repository: `symphonix-bridge-sdk`.

## Purpose

This architecture specification is reverse-engineered from the repo codebase and aligned to the requirement and use-case evidence. It records the repo boundary, evidence flow, governance controls, REA requirements-quality feedback, and verification paths that support the seeded healthcare platform profile.

## Architecture inputs

- Functional requirements: `docs/specifications/functional-requirements.md` (238 IDs).
- Non-functional requirements: `docs/specifications/non-functional-requirements.md` (28 IDs).
- Design specification: `docs/specifications/design-specification.md`.
- Canonical use-case matrix: `tests/harness/reduced_json_matrices/seeded_alignment_trace.14col.json`.
- Source scenario matrix: `tests/harness/json_matrices/seeded_alignment_trace_scenarios.json`.
- Seed profile: `seed_data/seeded_requirement_traceability.json`.
- Traceability ledger: `seeded_alignment_trace.py`.

## High-level architecture diagram

```mermaid
flowchart LR
  classDef ingest fill:#EFF6FF,stroke:#2563EB,color:#0B1F4D,stroke-width:1px
  classDef foundation fill:#F0FDF4,stroke:#2F7D32,color:#143B16,stroke-width:1px
  classDef intelligence fill:#FFF7ED,stroke:#F59E0B,color:#5F370E,stroke-width:1px
  classDef improvement fill:#F5F3FF,stroke:#7C3AED,color:#27105F,stroke-width:1px
  classDef execution fill:#ECFEFF,stroke:#0891B2,color:#083344,stroke-width:1px
  classDef governance fill:#FAF5FF,stroke:#6D28D9,color:#25115A,stroke-width:1px
  classDef outcome fill:#0B1F4D,stroke:#0B1F4D,color:#FFFFFF,stroke-width:1px

  subgraph A["1) Requirements and signal ingestion"]
    A1["Functional requirements\nCanonical use cases"]
    A2["Non-functional requirements\nSafety, privacy, reliability"]
    A3["Seeded healthcare profile\nTenant, role, care setting"]
  end
  subgraph B["2) Foundation and standardization"]
    B1["Traceability ledger\nRequirement to evidence map"]
    B2["Canonical matrices\n14-column use-case rows"]
    B3["Codebase evidence\nRepo-owned implementation paths"]
  end
  subgraph C["3) Design intelligence"]
    C1["Reverse-engineered surfaces\nAPI, UI, docs, workflow"]
    C2["Symphonix design rules\nClinical safety invariants"]
    C3["REA requirements QA\nISO 29148, ISO 25010, smells"]
  end
  subgraph D["4) Implementation and execution"]
    D1["Symphonix Bridge Sdk repo boundary"]
    D2["Seed data and tests\nReal internal paths"]
    D3["Operational evidence\nRunbooks, telemetry, reports"]
  end
  subgraph E["5) Evaluation and learning"]
  E1["Repo-local specification tests"]
  E2["FP/FN audit\nFalse-positive and false-negative checks"]
  E3["Global RTM\nCoverage and gap report"]
  E4["Self-improvement feedback\nREA scope and repo evidence"]
  end
  G["Clinical governance\nSafety, risk, audit, quality registry"]
  O["Outcomes\nSafer workflows, consistent quality, learning health system"]

  A1 --> B1
  A2 --> B1
  A3 --> B2
  B1 --> C1
  B2 --> C1
  B3 --> C1
  C1 --> D1
  C2 --> D1
  C3 --> D1
  D1 --> D2
  D1 --> D3
  D2 --> E1
  D3 --> E2
  E1 --> E3
  E2 --> E3
  E3 --> E4
  E4 --> A1
  E4 --> C3
  G --> A2
  G --> C2
  E3 --> G
  E3 --> O

  class A1,A2,A3 ingest
  class B1,B2,B3 foundation
  class C1,C2,C3 intelligence
  class D1,D2,D3 execution
  class E1,E2,E3,E4 improvement
  class G governance
  class O outcome
```

## Low-level architecture diagram

```mermaid
flowchart TB
  classDef spec fill:#EFF6FF,stroke:#2563EB,color:#0B1F4D,stroke-width:1px
  classDef data fill:#F0FDF4,stroke:#2F7D32,color:#143B16,stroke-width:1px
  classDef design fill:#FFF7ED,stroke:#F59E0B,color:#5F370E,stroke-width:1px
  classDef runtime fill:#ECFEFF,stroke:#0891B2,color:#083344,stroke-width:1px
  classDef test fill:#F5F3FF,stroke:#7C3AED,color:#27105F,stroke-width:1px
  classDef govern fill:#FAF5FF,stroke:#6D28D9,color:#25115A,stroke-width:1px

  subgraph S["Specification layer"]
    S1["Functional requirements spec"]
    S2["Non-functional requirements spec"]
    S3["Design specification"]
    S4["Architecture specification"]
    S5["REA scope model\nSRS, quality, traceability"]
  end
  subgraph M["Matrix and seed layer"]
    M1["BT V1 14-column matrix"]
    M2["Source scenario matrix"]
    M3["Healthcare superset seed profile"]
    M4["Seeded requirement traceability data"]
  end
  subgraph R["Symphonix Bridge Sdk implementation boundary"]
    R1["Repo-owned source paths"]
    R2["API, UI, workflow, or documentation surfaces"]
    R3["Configuration and deployment profiles"]
  end
  subgraph T["Verification layer"]
    T1["Traceability ledger test"]
    T2["Specification alignment test"]
    T3["Existing repo tests and harness checks"]
    T4["FP/FN audit evidence"]
  end
  G1["Governance controls\nAudit, safety, privacy, quality"]

  S1 --> M1
  S2 --> M1
  S3 --> R2
  S4 --> R1
  S5 --> S1
  S5 --> S2
  S5 --> S3
  M1 --> M2
  M1 --> T1
  M3 --> M4
  M4 --> T1
  R1 --> T3
  R2 --> T3
  R3 --> G1
  T1 --> T2
  T2 --> T4
  T3 --> T4
  G1 --> S2
  G1 --> S3

  class S1,S2,S3,S4,S5 spec
  class M1,M2,M3,M4 data
  class R1,R2,R3 runtime
  class T1,T2,T3,T4 test
  class G1 govern
```

## Repo boundary

- Package or project name: `symphonix-bridge-sdk`
- Observed surfaces: documentation, seeded_data, workflow_or_matrix.
- Observed frameworks and tools: fastapi, pydantic, pytest, ruff.

Observed implementation evidence:
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
- `src/bridge_sdk/adapters/kafka_adapter.py`
- `src/bridge_sdk/adapters/mcp_adapter.py`
- `src/bridge_sdk/adapters/nexus_a2a.py`
- `src/bridge_sdk/adapters/rest.py`
- `src/bridge_sdk/adapters/sse.py`
- `src/bridge_sdk/adapters/websocket_adapter.py`

## Architecture decisions

- Requirements and canonical use cases are treated as the controlling contract for repo behaviour.
- REA requirements QA is treated as part of the self-improvement loop for scope, wording, quality attributes, and traceability.
- The seeded traceability ledger is an evidence map; it does not replace service code or behavioural tests.
- Tenant, role, care-setting, jurisdiction, and integration differences are represented as deployment profiles.
- Clinical governance and quality controls remain visible at both architecture levels.
- Runtime readiness requires real internal routes, data, permissions, and telemetry where the repo owns those services.

## Verification

- Run `python -m pytest tests/test_seeded_alignment_traceability.py tests/test_specification_alignment.py`.
- Where the repo has `tests/test_bullettrain_v1_matrix.py`, run it with the generated tests.
- Run the workspace seeding audit to refresh the global RTM and FP/FN evidence.

## Change control

Architecture changes must update the diagrams, FR/NFR specifications, design specification, canonical matrices, seed evidence, and tests in the same change when they affect requirement behaviour or use-case coverage.
