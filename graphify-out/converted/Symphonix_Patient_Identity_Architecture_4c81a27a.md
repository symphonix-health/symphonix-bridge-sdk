<!-- converted from Symphonix_Patient_Identity_Architecture.docx -->

Symphonix Patient Identity Closed Loop
Architecture decision, requirements, use cases, traceability matrix, and test harness

# Executive Decision
Symphonix Health should standardise BulletTrain, Shared HealthRecord, Client Registry, and all patient-data siblings on SPID. SPID has the 10-digit modulus-11 shape used by the UK NHS number format, but it is a Symphonix identifier with a Symphonix FHIR system. The Client Registry is the only issuing authority. Other services maintain local projections and fail closed when patient identity is invalid, missing, under review, restricted, or deceased.
# Architecture Summary
- Client Registry owns SPID allocation, aliases, lifecycle status, duplicate/confused-record review, merge/link, restricted status, and death status.
- Shared HealthRecord and siblings own clinical/domain records but key patient context by SPID.
- Patient creation is propagated through a transactional outbox and patient.identity.* events.
- Agents can detect, explain, and recommend identity corrections, but deterministic services and human approval own safety-critical state changes.
- Closed-loop reconciliation compares registry and subscriber projections and replays events or opens review tasks for drift.
# NHS/PDS Lessons Applied


# Core Requirements


# Use Case Scenarios

# Implementation Plan

# Harness
Fast contract suite:
python -m pytest tests/test_patient_identity.py tests/harness/patient_identity/test_patient_identity_contract.py -q
Post-migration static enforcement:
$env:SYMPHONIX_PATIENT_IDENTITY_ENFORCE='1'; python -m pytest tests/harness/patient_identity/test_patient_identity_contract.py -q
# Sources

| Field | Value |
| --- | --- |
| Canonical identifier | SPID - Symphonix Patient Identifier |
| Identifier system | https://fhir.symphonix.health/Id/patient |
| NHS Number role | External alias only, never the internal master patient id |
| Requirements | 18 |
| Scenarios | 12 |
| NHS Pattern | Symphonix Design Rule |
| --- | --- |
| PDS master demographics | Use Client Registry as the Symphonix master patient identity service. |
| Duplicate records | Merge confirmed duplicates to one SPID and retain aliases. |
| Confused records | Put records under review and require NBO-style human approval before correction. |
| Sensitive flag / stop-noting | Represent as restricted identity status and suppress location/contact disclosure. |
| Death status | Stop active care loops and notifications without deleting the record. |
| Incorrect death status | Correct through audited reinstatement or death-status correction events. |
| ID | Priority | Family | Requirement | Scenario Count |
| --- | --- | --- | --- | --- |
| SPID-FR-001 | P0 | Master Patient Identity | Client Registry is issuing authority | 2 |
| SPID-FR-002 | P0 | Master Patient Identity | NHS-style checksum shape | 2 |
| SPID-FR-003 | P0 | Master Patient Identity | Not an NHS number | 2 |
| SPID-FR-004 | P0 | Fhir Canonical | FHIR Patient identity binding | 2 |
| SPID-FR-005 | P1 | Fhir Canonical | Canonical envelope carries patient identity | 1 |
| SPID-FR-006 | P0 | Propagation | Creation event propagation | 2 |
| SPID-FR-007 | P0 | Propagation | Subscriber projection contract | 2 |
| SPID-FR-008 | P0 | Safety Controls | Reject unknown or inactive patient writes | 3 |
| SPID-FR-009 | P0 | Propagation | Idempotent outbox delivery | 2 |
| SPID-FR-010 | P0 | Confused Records | Confused record workflow | 1 |
| SPID-FR-011 | P0 | Confused Records | Merge and link audit | 2 |
| SPID-FR-012 | P0 | Restricted Records | Stop-note and sensitive status | 1 |
| SPID-FR-013 | P0 | Deceased Patients | Death status propagation | 1 |
| SPID-FR-014 | P0 | Audit | Identity lifecycle audit | 3 |
| SPID-FR-015 | P0 | Agent Governance | Agent recommendations require deterministic guardrails | 2 |
| SPID-FR-016 | P1 | Reconciliation | Closed-loop reconciliation | 1 |
| SPID-NFR-001 | P0 | Security Privacy | Minimum disclosure | 1 |
| SPID-NFR-002 | P0 | Operability | Migration without patient-record loss | 1 |
| Use Case | Type | Priority | Subsystem | Title |
| --- | --- | --- | --- | --- |
| patient_identity_POS_0001 | Positive | P0 | client-registry | Create patient with registry-issued SPID |
| patient_identity_POS_0002 | Positive | P0 | shared-health-record | Creation event upserts Shared HealthRecord projection |
| patient_identity_POS_0003 | Positive | P1 | bridge-sdk | FHIR resource carries canonical SPID |
| patient_identity_NEG_0004 | Negative | P0 | patient-data-service | Clinical write with unknown patient is rejected |
| patient_identity_EDG_0005 | Edge | P0 | client-registry | Confused record enters human approval workflow |
| patient_identity_EDG_0006 | Edge | P0 | patient-data-service | Restricted patient suppresses location and automated contact |
| patient_identity_EDG_0007 | Edge | P0 | closed-loop-care | Death status stops active care loops without deleting record |
| patient_identity_EDG_0008 | Edge | P1 | reconciliation | Closed-loop reconciliation repairs projection drift |
| patient_identity_NEG_0009 | Negative | P0 | agent-governance | Agent identity mutation without approval is blocked |
| patient_identity_POS_0010 | Positive | P0 | migration | Legacy identifiers migrate to one SPID with aliases |
| patient_identity_NEG_0002 | Negative | P0 | client-registry | Invalid SPID checksum is rejected |
| patient_identity_NEG_0003 | Negative | P0 | bridge-sdk | NHS Number namespace is rejected as internal identity |
| Phase | Theme | Action | Priority |
| --- | --- | --- | --- |
| 1 | Shared contract | Adopt bridge_sdk.patient_identity, event schemas, and envelope patient metadata. | P0 |
| 2 | BulletTrain registry and SHR | Make Client Registry the SPID authority and stop local PAT-* creation in SHR. | P0 |
| 3 | Sibling migration | Replace internal nhs_number and PAT-* identifiers with SPID while preserving aliases. | P0 |
| 4 | Closed-loop governance | Add reconciliation, human approval, audit, and agent recommendation guardrails. | P1 |
| Source | URL |
| --- | --- |
| NHS PDS | https://digital.nhs.uk/services/personal-demographics-service |
| PDS National Back Office | https://digital.nhs.uk/services/personal-demographics-service/national-back-office-for-the-personal-demographics-service |
| PDS data quality incidents | https://digital.nhs.uk/services/personal-demographics-service/national-back-office-for-the-personal-demographics-service/data-quality-incidents |
| Access restriction / S-flag | https://digital.nhs.uk/services/personal-demographics-service/restricting-access-to-a-patients-demographic-record |
| NHS number format | https://digital.nhs.uk/services/personal-demographics-service/nhs-number |
| NHS Data Dictionary modulus-11 | https://v2.datadictionary.nhs.uk/data_dictionary/data_field_notes/n/nhs_number_de.asp%40shownav%3D0.html |
| NHS Notify death/flag suppression | https://webcms.prod.nhsnotify.national.nhs.uk/using-nhs-notify/recipients-you-cannot-message |
| Records Management Code | https://transform.england.nhs.uk/information-governance/guidance/records-management-code/records-management-code-of-practice/ |