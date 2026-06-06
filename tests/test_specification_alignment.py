from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATHS = {
    "functional": "docs/specifications/functional-requirements.md",
    "non_functional": "docs/specifications/non-functional-requirements.md",
    "design": "docs/specifications/design-specification.md",
    "architecture": "docs/specifications/architecture-specification.md",
}
NFR_TOKENS = {
    "ACC",
    "AUD",
    "AVL",
    "AVAIL",
    "CO",
    "OBS",
    "PER",
    "PERF",
    "PRV",
    "PRIV",
    "REL",
    "RES",
    "SAF",
    "SCL",
    "SEC",
}


def _load_traceability() -> object:
    module_path = ROOT / "seeded_alignment_trace.py"
    spec = importlib.util.spec_from_file_location("seeded_alignment_trace", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_nfr(requirement_id: str) -> bool:
    upper = requirement_id.upper()
    if upper.startswith("NFR") or "-NFR-" in upper or upper.startswith("DCB"):
        return True
    return bool(set(upper.split("-")) & NFR_TOKENS)


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_specification_set_exists_and_links_canonical_sources() -> None:
    module = _load_traceability()
    requirement_ids = set(module.REQUIREMENT_IDS)
    assert requirement_ids

    for path in SPEC_PATHS.values():
        assert (ROOT / path).exists(), path

    combined = "\n".join(_text(path) for path in SPEC_PATHS.values())
    for required_path in (
        "seeded_alignment_trace.py",
        "tests/harness/reduced_json_matrices/seeded_alignment_trace.14col.json",
        "seed_data/seeded_requirement_traceability.json",
        "tests/test_seeded_alignment_traceability.py",
    ):
        assert required_path in combined


def test_functional_and_non_functional_specs_cover_requirement_ids() -> None:
    module = _load_traceability()
    functional_text = _text(SPEC_PATHS["functional"])
    non_functional_text = _text(SPEC_PATHS["non_functional"])
    functional_ids = [rid for rid in module.REQUIREMENT_IDS if not _is_nfr(rid)]
    nfr_ids = [rid for rid in module.REQUIREMENT_IDS if _is_nfr(rid)]
    assert functional_ids
    assert nfr_ids

    missing_functional = [rid for rid in functional_ids if rid not in functional_text]
    missing_nfr = [rid for rid in nfr_ids if rid not in non_functional_text]
    assert not missing_functional
    assert not missing_nfr


def test_architecture_spec_has_high_and_low_level_diagrams() -> None:
    architecture_text = _text(SPEC_PATHS["architecture"])
    assert "## High-level architecture diagram" in architecture_text
    assert "## Low-level architecture diagram" in architecture_text
    assert architecture_text.count("```mermaid") >= 2
    for layer in (
        "Requirements and signal ingestion",
        "Foundation and standardization",
        "Design intelligence",
        "Implementation and execution",
        "Evaluation and learning",
        "Clinical governance",
        "REA requirements QA",
        "Self-improvement feedback",
    ):
        assert layer in architecture_text


def test_design_spec_is_reverse_engineered_from_codebase_and_requirements() -> None:
    design_text = _text(SPEC_PATHS["design"])
    assert "Reverse-engineered codebase profile" in design_text
    assert "Requirement alignment" in design_text
    assert "Symphonix Health design constraints" in design_text
    assert "Canonical use-case matrix" in design_text
