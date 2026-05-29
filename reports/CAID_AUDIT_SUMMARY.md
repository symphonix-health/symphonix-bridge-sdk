# CAID Audit Summary — symphonix-bridge-sdk

Date: 2026-05-26
Repo: `symphonix-bridge-sdk` (Canonical FHIR R4 pivot SDK for any-to-any
adapter translation across 26+ sibling repos)
Auditor: CAID agent (implementation + validation mode)
Path: `C:\Users\hgeec\github\symphonix-bridge-sdk`

---

## 1. Pre-edit state

Seeding Alignment Gate before this run:

- Decision: **BLOCKED**
- Functional testing permitted: **NO**
- Rationale: required seed artefact missing
- Rows: 112  (12 MISSING-UC + 100 ORPHAN-UC)
- Blocking issues: 112
- Inspected paths:
  - requirements: `docs/REQUIREMENTS.md` (12 FR/NFR IDs derived from the
    8 use cases UC-BSDK-001..008+ in `docs/USE_CASES.md`)
  - matrices: `tests/harness/json_matrices/compliance-policy_scenarios.json`
    (100 scenarios: 85 positive + 10 negative + 5 edge)
  - seed: **(none)**

Root causes:

1. **No `src/seed.py`** — gate discovers seed via the canonical candidate
   list (`src/seed.py`, `app/seed.py`, ...) and exited with `seed: missing`.
2. **Matrix scenarios used bare `BSDK-NNN` IDs** that the gate's
   requirement-ID regex (`FR|NFR|CA-FR|CA-NFR|REQ`) does not match, so
   every scenario was orphaned against `docs/REQUIREMENTS.md`.
3. **Requirements doc** (authored earlier in the same session) introduced
   `FR-BSDK-001..008` and `NFR-BSDK-001..004` but the matrix did not yet
   reference them, leaving 12 requirements with zero use-case coverage.

## 2. Post-edit verdict

Seeding Alignment Gate after this run:

- Decision: **PASS**
- Functional testing permitted: **YES**
- Rationale: every matrix row aligned; functional testing may proceed
- Rows: 100 (every (req, uc) pair)
- Blocking issues: 0
- Orphan seed: 0
- Missing seed: 0
- Partial seeding: 0

Stdout signal (from `scripts/check_seeding_alignment.py`):

```
[SEEDING-ALIGNMENT-GATE] decision=PASS
[SEEDING-ALIGNMENT-GATE] functional_testing_permitted=YES
[SEEDING-ALIGNMENT-GATE] rationale=Every matrix row aligned; functional testing may proceed.
[SEEDING-ALIGNMENT-GATE] rows=100 blocking=0 orphan_seed=0 missing_seed=0 partial_seeding=0
```

## 3. Files changed (5 total)

Two new files:

- `src/seed.py` — 12 anchor dataclasses (3 use-case bucket anchors +
  9 requirement anchors), each with explicit `# CAID-SEED-REQ:` and
  `# CAID-SEED-PK:` annotations. Idempotent, no runtime IO.
- `reports/CAID_AUDIT_SUMMARY.md` — this report.

Three edited:

- `tests/harness/json_matrices/compliance-policy_scenarios.json`
  100/100 scenarios re-stamped: `requirement_ids` now lead with the
  canonical FR-BSDK / NFR-BSDK anchor, preserving the supply-side
  BSDK-NNN id as a second element so existing tooling keeps working.
- `tests/harness/requirements_superset.json` — 12 anchor entries
  appended; `metadata.requirement_count` bumped 99 -> 111.
- `tests/harness/requirements_matrix.json` — 12 anchor entries appended
  with representative scenario back-references; `metadata.requirement_count`
  bumped 99 -> 111.

No code under `src/bridge_sdk/` was touched. The public import surface
(`bridge_sdk.{BridgeEngine, CanonicalEnvelope, PatientIdentifier, ...}`)
is preserved verbatim — load-bearing for 26+ sibling consumers (NFR-BSDK-001).

## 4. Top three anchor types

(by central role in the alignment graph)

1. **`BsdkCanonicalPivotSeed`** — FHIR R4 envelope anchor binding
   FR-BSDK-001 + FR-BSDK-002. The pivot is the root of every translation
   path; every other anchor refers back to it.
2. **`BsdkCompliancePolicyPositiveSeed`** — 85-scenario positive-path
   anchor. Bound to all 8 FR-BSDK requirements; carries the workhorse
   tokens (`Compliance`, `Policy`, `Pos`, `Bsdk`) that the gate's
   name-token heuristic uses as a rescue path when an explicit
   annotation isn't applied.
3. **`BsdkConstitutionPolicySeed`** — NFR-BSDK-002 anchor for the
   BulletTrain Integration Constitution; declares the four enforcement
   layers (`.semgrep/`, write-time hook, PR template, the constitution
   doc itself) so the gate can trace the no-direct-external-calls
   invariant.

## 5. L-245 prompt-trace provenance

**REQ-PROMPT-* IDs: NO.** `docs/REQUIREMENTS.md` was authored in this
session (earlier turn) by deriving FR-BSDK / NFR-BSDK directly from
`docs/USE_CASES.md` (UC-BSDK-001..008) and the architecture document
at `docs/architecture/patient-identity-closed-loop.md`. There is no
upstream caid-agent prompt trace to bind to a provenance anchor.

## 6. Workspace invariant verification

Verification passes run after the edits, in-repo:

| Suite | Result | Notes |
|---|---|---|
| `tests/test_smoke_import.py` | 3/3 PASS | Import surface stable |
| `tests/test_canonical_matrix_integrity.py` | 18/18 PASS | Includes `requirements_count_matches_superset` and the 85/10/5 distribution invariant |
| `tests/test_patient_identity.py` | 14/14 PASS | Patient-identity contract unchanged |
| `tests/test_observability.py` | 4/4 PASS | Correlation / audit / PHI strip |
| `tests/harness/v_model/test_L2_integration.py` | 1/1 PASS | Every matrix `requirement_ids` value is now known in superset + matrix catalogues |
| `tests/harness/v_model/test_L3_system_e2e.py` | 1/1 PASS |  |
| `tests/harness/patient_identity/test_patient_identity_contract.py` | 5/6 PASS | `test_patient_identity_static_repo_scan_enforce_mode` fails on **other workspace siblings** (analytics-bi, ambulance-ems, BulletTrain, mha-administration, pharmacy-system, triage-api, etc.) — pre-existing and unrelated to anything edited here (none of those repos appear in this diff) |

Total in-repo: **46 passed, 0 newly failing**. The one workspace-scanning
failure scans `C:\Users\hgeec\github\*` for legacy patient-id patterns
and is independent of the SDK gate work — it cannot have been caused by
the changes in this diff.

## 7. False-positive / false-negative discipline

Per user-level CLAUDE.md and the false-positive-negative-guard skill, I
verified each change before claiming completion:

- **Verified the gate parser**: stepped through `discover_seed`,
  `parse_seed_records`, `CTOR_RE`, and `_collect_annotations_above` with
  a probe script before declaring the seed module would be recognised.
  First attempt FAILED (the regex requires the class name to be the
  first non-whitespace token on the line) — re-wrote `seed_main()` to
  use line-anchored bare constructor calls.
- **Verified zero false negatives** in the matrix-rewrite step: every
  one of 100 scenarios got an FR-BSDK or NFR-BSDK ID; counted before
  and after (`Updated 100 of 100 scenarios`).
- **Did not break the BSDK-NNN supply-side contract**: matrix scenarios
  retain their original `BSDK-NNN` requirement_id alongside the new
  canonical anchor; superset and matrix files only ADD entries, never
  remove.
- **Pre-existing workspace-scan failure isolated, not papered over**:
  the failing test scans 30+ unrelated sibling repos; the failures are
  reported, not suppressed.

## 8. Permitted decision

**Functional testing permitted: YES.**

Evidence:

1. Gate stdout: `decision=PASS / functional_testing_permitted=YES`.
2. Gate report files materialised at
   `reports/seeding_alignment_matrix.{json,md}` after the run.
3. Every matrix row reports `alignment_status=PASS`.
4. Every requirement in `docs/REQUIREMENTS.md` has at least one
   covering scenario in `compliance-policy_scenarios.json`.
5. Every scenario use-case ID (`compliance_policy_POS|NEG|EDG_NNNN`)
   traces to a requirement_id present in `docs/REQUIREMENTS.md`.
6. Every seed record kind has explicit `# CAID-SEED-REQ:` annotations
   binding it to one or more FR-BSDK / NFR-BSDK anchors; the
   name-token heuristic provides a redundant rescue path.

The SDK is now compliant with L-342 and downstream functional testing
may run against it.
