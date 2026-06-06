from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIREMENTS_MATRIX_PATH = ROOT / "tests/harness/requirements_matrix.json"
FUNCTIONAL_SPEC_PATH = ROOT / "docs/specifications/functional-requirements.md"
NON_FUNCTIONAL_SPEC_PATH = ROOT / "docs/specifications/non-functional-requirements.md"
ARCHITECTURE_SPEC_PATH = ROOT / "docs/specifications/architecture-specification.md"
DESIGN_SPEC_PATH = ROOT / "docs/specifications/design-specification.md"

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

GENERIC_ACCEPTANCE_STATEMENT_PARTS = (
    "maintain repo-owned functional behaviour evidence",
    "maintain repo-owned quality attribute evidence",
    "requirement-specific behavior",
    "requirement-specific behaviour",
    "has specification, use-case, implementation, test, and seed evidence",
)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _text(path: Path) -> str:
    assert path.exists(), f"Missing specification artefact: {path}"
    return path.read_text(encoding="utf-8")


def _requirements() -> list[dict[str, Any]]:
    payload = _load_json(REQUIREMENTS_MATRIX_PATH)
    requirements = payload.get("requirements", [])
    assert isinstance(requirements, list)
    return [item for item in requirements if isinstance(item, dict)]


def _active_ac_ids(requirement: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for criterion in requirement.get("acceptance_criteria", []):
        if not isinstance(criterion, dict):
            continue
        if criterion.get("status") == "active" and criterion.get("ac_id"):
            ids.append(str(criterion["ac_id"]))
    return ids


def _is_nfr(requirement: dict[str, Any]) -> bool:
    category = str(requirement.get("category", "")).strip().lower()
    if category in {"non-functional", "non_functional", "nfr"}:
        return True
    if category in {"functional", "fr"}:
        return False
    requirement_id = str(requirement.get("requirement_id", "")).upper()
    if requirement_id.startswith("NFR") or "-NFR-" in requirement_id:
        return True
    return bool(set(requirement_id.split("-")) & NFR_TOKENS)


def _requirements_for(*, non_functional: bool) -> list[dict[str, Any]]:
    return [
        requirement
        for requirement in _requirements()
        if _is_nfr(requirement) is non_functional
    ]


def test_specification_set_exists_and_links_canonical_sources() -> None:
    for path in (
        FUNCTIONAL_SPEC_PATH,
        NON_FUNCTIONAL_SPEC_PATH,
        ARCHITECTURE_SPEC_PATH,
        DESIGN_SPEC_PATH,
    ):
        assert path.exists(), str(path)

    combined = "\n".join(
        _text(path)
        for path in (
            FUNCTIONAL_SPEC_PATH,
            NON_FUNCTIONAL_SPEC_PATH,
            ARCHITECTURE_SPEC_PATH,
            DESIGN_SPEC_PATH,
        )
    )
    for required_path in (
        "tests/harness/requirements_matrix.json",
        "tests/harness/reduced_json_matrices",
        "seed_data/seeded_requirement_traceability.json",
        "tests/test_requirement_acceptance_alignment.py",
    ):
        assert required_path in combined


def test_functional_and_non_functional_specs_include_acceptance_criteria() -> None:
    functional_text = _text(FUNCTIONAL_SPEC_PATH)
    non_functional_text = _text(NON_FUNCTIONAL_SPEC_PATH)
    assert "## Acceptance criteria" in functional_text
    assert "## Acceptance criteria" in non_functional_text


def test_functional_and_non_functional_specs_cover_requirement_and_ac_ids() -> None:
    functional_text = _text(FUNCTIONAL_SPEC_PATH)
    non_functional_text = _text(NON_FUNCTIONAL_SPEC_PATH)
    functional_requirements = _requirements_for(non_functional=False)
    non_functional_requirements = _requirements_for(non_functional=True)
    assert functional_requirements
    assert non_functional_requirements

    missing_functional: list[str] = []
    missing_non_functional: list[str] = []
    missing_functional_ac: list[str] = []
    missing_non_functional_ac: list[str] = []

    for requirement in functional_requirements:
        requirement_id = str(requirement["requirement_id"])
        if requirement_id not in functional_text:
            missing_functional.append(requirement_id)
        for ac_id in _active_ac_ids(requirement):
            if ac_id not in functional_text:
                missing_functional_ac.append(ac_id)

    for requirement in non_functional_requirements:
        requirement_id = str(requirement["requirement_id"])
        if requirement_id not in non_functional_text:
            missing_non_functional.append(requirement_id)
        for ac_id in _active_ac_ids(requirement):
            if ac_id not in non_functional_text:
                missing_non_functional_ac.append(ac_id)

    assert not missing_functional
    assert not missing_non_functional
    assert not missing_functional_ac
    assert not missing_non_functional_ac


def test_architecture_spec_has_high_and_low_level_diagrams() -> None:
    architecture_text = _text(ARCHITECTURE_SPEC_PATH)
    assert "## High-level architecture diagram" in architecture_text
    assert "## Low-level architecture diagram" in architecture_text
    assert architecture_text.count("```mermaid") >= 2


def test_generic_seeded_acceptance_wording_is_absent() -> None:
    acceptance_text = "\n".join(
        [_text(FUNCTIONAL_SPEC_PATH), _text(NON_FUNCTIONAL_SPEC_PATH)]
    ).lower()
    for phrase in GENERIC_ACCEPTANCE_STATEMENT_PARTS:
        assert phrase not in acceptance_text
