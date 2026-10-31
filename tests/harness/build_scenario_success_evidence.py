"""Build scenario-success evidence citing ONLY the executed app-harness nodes.

Option C (eps/vr-therapy pattern), adapted for an SDK/library with no bootable
HTTP app. The system1-reflex matrix is the only genuinely app-dispatchable
scenario set in symphonix-bridge-sdk: ``test_matrix_scenario_execution.py``
dispatches each genuinely-single-shot-dispatchable system1-reflex row into the
REAL ``bridge_sdk.system1_reflex`` engine its ``body.engine`` names, on inputs
fully determined by the row body, and asserts the observed deterministic result.
This builder cites exactly those executed node ids and records the honest count
of rows left unexecuted (the system1 engines whose required inputs the generic
row body does not carry -- see the harness docstring).

The FILE-EXISTS compliance-policy and TRACEABILITY_LEDGER seeded-alignment
scenario families are descriptor-only (no mounted route, no determinate callable
surface the row body exercises) and are therefore not part of this runtime
matrix.

This evidence is NOT an attempt to satisfy caid's ``direct.scenario_app_harness``
gate -- that gate's managed set is the full reduced + NFR matrices and it remains
RED by design (symphonix-bridge-sdk has not authored domain journeys that would
make every managed row app-dispatchable). The evidence is an honest record of
what IS executed against real repo code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MATRIX = (
    ROOT / "tests" / "harness" / "json_matrices" / "system1-reflex_scenarios.json"
)
OUTPUT = ROOT / "tests" / "harness" / "scenario_success_evidence.json"
PYTEST_FILE = "tests/harness/test_matrix_scenario_execution.py"
PYTEST_FUNCTION = "test_system1_reflex_row_against_the_real_engine"

# Engines dispatched by the harness: each a real, pure static callable in
# bridge_sdk.system1_reflex fully fed by the generic row body. Kept in lockstep
# with DISPATCH in test_matrix_scenario_execution.py.
DISPATCHABLE_ENGINES = frozenset(
    {"Tier0SafetyFloor", "ConsultationStateReflex", "ReferralSatisficingReflex"}
)
# Real source files the dispatched callables exercise.
APP_PATHS_EXERCISED = (
    "src/bridge_sdk/__init__.py",
    "src/bridge_sdk/system1_reflex.py",
)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("scenarios"), list):
        return [r for r in payload["scenarios"] if isinstance(r, dict)]
    return []


def _engine(row: dict[str, Any]) -> str:
    return str((row.get("input_payload") or {}).get("body", {}).get("engine", ""))


def build() -> dict[str, Any]:
    rel_path = RUNTIME_MATRIX.relative_to(ROOT).as_posix()
    payload = json.loads(RUNTIME_MATRIX.read_text(encoding="utf-8"))

    evidence: list[dict[str, Any]] = []
    unexecuted: list[str] = []
    for index, row in enumerate(_rows(payload)):
        use_case_id = str(row.get("use_case_id", ""))
        if not use_case_id:
            continue
        if _engine(row) not in DISPATCHABLE_ENGINES:
            unexecuted.append(use_case_id)
            continue
        evidence.append(
            {
                "use_case_id": use_case_id,
                "matrix_file": rel_path,
                "matrix_row_index": index,
                "matrix_row_key": f"{rel_path}#{index}:{use_case_id}",
                "pytest_param_id": use_case_id,
                "pytest_node_id": f"{PYTEST_FILE}::{PYTEST_FUNCTION}[{use_case_id}]",
                "expected_status": "passed",
                "app_paths_exercised": list(APP_PATHS_EXERCISED),
            }
        )

    return {
        "schema_version": "SYMPHONIX_SCENARIO_SUCCESS_EVIDENCE_V1",
        "generated_by": "tests/harness/build_scenario_success_evidence.py",
        "pytest_file": PYTEST_FILE,
        "pytest_function": PYTEST_FUNCTION,
        "runtime_matrix": rel_path,
        "executed_row_count": len(evidence),
        "unexecuted_row_count": len(unexecuted),
        "unexecuted_rows": sorted(unexecuted),
        "evidence": evidence,
    }


def main() -> None:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"[OK] wrote {payload['executed_row_count']} executed-node evidence entries; "
        f"unexecuted_row_count={payload['unexecuted_row_count']} to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
