"""V-Model L3 system/e2e coverage for canonical harness contracts."""

from __future__ import annotations

import json
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_l3_system_contracts_have_observable_triggers_and_outcomes() -> None:
    checked = 0
    missing: list[str] = []
    for path in sorted((HARNESS / "json_matrices").glob("*_scenarios.json")):
        for index, scenario in enumerate(_load(path).get("scenarios", []), start=1):
            checked += 1
            for field in ("trigger", "expected_outputs"):
                if field not in scenario or scenario[field] is None:
                    missing.append(f"{path.name}[{index}] missing {field}")

    assert checked
    assert not missing, "Incomplete system contracts: " + ", ".join(missing[:10])
