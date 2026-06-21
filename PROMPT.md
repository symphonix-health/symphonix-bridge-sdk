# CAID requirement prompt: symphonix-bridge-sdk

## Project role

`symphonix-bridge-sdk` is the Symphonix Health interoperability and governance
SDK for clinical workflow data exchange. It uses FHIR R4 as the canonical pivot
and bridges FHIR R4, HL7 v2, DICOM, X12, CDA, REST, Nexus A2A, MCP, Kafka, gRPC,
WebSocket, and SSE payloads through canonical envelopes.

## Clinical workflow scope

This repository handles clinical workflow evidence and must be treated as
safety relevant at repo scope:

- FHIR R4 canonical envelopes and profile conformance checks.
- HL7 v2, DICOM, X12, CDA, and REST adapter translation into and out of the
  canonical envelope.
- Terminology preservation, including LOINC and SNOMED CT bindings where
  present.
- Consent and data-sharing projection with fail-closed denial handling.
- Patient identity evidence and FHIR Patient binding helpers.
- FHIR Task projection for agent or workflow state.
- Safety-class metadata, clinical safety case checks, signal governance,
  human handoff packages, escalation state, audit records, and correlation IDs.
- Professional-documentation transport evidence such as provenance, consent,
  owner, freshness, next action, and review status.

## Boundary conditions

The SDK transports, normalizes, gates, and audits clinical workflow evidence. It
does not author final professional documents, choose therapy, assign acuity,
calculate severity, interpret studies, or replace qualified human review. Any
agent or downstream service consuming bridge evidence must preserve the envelope
metadata and keep AI or agent evidence as draft/supporting material until a
qualified human completes and signs the final record.

## CAID safety expectation

Because this repo handles FHIR, HL7, consent for data sharing, patient records,
and clinical safety metadata, CAID/CSAA should classify it at least as
`clinical_workflow`. `out_of_scope` or purely administrative results are
under-classification. A higher result must be investigated against the exact code
path that produced the signal before implementation proceeds.

## Verification gates

- Run `python -m caid.cli safety-scope --project-dir <repo> --full --format json`.
- Run the repo-local test suite and CAID `test-agent` gate after any adapter,
  envelope, consent, patient identity, signal governance, audit, or handoff
  change.
- Treat missing safety artefacts, missing consent evidence, missing real-service
  route evidence, or skipped generated-app gates as blocking.
