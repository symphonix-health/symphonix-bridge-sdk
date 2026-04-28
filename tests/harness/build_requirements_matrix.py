"""GHARRA — BT_REQUIREMENTS_TRACEABILITY_V1 requirements_matrix.json.

Walks every BT canonical matrix in tests/harness/canonical_matrices/ and
emits per-requirement coverage rows linking each REQ-GAR-* to the scenarios
that exercise it. The original 30 REQ-GAR-001..030 are anchored by the
existing executable scenarios; the global-standards extension reqs are
covered by the canonical-overlay slice + the compliance-policy matrix.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SUPERSET = ROOT / "tests" / "harness" / "requirements_superset.json"
CANON_DIR = ROOT / "tests" / "harness" / "canonical_matrices"
OUT = ROOT / "tests" / "harness" / "requirements_matrix.json"


def main() -> None:
    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    coverage: dict[str, list[dict]] = {r["requirement_id"]: [] for r in superset["requirements"]}

    for path in sorted(CANON_DIR.glob("*_canonical.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        subsystem = m["metadata"]["subsystem"]
        for s in m["scenarios"]:
            for rid in s.get("requirement_ids", []):
                if rid in coverage:
                    coverage[rid].append({
                        "matrix": path.name,
                        "subsystem": subsystem,
                        "use_case_id": s["use_case_id"],
                        "scenario_category": s["scenario_category"],
                    })

    rows = []
    for r in superset["requirements"]:
        rid = r["requirement_id"]
        scenarios = coverage[rid]
        rows.append({
            "requirement_id": rid,
            "family": r["family"],
            "title": r["title"],
            "statement": r["statement"],
            "category": r["category"],
            "source": r["source"],
            "coverage_status": "covered" if scenarios else "uncovered",
            "scenario_count": len(scenarios),
            "scenarios": scenarios[:20],
        })

    uncovered = [r for r in rows if r["coverage_status"] != "covered"]
    payload = {
        "schema_version": "BT_REQUIREMENTS_TRACEABILITY_V1",
        "canonical_matrix_schema": "BT_CANONICAL_MATRIX_V2_18COL",
        "metadata": {
            "subsystem": "symphonix-bridge-sdk",
            "requirement_count": len(rows),
            "covered_count": len(rows) - len(uncovered),
            "uncovered_count": len(uncovered),
        },
        "requirements": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {OUT.name} — {payload['metadata']['covered_count']}/{len(rows)} covered")
    if uncovered:
        print("  uncovered:", [u["requirement_id"] for u in uncovered])


if __name__ == "__main__":
    main()
