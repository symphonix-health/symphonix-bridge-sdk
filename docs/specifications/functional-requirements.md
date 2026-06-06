# Functional requirements specification

Repository: `symphonix-bridge-sdk`.

## Scope

This specification is reverse-engineered from the repo codebase, existing requirement IDs, canonical use-case matrices, seeded traceability ledger, and repo-local tests. It uses the REA Agent requirements-engineering scope model: ISO/IEC/IEEE 29148-style requirement structure, explicit traceability, and requirement-quality feedback into the canonical matrices.

## Source evidence

- Requirement ledger: `seeded_alignment_trace.py`
- Canonical 14-column matrix: `tests/harness/reduced_json_matrices/seeded_alignment_trace.14col.json`
- Source scenario matrix: `tests/harness/json_matrices/seeded_alignment_trace_scenarios.json`
- Seed evidence: `seed_data/seeded_requirement_traceability.json`
- Package or project name: `symphonix-bridge-sdk`
- Reverse-engineered surfaces: documentation, seeded_data, workflow_or_matrix.

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

Observed matrix artefacts:
- `tests/harness/reduced_json_matrices/compliance-policy_scenarios.14col.json`
- `tests/harness/reduced_json_matrices/compliance_policy_canonical.14col.json`
- `tests/harness/reduced_json_matrices/seeded_alignment_trace.14col.json`
- `tests/harness/json_matrices/compliance-policy_scenarios.json`
- `tests/harness/json_matrices/seeded_alignment_trace_scenarios.json`
- `tests/harness/canonical_matrices/compliance_policy_canonical.json`

## Functional requirement IDs

- `BSDK-001`, `BSDK-002`, `BSDK-003`, `BSDK-101`, `BSDK-102`, `BSDK-103`, `BSDK-104`, `BSDK-105`
- `BSDK-106`, `BSDK-107`, `BSDK-108`, `BSDK-109`, `BSDK-110`, `BSDK-111`, `BSDK-112`, `BSDK-113`
- `BSDK-114`, `BSDK-115`, `BSDK-116`, `BSDK-117`, `BSDK-118`, `BSDK-119`, `BSDK-120`, `BSDK-121`
- `BSDK-122`, `BSDK-123`, `BSDK-124`, `BSDK-125`, `BSDK-126`, `BSDK-127`, `BSDK-128`, `BSDK-129`
- `BSDK-130`, `BSDK-131`, `BSDK-132`, `BSDK-133`, `BSDK-134`, `BSDK-135`, `BSDK-136`, `BSDK-137`
- `BSDK-138`, `BSDK-139`, `BSDK-140`, `BSDK-141`, `BSDK-142`, `BSDK-143`, `BSDK-144`, `BSDK-145`
- `BSDK-146`, `BSDK-147`, `BSDK-148`, `BSDK-149`, `BSDK-150`, `BSDK-151`, `BSDK-152`, `BSDK-153`
- `BSDK-154`, `BSDK-155`, `BSDK-156`, `BSDK-157`, `BSDK-158`, `BSDK-159`, `BSDK-160`, `BSDK-161`
- `BSDK-162`, `BSDK-163`, `BSDK-164`, `BSDK-165`, `BSDK-166`, `BSDK-167`, `BSDK-168`, `BSDK-169`
- `BSDK-170`, `BSDK-171`, `BSDK-172`, `BSDK-173`, `BSDK-174`, `BSDK-175`, `BSDK-176`, `BSDK-177`
- `BSDK-178`, `BSDK-179`, `BSDK-180`, `BSDK-181`, `BSDK-182`, `BSDK-183`, `BSDK-184`, `BSDK-185`
- `BSDK-186`, `BSDK-187`, `BSDK-188`, `BSDK-189`, `BSDK-190`, `BSDK-191`, `BSDK-192`, `BSDK-193`
- `BSDK-194`, `BSDK-195`, `BSDK-196`, `DS-001`, `DS-002`, `DS-003`, `DS-101`, `DS-102`
- `DS-103`, `DS-104`, `DS-105`, `DS-106`, `DS-107`, `DS-108`, `DS-109`, `DS-110`
- `DS-111`, `DS-112`, `DS-113`, `DS-114`, `DS-115`, `DS-116`, `DS-117`, `DS-118`
- `DS-119`, `DS-120`, `DS-121`, `DS-122`, `DS-123`, `DS-124`, `DS-125`, `DS-126`
- `DS-127`, `DS-128`, `DS-129`, `DS-130`, `DS-131`, `DS-132`, `DS-133`, `DS-134`
- `DS-135`, `DS-136`, `DS-137`, `DS-138`, `DS-139`, `DS-140`, `DS-141`, `DS-142`
- `DS-143`, `DS-144`, `DS-145`, `DS-146`, `DS-147`, `DS-148`, `DS-149`, `DS-150`
- `DS-151`, `DS-152`, `DS-153`, `DS-154`, `DS-155`, `DS-156`, `DS-157`, `DS-158`
- `DS-159`, `DS-160`, `DS-161`, `DS-162`, `DS-163`, `DS-164`, `DS-165`, `DS-166`
- `DS-167`, `DS-168`, `DS-169`, `DS-170`, `DS-171`, `DS-172`, `DS-173`, `DS-174`
- `DS-175`, `DS-176`, `DS-177`, `DS-178`, `DS-179`, `DS-180`, `DS-181`, `DS-182`
- `DS-183`, `DS-184`, `DS-185`, `DS-186`, `DS-187`, `DS-188`, `DS-189`, `DS-190`
- `DS-191`, `DS-192`, `DS-193`, `DS-194`, `DS-195`, `DS-196`, `FR-001`, `FR-002`
- `FR-003`, `FR-004`, `FR-005`, `FR-006`, `FR-007`, `FR-008`, `FR-009`, `FR-010`
- `FR-011`, `FR-012`, `FR-013`, `FR-014`, `FR-015`, `FR-016`, `FR-BSDK-001`, `FR-BSDK-002`
- `FR-BSDK-003`, `FR-BSDK-004`, `FR-BSDK-005`, `FR-BSDK-006`, `FR-BSDK-007`, `FR-BSDK-008`, `SPID-FR-001`, `SPID-FR-002`
- `SPID-FR-003`, `SPID-FR-004`, `SPID-FR-005`, `SPID-FR-006`, `SPID-FR-007`, `SPID-FR-008`, `SPID-FR-009`, `SPID-FR-010`
- `SPID-FR-011`, `SPID-FR-012`, `SPID-FR-013`, `SPID-FR-014`, `SPID-FR-015`, `SPID-FR-016`

## Functional requirement clauses

| Requirement ID | Canonical use-case evidence | Specification obligation |
|---|---|---|
| `BSDK-001` | `compliance-policy_scenarios-compliance_policy_POS_0001`, `compliance-policy_scenarios-compliance_policy_EDG_0100`, `compliance_policy_canonical-compliance_policy_POS_0001` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-002` | `compliance-policy_scenarios-compliance_policy_POS_0002`, `compliance_policy_canonical-compliance_policy_POS_0002`, `SA-SBS-00002` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-003` | `compliance-policy_scenarios-compliance_policy_POS_0003`, `compliance_policy_canonical-compliance_policy_POS_0003`, `SA-SBS-00003` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-101` | `compliance-policy_scenarios-compliance_policy_POS_0004`, `compliance_policy_canonical-compliance_policy_POS_0004`, `SA-SBS-00004` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-102` | `compliance-policy_scenarios-compliance_policy_POS_0005`, `compliance_policy_canonical-compliance_policy_POS_0005`, `SA-SBS-00005` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-103` | `compliance-policy_scenarios-compliance_policy_POS_0006`, `compliance_policy_canonical-compliance_policy_POS_0006`, `SA-SBS-00006` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-104` | `compliance-policy_scenarios-compliance_policy_POS_0007`, `compliance_policy_canonical-compliance_policy_POS_0007`, `SA-SBS-00007` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-105` | `compliance-policy_scenarios-compliance_policy_POS_0008`, `compliance_policy_canonical-compliance_policy_POS_0008`, `SA-SBS-00008` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-106` | `compliance-policy_scenarios-compliance_policy_POS_0009`, `compliance_policy_canonical-compliance_policy_POS_0009`, `SA-SBS-00009` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-107` | `compliance-policy_scenarios-compliance_policy_POS_0010`, `compliance_policy_canonical-compliance_policy_POS_0010`, `SA-SBS-00010` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-108` | `compliance-policy_scenarios-compliance_policy_POS_0011`, `compliance_policy_canonical-compliance_policy_POS_0011`, `SA-SBS-00011` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-109` | `compliance-policy_scenarios-compliance_policy_POS_0012`, `compliance_policy_canonical-compliance_policy_POS_0012`, `SA-SBS-00012` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-110` | `compliance-policy_scenarios-compliance_policy_POS_0013`, `compliance_policy_canonical-compliance_policy_POS_0013`, `SA-SBS-00013` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-111` | `compliance-policy_scenarios-compliance_policy_POS_0014`, `compliance_policy_canonical-compliance_policy_POS_0014`, `SA-SBS-00014` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-112` | `compliance-policy_scenarios-compliance_policy_POS_0015`, `compliance_policy_canonical-compliance_policy_POS_0015`, `SA-SBS-00015` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-113` | `compliance-policy_scenarios-compliance_policy_POS_0016`, `compliance_policy_canonical-compliance_policy_POS_0016`, `SA-SBS-00016` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-114` | `compliance-policy_scenarios-compliance_policy_POS_0017`, `compliance_policy_canonical-compliance_policy_POS_0017`, `SA-SBS-00017` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-115` | `compliance-policy_scenarios-compliance_policy_POS_0018`, `compliance_policy_canonical-compliance_policy_POS_0018`, `SA-SBS-00018` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-116` | `compliance-policy_scenarios-compliance_policy_POS_0019`, `compliance_policy_canonical-compliance_policy_POS_0019`, `SA-SBS-00019` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-117` | `compliance-policy_scenarios-compliance_policy_POS_0020`, `compliance_policy_canonical-compliance_policy_POS_0020`, `SA-SBS-00020` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-118` | `compliance-policy_scenarios-compliance_policy_POS_0021`, `compliance_policy_canonical-compliance_policy_POS_0021`, `SA-SBS-00021` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-119` | `compliance-policy_scenarios-compliance_policy_POS_0022`, `compliance_policy_canonical-compliance_policy_POS_0022`, `SA-SBS-00022` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-120` | `compliance-policy_scenarios-compliance_policy_POS_0023`, `compliance_policy_canonical-compliance_policy_POS_0023`, `SA-SBS-00023` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-121` | `compliance-policy_scenarios-compliance_policy_POS_0024`, `compliance_policy_canonical-compliance_policy_POS_0024`, `SA-SBS-00024` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-122` | `compliance-policy_scenarios-compliance_policy_POS_0025`, `compliance_policy_canonical-compliance_policy_POS_0025`, `SA-SBS-00025` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-123` | `compliance-policy_scenarios-compliance_policy_POS_0026`, `compliance_policy_canonical-compliance_policy_POS_0026`, `SA-SBS-00026` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-124` | `compliance-policy_scenarios-compliance_policy_POS_0027`, `compliance_policy_canonical-compliance_policy_POS_0027`, `SA-SBS-00027` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-125` | `compliance-policy_scenarios-compliance_policy_POS_0028`, `compliance_policy_canonical-compliance_policy_POS_0028`, `SA-SBS-00028` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-126` | `compliance-policy_scenarios-compliance_policy_POS_0029`, `compliance_policy_canonical-compliance_policy_POS_0029`, `SA-SBS-00029` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-127` | `compliance-policy_scenarios-compliance_policy_POS_0030`, `compliance_policy_canonical-compliance_policy_POS_0030`, `SA-SBS-00030` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-128` | `compliance-policy_scenarios-compliance_policy_POS_0031`, `compliance_policy_canonical-compliance_policy_POS_0031`, `SA-SBS-00031` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-129` | `compliance-policy_scenarios-compliance_policy_POS_0032`, `compliance_policy_canonical-compliance_policy_POS_0032`, `SA-SBS-00032` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-130` | `compliance-policy_scenarios-compliance_policy_POS_0033`, `compliance_policy_canonical-compliance_policy_POS_0033`, `SA-SBS-00033` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-131` | `compliance-policy_scenarios-compliance_policy_POS_0034`, `compliance_policy_canonical-compliance_policy_POS_0034`, `SA-SBS-00034` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-132` | `compliance-policy_scenarios-compliance_policy_POS_0035`, `compliance_policy_canonical-compliance_policy_POS_0035`, `SA-SBS-00035` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-133` | `compliance-policy_scenarios-compliance_policy_POS_0036`, `compliance_policy_canonical-compliance_policy_POS_0036`, `SA-SBS-00036` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-134` | `compliance-policy_scenarios-compliance_policy_POS_0037`, `compliance_policy_canonical-compliance_policy_POS_0037`, `SA-SBS-00037` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-135` | `compliance-policy_scenarios-compliance_policy_POS_0038`, `compliance_policy_canonical-compliance_policy_POS_0038`, `SA-SBS-00038` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-136` | `compliance-policy_scenarios-compliance_policy_POS_0039`, `compliance_policy_canonical-compliance_policy_POS_0039`, `SA-SBS-00039` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-137` | `compliance-policy_scenarios-compliance_policy_POS_0040`, `compliance_policy_canonical-compliance_policy_POS_0040`, `SA-SBS-00040` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-138` | `compliance-policy_scenarios-compliance_policy_POS_0041`, `compliance_policy_canonical-compliance_policy_POS_0041`, `SA-SBS-00041` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-139` | `compliance-policy_scenarios-compliance_policy_POS_0042`, `compliance_policy_canonical-compliance_policy_POS_0042`, `SA-SBS-00042` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-140` | `compliance-policy_scenarios-compliance_policy_POS_0043`, `compliance_policy_canonical-compliance_policy_POS_0043`, `SA-SBS-00043` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-141` | `compliance-policy_scenarios-compliance_policy_POS_0044`, `compliance_policy_canonical-compliance_policy_POS_0044`, `SA-SBS-00044` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-142` | `compliance-policy_scenarios-compliance_policy_POS_0045`, `compliance_policy_canonical-compliance_policy_POS_0045`, `SA-SBS-00045` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-143` | `compliance-policy_scenarios-compliance_policy_POS_0046`, `compliance_policy_canonical-compliance_policy_POS_0046`, `SA-SBS-00046` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-144` | `compliance-policy_scenarios-compliance_policy_POS_0047`, `compliance_policy_canonical-compliance_policy_POS_0047`, `SA-SBS-00047` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-145` | `compliance-policy_scenarios-compliance_policy_POS_0048`, `compliance_policy_canonical-compliance_policy_POS_0048`, `SA-SBS-00048` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-146` | `compliance-policy_scenarios-compliance_policy_POS_0049`, `compliance_policy_canonical-compliance_policy_POS_0049`, `SA-SBS-00049` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-147` | `compliance-policy_scenarios-compliance_policy_POS_0050`, `compliance_policy_canonical-compliance_policy_POS_0050`, `SA-SBS-00050` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-148` | `compliance-policy_scenarios-compliance_policy_POS_0051`, `compliance_policy_canonical-compliance_policy_POS_0051`, `SA-SBS-00051` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-149` | `compliance-policy_scenarios-compliance_policy_POS_0052`, `compliance_policy_canonical-compliance_policy_POS_0052`, `SA-SBS-00052` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-150` | `compliance-policy_scenarios-compliance_policy_POS_0053`, `compliance_policy_canonical-compliance_policy_POS_0053`, `SA-SBS-00053` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-151` | `compliance-policy_scenarios-compliance_policy_POS_0054`, `compliance_policy_canonical-compliance_policy_POS_0054`, `SA-SBS-00054` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-152` | `compliance-policy_scenarios-compliance_policy_POS_0055`, `compliance_policy_canonical-compliance_policy_POS_0055`, `SA-SBS-00055` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-153` | `compliance-policy_scenarios-compliance_policy_POS_0056`, `compliance_policy_canonical-compliance_policy_POS_0056`, `SA-SBS-00056` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-154` | `compliance-policy_scenarios-compliance_policy_POS_0057`, `compliance_policy_canonical-compliance_policy_POS_0057`, `SA-SBS-00057` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-155` | `compliance-policy_scenarios-compliance_policy_POS_0058`, `compliance_policy_canonical-compliance_policy_POS_0058`, `SA-SBS-00058` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-156` | `compliance-policy_scenarios-compliance_policy_POS_0059`, `compliance_policy_canonical-compliance_policy_POS_0059`, `SA-SBS-00059` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-157` | `compliance-policy_scenarios-compliance_policy_POS_0060`, `compliance_policy_canonical-compliance_policy_POS_0060`, `SA-SBS-00060` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-158` | `compliance-policy_scenarios-compliance_policy_POS_0061`, `compliance_policy_canonical-compliance_policy_POS_0061`, `SA-SBS-00061` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-159` | `compliance-policy_scenarios-compliance_policy_POS_0062`, `compliance_policy_canonical-compliance_policy_POS_0062`, `SA-SBS-00062` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-160` | `compliance-policy_scenarios-compliance_policy_POS_0063`, `compliance_policy_canonical-compliance_policy_POS_0063`, `SA-SBS-00063` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-161` | `compliance-policy_scenarios-compliance_policy_POS_0064`, `compliance_policy_canonical-compliance_policy_POS_0064`, `SA-SBS-00064` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-162` | `compliance-policy_scenarios-compliance_policy_POS_0065`, `compliance_policy_canonical-compliance_policy_POS_0065`, `SA-SBS-00065` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-163` | `compliance-policy_scenarios-compliance_policy_POS_0066`, `compliance_policy_canonical-compliance_policy_POS_0066`, `SA-SBS-00066` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-164` | `compliance-policy_scenarios-compliance_policy_POS_0067`, `compliance_policy_canonical-compliance_policy_POS_0067`, `SA-SBS-00067` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-165` | `compliance-policy_scenarios-compliance_policy_POS_0068`, `compliance_policy_canonical-compliance_policy_POS_0068`, `SA-SBS-00068` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-166` | `compliance-policy_scenarios-compliance_policy_POS_0069`, `compliance_policy_canonical-compliance_policy_POS_0069`, `SA-SBS-00069` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-167` | `compliance-policy_scenarios-compliance_policy_POS_0070`, `compliance_policy_canonical-compliance_policy_POS_0070`, `SA-SBS-00070` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-168` | `compliance-policy_scenarios-compliance_policy_POS_0071`, `compliance_policy_canonical-compliance_policy_POS_0071`, `SA-SBS-00071` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-169` | `compliance-policy_scenarios-compliance_policy_POS_0072`, `compliance_policy_canonical-compliance_policy_POS_0072`, `SA-SBS-00072` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-170` | `compliance-policy_scenarios-compliance_policy_POS_0073`, `compliance_policy_canonical-compliance_policy_POS_0073`, `SA-SBS-00073` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-171` | `compliance-policy_scenarios-compliance_policy_POS_0074`, `compliance_policy_canonical-compliance_policy_POS_0074`, `SA-SBS-00074` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-172` | `compliance-policy_scenarios-compliance_policy_POS_0075`, `compliance_policy_canonical-compliance_policy_POS_0075`, `SA-SBS-00075` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-173` | `compliance-policy_scenarios-compliance_policy_POS_0076`, `compliance_policy_canonical-compliance_policy_POS_0076`, `SA-SBS-00076` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-174` | `compliance-policy_scenarios-compliance_policy_POS_0077`, `compliance_policy_canonical-compliance_policy_POS_0077`, `SA-SBS-00077` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-175` | `compliance-policy_scenarios-compliance_policy_POS_0078`, `compliance_policy_canonical-compliance_policy_POS_0078`, `SA-SBS-00078` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-176` | `compliance-policy_scenarios-compliance_policy_POS_0079`, `compliance_policy_canonical-compliance_policy_POS_0079`, `SA-SBS-00079` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-177` | `compliance-policy_scenarios-compliance_policy_POS_0080`, `compliance_policy_canonical-compliance_policy_POS_0080`, `SA-SBS-00080` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-178` | `compliance-policy_scenarios-compliance_policy_POS_0081`, `compliance_policy_canonical-compliance_policy_POS_0081`, `SA-SBS-00081` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-179` | `compliance-policy_scenarios-compliance_policy_POS_0082`, `compliance_policy_canonical-compliance_policy_POS_0082`, `SA-SBS-00082` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-180` | `compliance-policy_scenarios-compliance_policy_POS_0083`, `compliance_policy_canonical-compliance_policy_POS_0083`, `SA-SBS-00083` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-181` | `compliance-policy_scenarios-compliance_policy_POS_0084`, `compliance_policy_canonical-compliance_policy_POS_0084`, `SA-SBS-00084` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-182` | `compliance-policy_scenarios-compliance_policy_POS_0085`, `compliance_policy_canonical-compliance_policy_POS_0085`, `SA-SBS-00085` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-183` | `compliance-policy_scenarios-compliance_policy_NEG_0086`, `compliance_policy_canonical-compliance_policy_NEG_0086`, `SA-SBS-00086` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-184` | `compliance-policy_scenarios-compliance_policy_NEG_0087`, `compliance_policy_canonical-compliance_policy_NEG_0087`, `SA-SBS-00087` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-185` | `compliance-policy_scenarios-compliance_policy_NEG_0088`, `compliance_policy_canonical-compliance_policy_NEG_0088`, `SA-SBS-00088` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-186` | `compliance-policy_scenarios-compliance_policy_NEG_0089`, `compliance_policy_canonical-compliance_policy_NEG_0089`, `SA-SBS-00089` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-187` | `compliance-policy_scenarios-compliance_policy_NEG_0090`, `compliance_policy_canonical-compliance_policy_NEG_0090`, `SA-SBS-00090` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-188` | `compliance-policy_scenarios-compliance_policy_NEG_0091`, `compliance_policy_canonical-compliance_policy_NEG_0091`, `SA-SBS-00091` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-189` | `compliance-policy_scenarios-compliance_policy_NEG_0092`, `compliance_policy_canonical-compliance_policy_NEG_0092`, `SA-SBS-00092` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-190` | `compliance-policy_scenarios-compliance_policy_NEG_0093`, `compliance_policy_canonical-compliance_policy_NEG_0093`, `SA-SBS-00093` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-191` | `compliance-policy_scenarios-compliance_policy_NEG_0094`, `compliance_policy_canonical-compliance_policy_NEG_0094`, `SA-SBS-00094` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-192` | `compliance-policy_scenarios-compliance_policy_NEG_0095`, `compliance_policy_canonical-compliance_policy_NEG_0095`, `SA-SBS-00095` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-193` | `compliance-policy_scenarios-compliance_policy_EDG_0096`, `compliance_policy_canonical-compliance_policy_EDG_0096`, `SA-SBS-00096` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-194` | `compliance-policy_scenarios-compliance_policy_EDG_0097`, `compliance_policy_canonical-compliance_policy_EDG_0097`, `SA-SBS-00097` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-195` | `compliance-policy_scenarios-compliance_policy_EDG_0098`, `compliance_policy_canonical-compliance_policy_EDG_0098`, `SA-SBS-00098` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `BSDK-196` | `compliance-policy_scenarios-compliance_policy_EDG_0099`, `compliance_policy_canonical-compliance_policy_EDG_0099`, `SA-SBS-00099` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-001` | `SA-SBS-00100`, `SA-SBS-SRC-00100` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-002` | `SA-SBS-00101`, `SA-SBS-SRC-00101` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-003` | `SA-SBS-00102`, `SA-SBS-SRC-00102` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-101` | `SA-SBS-00103`, `SA-SBS-SRC-00103` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-102` | `SA-SBS-00104`, `SA-SBS-SRC-00104` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-103` | `SA-SBS-00105`, `SA-SBS-SRC-00105` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-104` | `SA-SBS-00106`, `SA-SBS-SRC-00106` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-105` | `SA-SBS-00107`, `SA-SBS-SRC-00107` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-106` | `SA-SBS-00108`, `SA-SBS-SRC-00108` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-107` | `SA-SBS-00109`, `SA-SBS-SRC-00109` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-108` | `SA-SBS-00110`, `SA-SBS-SRC-00110` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-109` | `SA-SBS-00111`, `SA-SBS-SRC-00111` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-110` | `SA-SBS-00112`, `SA-SBS-SRC-00112` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-111` | `SA-SBS-00113`, `SA-SBS-SRC-00113` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-112` | `SA-SBS-00114`, `SA-SBS-SRC-00114` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-113` | `SA-SBS-00115`, `SA-SBS-SRC-00115` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-114` | `SA-SBS-00116`, `SA-SBS-SRC-00116` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-115` | `SA-SBS-00117`, `SA-SBS-SRC-00117` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-116` | `SA-SBS-00118`, `SA-SBS-SRC-00118` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-117` | `SA-SBS-00119`, `SA-SBS-SRC-00119` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-118` | `SA-SBS-00120`, `SA-SBS-SRC-00120` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-119` | `SA-SBS-00121`, `SA-SBS-SRC-00121` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-120` | `SA-SBS-00122`, `SA-SBS-SRC-00122` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-121` | `SA-SBS-00123`, `SA-SBS-SRC-00123` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-122` | `SA-SBS-00124`, `SA-SBS-SRC-00124` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-123` | `SA-SBS-00125`, `SA-SBS-SRC-00125` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-124` | `SA-SBS-00126`, `SA-SBS-SRC-00126` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-125` | `SA-SBS-00127`, `SA-SBS-SRC-00127` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-126` | `SA-SBS-00128`, `SA-SBS-SRC-00128` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-127` | `SA-SBS-00129`, `SA-SBS-SRC-00129` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-128` | `SA-SBS-00130`, `SA-SBS-SRC-00130` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-129` | `SA-SBS-00131`, `SA-SBS-SRC-00131` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-130` | `SA-SBS-00132`, `SA-SBS-SRC-00132` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-131` | `SA-SBS-00133`, `SA-SBS-SRC-00133` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-132` | `SA-SBS-00134`, `SA-SBS-SRC-00134` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-133` | `SA-SBS-00135`, `SA-SBS-SRC-00135` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-134` | `SA-SBS-00136`, `SA-SBS-SRC-00136` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-135` | `SA-SBS-00137`, `SA-SBS-SRC-00137` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-136` | `SA-SBS-00138`, `SA-SBS-SRC-00138` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-137` | `SA-SBS-00139`, `SA-SBS-SRC-00139` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-138` | `SA-SBS-00140`, `SA-SBS-SRC-00140` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-139` | `SA-SBS-00141`, `SA-SBS-SRC-00141` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-140` | `SA-SBS-00142`, `SA-SBS-SRC-00142` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-141` | `SA-SBS-00143`, `SA-SBS-SRC-00143` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-142` | `SA-SBS-00144`, `SA-SBS-SRC-00144` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-143` | `SA-SBS-00145`, `SA-SBS-SRC-00145` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-144` | `SA-SBS-00146`, `SA-SBS-SRC-00146` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-145` | `SA-SBS-00147`, `SA-SBS-SRC-00147` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-146` | `SA-SBS-00148`, `SA-SBS-SRC-00148` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-147` | `SA-SBS-00149`, `SA-SBS-SRC-00149` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-148` | `SA-SBS-00150`, `SA-SBS-SRC-00150` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-149` | `SA-SBS-00151`, `SA-SBS-SRC-00151` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-150` | `SA-SBS-00152`, `SA-SBS-SRC-00152` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-151` | `SA-SBS-00153`, `SA-SBS-SRC-00153` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-152` | `SA-SBS-00154`, `SA-SBS-SRC-00154` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-153` | `SA-SBS-00155`, `SA-SBS-SRC-00155` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-154` | `SA-SBS-00156`, `SA-SBS-SRC-00156` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-155` | `SA-SBS-00157`, `SA-SBS-SRC-00157` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-156` | `SA-SBS-00158`, `SA-SBS-SRC-00158` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-157` | `SA-SBS-00159`, `SA-SBS-SRC-00159` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-158` | `SA-SBS-00160`, `SA-SBS-SRC-00160` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-159` | `SA-SBS-00161`, `SA-SBS-SRC-00161` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-160` | `SA-SBS-00162`, `SA-SBS-SRC-00162` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-161` | `SA-SBS-00163`, `SA-SBS-SRC-00163` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-162` | `SA-SBS-00164`, `SA-SBS-SRC-00164` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-163` | `SA-SBS-00165`, `SA-SBS-SRC-00165` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-164` | `SA-SBS-00166`, `SA-SBS-SRC-00166` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-165` | `SA-SBS-00167`, `SA-SBS-SRC-00167` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-166` | `SA-SBS-00168`, `SA-SBS-SRC-00168` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-167` | `SA-SBS-00169`, `SA-SBS-SRC-00169` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-168` | `SA-SBS-00170`, `SA-SBS-SRC-00170` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-169` | `SA-SBS-00171`, `SA-SBS-SRC-00171` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-170` | `SA-SBS-00172`, `SA-SBS-SRC-00172` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-171` | `SA-SBS-00173`, `SA-SBS-SRC-00173` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-172` | `SA-SBS-00174`, `SA-SBS-SRC-00174` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-173` | `SA-SBS-00175`, `SA-SBS-SRC-00175` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-174` | `SA-SBS-00176`, `SA-SBS-SRC-00176` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-175` | `SA-SBS-00177`, `SA-SBS-SRC-00177` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-176` | `SA-SBS-00178`, `SA-SBS-SRC-00178` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-177` | `SA-SBS-00179`, `SA-SBS-SRC-00179` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-178` | `SA-SBS-00180`, `SA-SBS-SRC-00180` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-179` | `SA-SBS-00181`, `SA-SBS-SRC-00181` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-180` | `SA-SBS-00182`, `SA-SBS-SRC-00182` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-181` | `SA-SBS-00183`, `SA-SBS-SRC-00183` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-182` | `SA-SBS-00184`, `SA-SBS-SRC-00184` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-183` | `SA-SBS-00185`, `SA-SBS-SRC-00185` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-184` | `SA-SBS-00186`, `SA-SBS-SRC-00186` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-185` | `SA-SBS-00187`, `SA-SBS-SRC-00187` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-186` | `SA-SBS-00188`, `SA-SBS-SRC-00188` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-187` | `SA-SBS-00189`, `SA-SBS-SRC-00189` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-188` | `SA-SBS-00190`, `SA-SBS-SRC-00190` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-189` | `SA-SBS-00191`, `SA-SBS-SRC-00191` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-190` | `SA-SBS-00192`, `SA-SBS-SRC-00192` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-191` | `SA-SBS-00193`, `SA-SBS-SRC-00193` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-192` | `SA-SBS-00194`, `SA-SBS-SRC-00194` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-193` | `SA-SBS-00195`, `SA-SBS-SRC-00195` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-194` | `SA-SBS-00196`, `SA-SBS-SRC-00196` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-195` | `SA-SBS-00197`, `SA-SBS-SRC-00197` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `DS-196` | `SA-SBS-00198`, `SA-SBS-SRC-00198` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-001` | `SA-SBS-00199`, `SA-SBS-SRC-00199` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-002` | `SA-SBS-00200`, `SA-SBS-SRC-00200` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-003` | `SA-SBS-00201`, `SA-SBS-SRC-00201` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-004` | `SA-SBS-00202`, `SA-SBS-SRC-00202` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-005` | `SA-SBS-00203`, `SA-SBS-SRC-00203` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-006` | `SA-SBS-00204`, `SA-SBS-SRC-00204` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-007` | `SA-SBS-00205`, `SA-SBS-SRC-00205` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-008` | `SA-SBS-00206`, `SA-SBS-SRC-00206` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-009` | `SA-SBS-00207`, `SA-SBS-SRC-00207` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-010` | `SA-SBS-00208`, `SA-SBS-SRC-00208` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-011` | `SA-SBS-00209`, `SA-SBS-SRC-00209` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-012` | `SA-SBS-00210`, `SA-SBS-SRC-00210` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-013` | `SA-SBS-00211`, `SA-SBS-SRC-00211` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-014` | `SA-SBS-00212`, `SA-SBS-SRC-00212` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-015` | `SA-SBS-00213`, `SA-SBS-SRC-00213` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-016` | `SA-SBS-00214`, `SA-SBS-SRC-00214` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-001` | `compliance-policy_scenarios-compliance_policy_POS_0001`, `compliance-policy_scenarios-compliance_policy_POS_0009`, `compliance-policy_scenarios-compliance_policy_POS_0017` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-002` | `compliance-policy_scenarios-compliance_policy_POS_0002`, `compliance-policy_scenarios-compliance_policy_POS_0010`, `compliance-policy_scenarios-compliance_policy_POS_0018` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-003` | `compliance-policy_scenarios-compliance_policy_POS_0003`, `compliance-policy_scenarios-compliance_policy_POS_0011`, `compliance-policy_scenarios-compliance_policy_POS_0019` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-004` | `compliance-policy_scenarios-compliance_policy_POS_0004`, `compliance-policy_scenarios-compliance_policy_POS_0012`, `compliance-policy_scenarios-compliance_policy_POS_0020` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-005` | `compliance-policy_scenarios-compliance_policy_POS_0005`, `compliance-policy_scenarios-compliance_policy_POS_0013`, `compliance-policy_scenarios-compliance_policy_POS_0021` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-006` | `compliance-policy_scenarios-compliance_policy_POS_0006`, `compliance-policy_scenarios-compliance_policy_POS_0014`, `compliance-policy_scenarios-compliance_policy_POS_0022` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-007` | `compliance-policy_scenarios-compliance_policy_POS_0007`, `compliance-policy_scenarios-compliance_policy_POS_0015`, `compliance-policy_scenarios-compliance_policy_POS_0023` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `FR-BSDK-008` | `compliance-policy_scenarios-compliance_policy_POS_0008`, `compliance-policy_scenarios-compliance_policy_POS_0016`, `compliance-policy_scenarios-compliance_policy_POS_0024` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-001` | `SA-SBS-00249`, `SA-SBS-SRC-00249` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-002` | `SA-SBS-00250`, `SA-SBS-SRC-00250` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-003` | `SA-SBS-00251`, `SA-SBS-SRC-00251` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-004` | `SA-SBS-00252`, `SA-SBS-SRC-00252` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-005` | `SA-SBS-00253`, `SA-SBS-SRC-00253` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-006` | `SA-SBS-00254`, `SA-SBS-SRC-00254` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-007` | `SA-SBS-00255`, `SA-SBS-SRC-00255` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-008` | `SA-SBS-00256`, `SA-SBS-SRC-00256` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-009` | `SA-SBS-00257`, `SA-SBS-SRC-00257` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-010` | `SA-SBS-00258`, `SA-SBS-SRC-00258` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-011` | `SA-SBS-00259`, `SA-SBS-SRC-00259` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-012` | `SA-SBS-00260`, `SA-SBS-SRC-00260` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-013` | `SA-SBS-00261`, `SA-SBS-SRC-00261` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-014` | `SA-SBS-00262`, `SA-SBS-SRC-00262` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-015` | `SA-SBS-00263`, `SA-SBS-SRC-00263` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |
| `SPID-FR-016` | `SA-SBS-00264`, `SA-SBS-SRC-00264` | Maintain repo-owned functional behaviour evidence through requirements, canonical matrices, implementation ownership, tests, and seeded data. |

## Acceptance rule

Every functional requirement above must remain linked to at least one canonical use-case row, the seeded traceability ledger, implementation ownership evidence, and a repo-local test path. Changes that add, rename, or remove functional behaviour must update this file, the canonical matrix, and the traceability tests in the same change.
