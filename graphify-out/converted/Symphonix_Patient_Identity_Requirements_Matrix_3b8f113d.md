<!-- converted from Symphonix_Patient_Identity_Requirements_Matrix.xlsx -->

## Sheet: Summary
| Symphonix Patient Identity Closed Loop |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| Metric | Value | Notes |  |  |  |
| Canonical identifier | SPID | Symphonix Patient Identifier |  |  |  |
| FHIR identifier system | https://fhir.symphonix.health/Id/patient | Internal master identity namespace |  |  |  |
| Requirement count | 18 | All rows trace to scenarios |  |  |  |
| Scenario count | 12 | Positive, negative, and edge coverage |  |  |  |
| P0 requirements | 16 | Safety-critical and migration-critical |  |  |  |
| Static enforcement | Opt-in | Set SYMPHONIX_PATIENT_IDENTITY_ENFORCE=1 after repo migration |  |  |  |
| Requirements By Family | Count |  |  |  |  |
| AGENT_GOVERNANCE | 1 |  |  |  |  |
| AUDIT | 1 |  |  |  |  |
| CONFUSED_RECORDS | 2 |  |  |  |  |
| DECEASED_PATIENTS | 1 |  |  |  |  |
| FHIR_CANONICAL | 2 |  |  |  |  |
| MASTER_PATIENT_IDENTITY | 3 |  |  |  |  |
| OPERABILITY | 1 |  |  |  |  |
| PROPAGATION | 3 |  |  |  |  |
| RECONCILIATION | 1 |  |  |  |  |
| RESTRICTED_RECORDS | 1 |  |  |  |  |
| SAFETY_CONTROLS | 1 |  |  |  |  |
| SECURITY_PRIVACY | 1 |  |  |  |  |
## Sheet: Requirements
| Requirement ID | Priority | Family | Category | Title | Statement | Scenario Count | Scenario IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SPID-FR-001 | P0 | MASTER_PATIENT_IDENTITY | functional | Client Registry is issuing authority | Client Registry SHALL be the only service that creates or assigns the canonical Symphonix Patient Identifier. | 2 | patient_identity_POS_0001, patient_identity_NEG_0004 |
| SPID-FR-002 | P0 | MASTER_PATIENT_IDENTITY | functional | NHS-style checksum shape | SPID SHALL be exactly 10 digits and SHALL pass the modulus-11 check digit algorithm used by the UK NHS number format. | 2 | patient_identity_POS_0001, patient_identity_NEG_0002 |
| SPID-FR-003 | P0 | MASTER_PATIENT_IDENTITY | compliance | Not an NHS number | SPID SHALL NOT be labelled, stored, emitted, or documented as an NHS Number. | 2 | patient_identity_POS_0001, patient_identity_NEG_0003 |
| SPID-FR-004 | P0 | FHIR_CANONICAL | functional | FHIR Patient identity binding | FHIR Patient.id and Patient.identifier SHALL include the SPID for every patient-data exchange. | 2 | patient_identity_POS_0001, patient_identity_POS_0003 |
| SPID-FR-005 | P1 | FHIR_CANONICAL | functional | Canonical envelope carries patient identity | Bridge envelopes and agent messages carrying patient data SHALL expose the canonical SPID as structured metadata. | 1 | patient_identity_POS_0003 |
| SPID-FR-006 | P0 | PROPAGATION | functional | Creation event propagation | Client Registry SHALL publish a patient.identity.created event for every committed patient creation. | 2 | patient_identity_POS_0001, patient_identity_POS_0002 |
| SPID-FR-007 | P0 | PROPAGATION | functional | Subscriber projection contract | Every patient-data service SHALL maintain a local patient context keyed by SPID and reconciled from identity events. | 2 | patient_identity_POS_0002, patient_identity_EDG_0008 |
| SPID-FR-008 | P0 | SAFETY_CONTROLS | safety | Reject unknown or inactive patient writes | Patient-data services SHALL reject non-emergency clinical writes when SPID is unknown, invalid, inactive, confused, restricted without permitted purpose, or deceased. | 3 | patient_identity_NEG_0004, patient_identity_EDG_0006, patient_identity_EDG_0007 |
| SPID-FR-009 | P0 | PROPAGATION | reliability | Idempotent outbox delivery | Identity events SHALL use idempotency keys and replayable outbox semantics across EventBus, hub, Nexus A2A, and subscriber adapters. | 2 | patient_identity_POS_0002, patient_identity_EDG_0008 |
| SPID-FR-010 | P0 | CONFUSED_RECORDS | safety | Confused record workflow | Potential confused records SHALL be placed under review and resolved by an NBO-style human approval workflow before merge, split, or reassignment. | 1 | patient_identity_EDG_0005 |
| SPID-FR-011 | P0 | CONFUSED_RECORDS | functional | Merge and link audit | Confirmed duplicates SHALL be merged or linked with alias retention, event replay, and immutable audit history. | 2 | patient_identity_EDG_0005, patient_identity_EDG_0008 |
| SPID-FR-012 | P0 | RESTRICTED_RECORDS | privacy | Stop-note and sensitive status | Restricted access, historically described as stop-noting, SHALL be represented as a sensitive/restricted identity state and propagated to services. | 1 | patient_identity_EDG_0006 |
| SPID-FR-013 | P0 | DECEASED_PATIENTS | safety | Death status propagation | Formal and informal death status SHALL be modelled, audited, and propagated without deleting the patient record. | 1 | patient_identity_EDG_0007 |
| SPID-FR-014 | P0 | AUDIT | compliance | Identity lifecycle audit | Every identity lifecycle transition SHALL emit an immutable audit record with actor, system, reason, correlation id, and before/after state. | 3 | patient_identity_POS_0001, patient_identity_EDG_0005, patient_identity_EDG_0007 |
| SPID-FR-015 | P0 | AGENT_GOVERNANCE | safety | Agent recommendations require deterministic guardrails | Agents MAY detect, reconcile, and recommend patient identity fixes, but SHALL NOT autonomously create identifiers, merge records, remove restrictions, or change death status. | 2 | patient_identity_EDG_0005, patient_identity_NEG_0009 |
| SPID-FR-016 | P1 | RECONCILIATION | reliability | Closed-loop reconciliation | A scheduled closed-loop reconciliation SHALL compare Client Registry with all patient-data projections and open remediation tasks for drift. | 1 | patient_identity_EDG_0008 |
| SPID-NFR-001 | P0 | SECURITY_PRIVACY | non-functional | Minimum disclosure | Patient identity propagation SHALL disclose only fields needed by each subscriber purpose and SHALL carry consent and purpose-of-use metadata. | 1 | patient_identity_EDG_0006 |
| SPID-NFR-002 | P0 | OPERABILITY | non-functional | Migration without patient-record loss | Migration from mpiId, nationalID, nhs_number, and local PAT-* identifiers SHALL preserve aliases and map every patient-data record to exactly one active SPID or one explicit under-review exception. | 1 | patient_identity_POS_0010 |
## Sheet: Scenarios
| Use Case ID | Category | Priority | Subsystem | Requirement IDs | Title | Automation Status | Duration Sec | Expected Events |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| patient_identity_POS_0001 | Positive | P0 | client-registry | SPID-FR-001, SPID-FR-002, SPID-FR-003, SPID-FR-004, SPID-FR-006, SPID-FR-014 | Create patient with registry-issued SPID | automated | 10 | patient.identity.created |
| patient_identity_POS_0002 | Positive | P0 | shared-health-record | SPID-FR-006, SPID-FR-007, SPID-FR-009 | Creation event upserts Shared HealthRecord projection | automated | 8 | patient.projection.upserted |
| patient_identity_POS_0003 | Positive | P1 | bridge-sdk | SPID-FR-004, SPID-FR-005 | FHIR resource carries canonical SPID | automated | 3 | bridge.patient_identity.validated |
| patient_identity_NEG_0004 | Negative | P0 | patient-data-service | SPID-FR-001, SPID-FR-008 | Clinical write with unknown patient is rejected | automated | 5 | patient.identity.write_blocked |
| patient_identity_EDG_0005 | Edge | P0 | client-registry | SPID-FR-010, SPID-FR-011, SPID-FR-014, SPID-FR-015 | Confused record enters human approval workflow | automated | 20 | patient.identity.confusion_detected |
| patient_identity_EDG_0006 | Edge | P0 | patient-data-service | SPID-FR-008, SPID-FR-012, SPID-NFR-001 | Restricted patient suppresses location and automated contact | automated | 10 | patient.identity.restricted |
| patient_identity_EDG_0007 | Edge | P0 | closed-loop-care | SPID-FR-008, SPID-FR-013, SPID-FR-014 | Death status stops active care loops without deleting record | automated | 15 | patient.identity.deceased |
| patient_identity_EDG_0008 | Edge | P1 | reconciliation | SPID-FR-007, SPID-FR-009, SPID-FR-011, SPID-FR-016 | Closed-loop reconciliation repairs projection drift | automated | 30 | patient.identity.reconciled |
| patient_identity_NEG_0009 | Negative | P0 | agent-governance | SPID-FR-015 | Agent identity mutation without approval is blocked | automated | 5 | patient.identity.agent_action_blocked |
| patient_identity_POS_0010 | Positive | P0 | migration | SPID-NFR-002 | Legacy identifiers migrate to one SPID with aliases | manual_until_migration_window | 60 | patient.identity.aliases_backfilled |
| patient_identity_NEG_0002 | Negative | P0 | client-registry | SPID-FR-002 | Invalid SPID checksum is rejected | automated | 3 | patient.identity.validation_failed |
| patient_identity_NEG_0003 | Negative | P0 | bridge-sdk | SPID-FR-003 | NHS Number namespace is rejected as internal identity | automated | 3 | bridge.patient_identity.validation_failed |
## Sheet: Migration Backlog
| Repo / Area | Current Pattern | Target Change | Priority | Readiness Gate |
| --- | --- | --- | --- | --- |
| BulletTrain Client Registry | mpiId UUID, nationalID, duplicate/confusion tables | Make SPID the clinical patient id; preserve mpiId and nationalID as aliases; add outbox lifecycle events | P0 | Creation emits patient.identity.created with SPID and idempotency key |
| BulletTrain Shared HealthRecord | Local patient_id and PAT-* creation | Consume registry creation events; reject local patient creation and invalid SPID writes | P0 | No generate_id("PAT-") path remains for patients |
| Appointment / Screening / EPS / Maternity / Triage siblings | PAT-* and nhs_number field usage | Rename internal identity fields to patient_id/SPID and keep NHS Number as external alias only | P0 | Static harness enforce mode has zero findings |
| Bridge SDK / Nexus A2A | Canonical envelope has no explicit patient identity metadata | Add patient_id, identifier_system, identity_version, lifecycle_status to patient-data envelopes | P1 | Adapter tests extract SPID from FHIR and metadata |
| Agent workspaces | Identity reasoning possible without hard guardrails | Agents recommend only; merge, split, restriction removal, and death correction require human approval | P0 | Unauthorized A2A identity mutation is denied |
## Sheet: Source Notes
| Source | Use In Architecture | URL / Path |
| --- | --- | --- |
| NHS Personal Demographics Service | PDS as national master demographic database and NBO data-quality model | https://digital.nhs.uk/services/personal-demographics-service |
| NHS PDS National Back Office | Data quality incidents, duplicate records, confused records, incorrect death status | https://digital.nhs.uk/services/personal-demographics-service/national-back-office-for-the-personal-demographics-service |
| NHS Data Dictionary | 10-digit modulus-11 checksum pattern | https://v2.datadictionary.nhs.uk/data_dictionary/data_field_notes/n/nhs_number_de.asp%40shownav%3D0.html |
| NHS access restriction guidance | Sensitive status / S-flag handling as modern stop-note equivalent | https://digital.nhs.uk/services/personal-demographics-service/restricting-access-to-a-patients-demographic-record |
| NHS Notify | Suppression for flagged records and patient death status | https://webcms.prod.nhsnotify.national.nhs.uk/using-nhs-notify/recipients-you-cannot-message |
| Bridge SDK architecture doc | Target architecture, migration plan, and harness commands | docs/architecture/patient-identity-closed-loop.md |