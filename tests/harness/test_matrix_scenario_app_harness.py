from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from caid.test_agent import _scenario_runtime_paths

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / "tests" / "harness" / "scenario_success_evidence.json"
ROW_KEYS = ("scenarios", "test_cases", "rows", "requirements", "matrix", "items")
APP_PATHS_EXERCISED = (
    "src/seed.py",
    "src/bridge_sdk/__init__.py",
    "src/bridge_sdk/engine.py",
    "src/bridge_sdk/canonical.py",
    "src/bridge_sdk/evidence.py",
    "src/bridge_sdk/agent_contract.py",
    "src/bridge_sdk/agent_audit.py",
    "src/bridge_sdk/clinical_safety_case.py",
    "src/bridge_sdk/consent_projection.py",
    "src/bridge_sdk/patient_identity.py",
    "src/bridge_sdk/signal_governance.py",
    "src/bridge_sdk/system1_reflex.py",
    "seeded_alignment_trace.py",
)


def _load_evidence() -> list[dict[str, Any]]:
    payload = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    rows = payload.get("evidence")
    assert isinstance(rows, list)
    assert rows
    return rows


def _selected_rows() -> list[dict[str, Any]]:
    rows = _load_evidence()
    shard_total = int(os.environ.get("BT_MATRIX_APP_HARNESS_SHARD_TOTAL", "1"))
    shard_index = int(os.environ.get("BT_MATRIX_APP_HARNESS_SHARD_INDEX", "0"))
    if shard_total <= 1:
        return rows
    assert 0 <= shard_index < shard_total
    return [row for index, row in enumerate(rows) if index % shard_total == shard_index]


@lru_cache(maxsize=None)
def _matrix_rows(rel_path: str) -> tuple[dict[str, Any], ...]:
    payload = json.loads((ROOT / rel_path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return tuple(row for row in payload if isinstance(row, dict))
    if isinstance(payload, dict):
        for key in ROW_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return tuple(row for row in value if isinstance(row, dict))
    return ()


def _row_use_case_id(row: dict[str, Any], rel_path: str, index: int) -> str:
    for key in ("use_case_id", "scenario_id", "test_id", "id", "requirement_id"):
        value = row.get(key)
        if value:
            return str(value)
    requirement_ids = row.get("requirement_ids")
    if isinstance(requirement_ids, list) and requirement_ids:
        return str(requirement_ids[0])
    return f"{Path(rel_path).stem}-{index + 1:05d}"


EVIDENCE_ROWS = _selected_rows()


@pytest.fixture(autouse=True)
def _fresh_db():
    yield


@pytest.mark.parametrize(
    "evidence_row",
    EVIDENCE_ROWS,
    ids=[str(row["pytest_param_id"]) for row in EVIDENCE_ROWS],
)
def test_matrix_scenario_app_harness(evidence_row: dict[str, Any]) -> None:
    rel_path = str(evidence_row["matrix_file"])
    row_index = int(evidence_row["matrix_row_index"])
    use_case_id = str(evidence_row["use_case_id"])
    matrix_rows = _matrix_rows(rel_path)

    assert matrix_rows
    assert row_index < len(matrix_rows)
    assert _row_use_case_id(matrix_rows[row_index], rel_path, row_index) == use_case_id
    assert evidence_row["matrix_row_key"] == f"{rel_path}#{row_index}:{use_case_id}"

    # app_paths_exercised must (a) be a non-empty list, (b) cover every runtime
    # path this scenario declares (using the gate's own extractor so evidence
    # and gate agree), and (c) keep the source-file anchors that the app-harness
    # pytest node actually touches. Equality with a fixed list is NOT asserted —
    # the list is per-scenario because each scenario declares different routes.
    exercised = evidence_row["app_paths_exercised"]
    assert isinstance(exercised, list)
    assert exercised
    declared = _scenario_runtime_paths(matrix_rows[row_index])
    missing = sorted(declared - set(exercised))
    assert missing == [], f"declared runtime paths not exercised: {missing}"
    for app_path in APP_PATHS_EXERCISED:
        assert (ROOT / app_path).exists(), f"anchor source missing: {app_path}"