"""etps — caid-agent NFR Canonical Matrix harness.

Reads ``derived_nfrs.json`` (produced by build_derived_nfrs.py) and emits
one BT_CANONICAL_MATRIX_V1_14COL file per NFR into
``tests/harness/nfr_canonical_matrices/``. Each matrix has the standard
100 scenarios with 85/10/5 distribution.

Run after refreshing the FRs (build_requirements_superset.py) and the
derived NFRs (build_derived_nfrs.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DERIVED = ROOT / "tests" / "harness" / "derived_nfrs.json"
SUPERSET = ROOT / "tests" / "harness" / "requirements_superset.json"
OUT_DIR = ROOT / "tests" / "harness" / "nfr_canonical_matrices"

# Workspace-sibling caid-agent — preferred so changes to the engine flow
# without re-publishing a package.
_SIBLING_CAID_SRC = ROOT.parent / "caid-agent" / "src"
if _SIBLING_CAID_SRC.exists() and str(_SIBLING_CAID_SRC) not in sys.path:
    sys.path.insert(0, str(_SIBLING_CAID_SRC))


def main() -> None:
    try:
        from caid.nfr_canonical_matrix import (
            build_all_nfr_matrices, write_matrices,
        )
        from caid.task_spec import RequirementLink, AcceptanceCriterion
    except ImportError as exc:
        raise SystemExit(
            f"caid-agent NFR canonical-matrix builder not importable "
            f"({exc}). Ensure ../caid-agent is checked out alongside "
            f"this repo, or pip install -e ../caid-agent."
        ) from exc

    if not DERIVED.exists():
        raise SystemExit(
            f"missing {DERIVED} — run build_derived_nfrs.py first"
        )
    if not SUPERSET.exists():
        raise SystemExit(
            f"missing {SUPERSET} — run build_requirements_superset.py first"
        )

    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    if "metadata" in superset and "subsystem" in superset["metadata"]:
        subsystem = superset["metadata"]["subsystem"]
    else:
        subsystem = superset.get("subsystem", "unknown")

    payload = json.loads(DERIVED.read_text(encoding="utf-8"))
    nfrs: list[RequirementLink] = []
    for raw in payload.get("derived_nfrs", []):
        acs = [
            AcceptanceCriterion(
                ac_id=a.get("ac_id", ""),
                given=a.get("given", ""),
                when=a.get("when", ""),
                then=a.get("then", ""),
                test_type=a.get("test_type", "Positive"),
            )
            for a in raw.get("acceptance_criteria", [])
        ]
        nfrs.append(RequirementLink(
            req_id=raw["requirement_id"],
            title=raw.get("title", ""),
            statement=raw.get("statement", ""),
            rationale=raw.get("rationale", ""),
            category=raw.get("category", "non-functional"),
            priority=raw.get("priority", "HIGH"),
            nfr_aspects=[
                raw.get("iso_25010_characteristic", ""),
                raw.get("iso_25010_subcharacteristic", ""),
            ],
            regulatory_ref=raw.get("regulatory_ref", ""),
            trace_links=raw.get("trace_links", []),
            acceptance_criteria=acs,
        ))

    if not nfrs:
        print("[INFO] no NFRs to materialise (empty derived_nfrs.json)")
        return

    matrices = build_all_nfr_matrices(nfrs, subsystem=subsystem)
    written = write_matrices(matrices, OUT_DIR)
    print(
        f"[OK] {OUT_DIR.name} — {len(written)} NFR matrices "
        f"× 100 scenarios each = {len(written) * 100} total"
    )


if __name__ == "__main__":
    main()
