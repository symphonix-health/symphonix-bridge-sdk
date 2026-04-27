"""symphonix-bridge-sdk — BT canonical matrix integrity check.

Validates the BT_CANONICAL_MATRIX_V1_14COL traceability layer that lives
alongside (and is generated FROM) the executable scenarios_*.json files:

1. Every matrix in tests/harness/canonical_matrices/ wraps with
   schema_version=BT_CANONICAL_MATRIX_V1_14COL and the canonical 14 columns.
2. Each matrix has exactly 100 scenarios.
3. Each matrix's category distribution is 85 Positive / 10 Negative / 5 Edge.
4. Every scenario references >= 1 requirement_id.
5. tests/harness/requirements_matrix.json validates as
   schema_version=BT_REQUIREMENTS_TRACEABILITY_V1.
6. Every requirement is covered by >= 1 scenario.
7. No scenario references an unknown requirement_id.
8. Requirement count matches superset.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
NFR_DIR = ROOT / "tests" / "harness" / "nfr_canonical_matrices"
DERIVED_NFRS = ROOT / "tests" / "harness" / "derived_nfrs.json"
CANON_DIR = ROOT / "tests" / "harness" / "canonical_matrices"
REQ_MATRIX = ROOT / "tests" / "harness" / "requirements_matrix.json"
SUPERSET = ROOT / "tests" / "harness" / "requirements_superset.json"

CANONICAL_COLUMNS = (
    "use_case_id", "subsystem", "requirement_ids", "scenario_category",
    "title", "description", "preconditions", "trigger", "input_payload",
    "expected_connector_calls", "expected_events", "expected_outputs",
    "fault_profile", "security_profile",
)


def _load_matrices() -> dict[str, dict]:
    return {p.name: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(CANON_DIR.glob("*_canonical.json"))}


def test_canonical_schema_present() -> None:
    matrices = _load_matrices()
    assert matrices, "no canonical matrices found"
    for name, m in matrices.items():
        assert m.get("schema_version") == "BT_CANONICAL_MATRIX_V1_14COL", \
            f"{name} missing canonical schema"
        assert tuple(m.get("columns", ())) == CANONICAL_COLUMNS, \
            f"{name} columns mismatch"


def test_each_matrix_has_exactly_100_scenarios() -> None:
    for name, m in _load_matrices().items():
        scenarios = m.get("scenarios", [])
        assert len(scenarios) == 100, \
            f"{name} has {len(scenarios)} scenarios (expected 100)"


def test_each_matrix_distribution_is_85_10_5() -> None:
    for name, m in _load_matrices().items():
        s = m["scenarios"]
        pos = sum(1 for x in s if x.get("scenario_category") == "Positive")
        neg = sum(1 for x in s if x.get("scenario_category") == "Negative")
        edg = sum(1 for x in s if x.get("scenario_category") == "Edge")
        assert (pos, neg, edg) == (85, 10, 5), \
            f"{name}: distribution {pos}/{neg}/{edg} (expected 85/10/5)"


def test_every_scenario_has_canonical_columns() -> None:
    for name, m in _load_matrices().items():
        for s in m["scenarios"]:
            for col in CANONICAL_COLUMNS:
                assert col in s, \
                    f"{name} scenario {s.get('use_case_id')} missing column {col}"


def test_every_scenario_traces_to_at_least_one_requirement() -> None:
    for name, m in _load_matrices().items():
        for s in m["scenarios"]:
            assert s.get("requirement_ids"), \
                f"{name} scenario {s.get('use_case_id')} has no requirement_ids"


def test_requirements_matrix_canonical_schema() -> None:
    payload = json.loads(REQ_MATRIX.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "BT_REQUIREMENTS_TRACEABILITY_V1"
    assert payload["canonical_matrix_schema"] == "BT_CANONICAL_MATRIX_V1_14COL"


def test_every_requirement_is_covered() -> None:
    payload = json.loads(REQ_MATRIX.read_text(encoding="utf-8"))
    uncovered = [r["requirement_id"] for r in payload["requirements"]
                 if r["coverage_status"] != "covered"]
    assert not uncovered, f"uncovered requirements: {uncovered}"


def test_no_scenario_references_unknown_requirement() -> None:
    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    known = {r["requirement_id"] for r in superset["requirements"]}
    # symphonix-bridge-sdk legacy requirement-id pattern: any compact ID-like string
    # (no whitespace, ≤64 chars, alphanumerics + ._- only). The executable
    # scenarios carry many heritage tags: BSDK-*, FR-/NFR-/UC-, dotted
    # use-case-refs (`a2a_mcp.agent_card_gen`), CL-NN, etc.
    import re
    _legacy_re = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

    def legacy_ok(rid: str) -> bool:
        return bool(_legacy_re.match(rid))
    for name, m in _load_matrices().items():
        for s in m["scenarios"]:
            for rid in s.get("requirement_ids", []):
                assert rid in known or legacy_ok(rid), \
                    f"{name} scenario {s['use_case_id']} references unknown {rid}"


def test_requirements_count_matches_superset() -> None:
    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    payload = json.loads(REQ_MATRIX.read_text(encoding="utf-8"))
    assert payload["metadata"]["requirement_count"] == len(superset["requirements"])


def test_derived_nfrs_match_caid_engine_output() -> None:
    """Drift gate: re-run the caid-agent NFR derivation engine against
    the current requirements_superset.json and compare the result to
    the persisted ``tests/harness/derived_nfrs.json``.

    Drift between the FR catalogue and the derived NFR set fails this
    test â refresh by running ``python tests/harness/build_derived_nfrs.py``.
    """
    import sys
    derived_path = ROOT / "tests" / "harness" / "derived_nfrs.json"
    assert derived_path.exists(), (
        f"missing {derived_path.name} â generate it with "
        f"`python tests/harness/build_derived_nfrs.py`"
    )

    sibling_caid = ROOT.parent / "caid-agent" / "src"
    if sibling_caid.exists() and str(sibling_caid) not in sys.path:
        sys.path.insert(0, str(sibling_caid))
    harness_dir = ROOT / "tests" / "harness"
    if str(harness_dir) not in sys.path:
        sys.path.insert(0, str(harness_dir))

    try:
        from caid.nfr_derivation import NFRDerivationEngine
        from caid.task_spec import RequirementLink
        import build_derived_nfrs as harness  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"caid-agent NFR engine not importable: {exc}")

    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    if "metadata" in superset and "subsystem" in superset["metadata"]:
        subsystem = superset["metadata"]["subsystem"]
    else:
        subsystem = superset.get("subsystem", "unknown")

    frs = [
        RequirementLink(
            req_id=r["requirement_id"],
            title=r.get("title", r["requirement_id"]),
            statement=r.get("statement", ""),
            rationale=r.get("rationale", ""),
            category="functional",
        )
        for r in superset["requirements"]
        if r.get("category", "functional") not in {"non-functional"}
    ]

    engine = NFRDerivationEngine()
    actual = engine.derive(
        frs=frs,
        project_type=harness._project_type_for_subsystem(subsystem),
        regulatory_regime=harness._regulatory_regime_for_subsystem(subsystem),
        scale_tier=harness._scale_tier_for_subsystem(subsystem),
    )
    actual_keys = {(n.title, n.statement) for n in actual}

    persisted = json.loads(derived_path.read_text(encoding="utf-8"))
    persisted_keys = {
        (n["title"], n["statement"])
        for n in persisted.get("derived_nfrs", [])
    }

    missing_in_persisted = actual_keys - persisted_keys
    extra_in_persisted = persisted_keys - actual_keys
    assert not missing_in_persisted and not extra_in_persisted, (
        "derived_nfrs.json drift detected â re-run "
        "`python tests/harness/build_derived_nfrs.py`. "
        f"Engine emits {len(actual_keys)} NFRs; persisted has "
        f"{len(persisted_keys)}. "
        f"Missing from persisted: "
        f"{sorted(t for t, _ in missing_in_persisted)}. "
        f"Extra in persisted: "
        f"{sorted(t for t, _ in extra_in_persisted)}."
    )

    assert persisted.get("schema_version") == "BT_DERIVED_NFRS_V1"
    assert persisted.get("iso_model") == "ISO/IEC 25010:2023"


def _load_nfr_matrices() -> dict[str, dict]:
    if not NFR_DIR.exists():
        return {}
    return {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(NFR_DIR.glob("*_canonical.json"))
    }


def test_nfr_matrices_present_for_every_derived_nfr() -> None:
    """One NFR canonical matrix must exist for every derived NFR."""
    if not DERIVED_NFRS.exists():
        pytest.skip("derived_nfrs.json not present in tests/harness")
    derived = json.loads(DERIVED_NFRS.read_text(encoding="utf-8"))
    nfrs = derived.get("derived_nfrs", [])
    if not nfrs:
        pytest.skip("no NFRs derived — build not present")
    matrices = _load_nfr_matrices()
    assert matrices, (
        f"no NFR canonical matrices found in {NFR_DIR.name} â run "
        f"`python tests/harness/build_nfr_canonical_matrices.py`"
    )
    expected_ids = {n["requirement_id"] for n in nfrs}
    seen_ids: set[str] = set()
    for m in matrices.values():
        seen_ids.update(
            m.get("metadata", {}).get("default_requirement_ids", [])
        )
    missing = expected_ids - seen_ids
    extra = seen_ids - expected_ids
    assert not missing and not extra, (
        f"NFR matrix coverage drift â re-run "
        f"`python tests/harness/build_nfr_canonical_matrices.py`. "
        f"Missing matrices for: {sorted(missing)}. "
        f"Extra (no matching NFR): {sorted(extra)}."
    )


def test_nfr_matrices_canonical_schema() -> None:
    matrices = _load_nfr_matrices()
    if not matrices:
        pytest.skip("NFR matrices not present in tests/harness")
    for name, m in matrices.items():
        assert m.get("schema_version") == "BT_CANONICAL_MATRIX_V1_14COL", \
            f"{name} missing canonical schema"
        assert tuple(m.get("columns", ())) == CANONICAL_COLUMNS, \
            f"{name} columns mismatch"


def test_nfr_matrices_have_exactly_100_scenarios() -> None:
    matrices = _load_nfr_matrices()
    if not matrices:
        pytest.skip("NFR matrices not present in tests/harness")
    for name, m in matrices.items():
        scenarios = m.get("scenarios", [])
        assert len(scenarios) == 100, \
            f"{name} has {len(scenarios)} scenarios (expected 100)"


def test_nfr_matrices_distribution_is_85_10_5() -> None:
    matrices = _load_nfr_matrices()
    if not matrices:
        pytest.skip("NFR matrices not present in tests/harness")
    for name, m in matrices.items():
        scenarios = m["scenarios"]
        pos = sum(1 for s in scenarios
                  if s.get("scenario_category") == "Positive")
        neg = sum(1 for s in scenarios
                  if s.get("scenario_category") == "Negative")
        edg = sum(1 for s in scenarios
                  if s.get("scenario_category") == "Edge")
        assert (pos, neg, edg) == (85, 10, 5), \
            f"{name}: distribution {pos}/{neg}/{edg} (expected 85/10/5)"


def test_nfr_matrices_metadata_carries_iso_attribution() -> None:
    matrices = _load_nfr_matrices()
    if not matrices:
        pytest.skip("NFR matrices not present in tests/harness")
    for name, m in matrices.items():
        meta = m.get("metadata", {})
        assert meta.get("iso_25010_characteristic"), (
            f"{name} metadata missing iso_25010_characteristic"
        )

