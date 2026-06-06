from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX_DIR = ROOT / "tests" / "harness" / "reduced_json_matrices"
REQ_MATRIX = ROOT / "tests" / "harness" / "requirements_matrix.json"

CANONICAL_COLUMNS = [
    "use_case_id",
    "component",
    "scenario",
    "test_type",
    "priority",
    "expected_outcomes",
    "preconditions",
    "test_data",
    "validation_rules",
    "dependencies",
    "tags",
    "estimated_duration",
    "automation_status",
    "notes",
]
VALID_TEST_TYPES = {"positive", "negative", "edge"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_AUTOMATION = {"automated", "manual", "planned", "in_progress"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("test_cases", "scenarios", "tests", "cases"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _matrix_files() -> list[Path]:
    files = sorted(MATRIX_DIR.glob("*.14col.json"))
    assert files, "no BulletTrain 14-column matrices found"
    return files


def _source_rows(path: Path) -> list[dict[str, Any]]:
    return _rows(_read_json(path))


def test_bullettrain_v1_matrices_use_14_column_schema() -> None:
    seen_ids: set[str] = set()
    for path in _matrix_files():
        payload = _read_json(path)
        assert payload.get("schema_version") == "BT_CANONICAL_MATRIX_V1_14COL", (
            path.name
        )
        rows = _rows(payload)
        assert rows, path.name
        for row in rows:
            assert list(row.keys()) == CANONICAL_COLUMNS, (
                f"{path.name}:{row.get('use_case_id')}"
            )
            assert row["test_type"] in VALID_TEST_TYPES
            assert row["priority"] in VALID_PRIORITIES
            assert row["automation_status"] in VALID_AUTOMATION
            assert row["use_case_id"] not in seen_ids
            seen_ids.add(row["use_case_id"])
            assert row["expected_outcomes"]
            assert row["validation_rules"]
            assert row["dependencies"]
            assert row["tags"]
            assert isinstance(row["estimated_duration"], int)
            assert row["test_data"].get("source_matrix")
            assert row["test_data"].get("source_use_case_id")
            assert row["test_data"].get("requirement_ids")


def test_bullettrain_v1_projection_preserves_source_v2_rows() -> None:
    for path in _matrix_files():
        payload = _read_json(path)
        source_rel = payload["metadata"]["source_matrix"]
        source_path = ROOT / source_rel
        assert source_path.exists(), source_rel
        source_by_id = {
            str(row.get("use_case_id")): row for row in _source_rows(source_path)
        }
        projected = _rows(payload)
        assert len(projected) == len(source_by_id), path.name
        for row in projected:
            source_id = row["test_data"]["source_use_case_id"]
            assert source_id in source_by_id, f"{path.name}:{source_id}"
            source_reqs = {
                str(r) for r in source_by_id[source_id].get("requirement_ids", [])
            }
            projected_reqs = {
                str(r) for r in row["test_data"].get("requirement_ids", [])
            }
            assert source_reqs == projected_reqs


def test_bullettrain_v1_matrices_cover_requirements_matrix() -> None:
    requirements = _read_json(REQ_MATRIX).get("requirements", [])
    required_ids = {
        str(item.get("requirement_id"))
        for item in requirements
        if item.get("requirement_id")
        and item.get("coverage_status", "covered") == "covered"
    }
    matrix_ids: set[str] = set()
    for path in _matrix_files():
        for row in _rows(_read_json(path)):
            matrix_ids.update(
                str(r) for r in row["test_data"].get("requirement_ids", [])
            )
            matrix_ids.update(
                str(tag) for tag in row.get("tags", []) if isinstance(tag, str)
            )
    assert required_ids, "requirements_matrix.json has no covered requirements"
    assert required_ids <= matrix_ids
