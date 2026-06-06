# Architecture, setup, operations, testing, and seeding

Repository: `symphonix-bridge-sdk`.

## Architecture

Architecture is specified in `docs/specifications/architecture-specification.md`. That file contains the required high-level and low-level architecture diagrams and links the repo boundary to functional requirements, non-functional requirements, design constraints, canonical use cases, implementation evidence, tests, and seeded data.

## Setup

Use the repo's existing package manager and test runner. Where no repo-specific bootstrap is present, the seeded alignment checks use only Python standard-library modules and can be run with `python -m pytest tests/test_seeded_alignment_traceability.py tests/test_specification_alignment.py`.

## Operations

Operational readiness depends on the real service, documentation, or website artefacts already owned by the repository. The alignment ledger and generated specifications do not replace runtime monitoring, logs, traces, dashboards, alerts, or service-specific runbooks.

## Testing

Run the repo's existing test suite, then run `python -m pytest tests/test_seeded_alignment_traceability.py tests/test_specification_alignment.py` to verify requirement-to-specification, requirement-to-use-case, requirement-to-implementation, requirement-to-test, and requirement-to-seed evidence.

## Seeding

Seed evidence is recorded in `seed_data/seeded_requirement_traceability.json` using configurable healthcare tenant and care-setting profiles. Internal service tests must use real seeded routes, data, permissions, and telemetry rather than mocks or placeholder backends.

## Specification set

- Functional requirements: `docs/specifications/functional-requirements.md`
- Non-functional requirements: `docs/specifications/non-functional-requirements.md`
- Design specification: `docs/specifications/design-specification.md`
- Architecture specification: `docs/specifications/architecture-specification.md`
- Requirement traceability: `docs/specifications/seeded-requirement-traceability.md`
