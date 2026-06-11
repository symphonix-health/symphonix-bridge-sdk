"""V-Model L2 integration coverage for canonical harness traceability."""

from __future__ import annotations

import json
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _requirement_ids(path: Path) -> set[str]:
    items = _load(path).get("requirements", [])
    if isinstance(items, dict):
        items = items.values()
    return {
        str(item.get("requirement_id") or item.get("id"))
        for item in items
        if isinstance(item, dict) and (item.get("requirement_id") or item.get("id"))
    }


def test_l2_canonical_scenarios_integrate_with_requirement_catalogue() -> None:
    known = _requirement_ids(HARNESS / "requirements_superset.json")
    known |= _requirement_ids(HARNESS / "requirements_matrix.json")
    assert known

    linked: list[str] = []
    missing: list[str] = []
    for path in sorted((HARNESS / "json_matrices").glob("*_scenarios.json")):
        for index, scenario in enumerate(_load(path).get("scenarios", []), start=1):
            requirement_ids = scenario.get("requirement_ids") or []
            if isinstance(requirement_ids, str):
                requirement_ids = [requirement_ids]
            requirement_ids = [
                part.strip()
                for rid in requirement_ids
                for part in str(rid).replace(";", ",").split(",")
                if part.strip()
            ]
            linked.extend(str(rid) for rid in requirement_ids)
            missing.extend(
                f"{path.name}[{index}] -> {rid}"
                for rid in requirement_ids
                if str(rid) not in known
            )

    assert linked
    assert not missing, "Unknown requirement links: " + ", ".join(missing[:10])
