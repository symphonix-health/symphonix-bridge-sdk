from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIREMENTS_MATRIX_RELATIVE_PATH = "tests/harness/requirements_matrix.json"
MATRIX_GLOB = "tests/harness/reduced_json_matrices/*.14col.json"
FUNCTIONAL_SPEC_RELATIVE_PATH = "docs/specifications/functional-requirements.md"
NON_FUNCTIONAL_SPEC_RELATIVE_PATH = "docs/specifications/non-functional-requirements.md"
SEED_TRACE_RELATIVE_PATH = "seed_data/seeded_requirement_traceability.json"

REQUIREMENTS_MATRIX_PATH = ROOT / REQUIREMENTS_MATRIX_RELATIVE_PATH
FUNCTIONAL_SPEC_PATH = ROOT / FUNCTIONAL_SPEC_RELATIVE_PATH
NON_FUNCTIONAL_SPEC_PATH = ROOT / NON_FUNCTIONAL_SPEC_RELATIVE_PATH
SEED_TRACE_PATH = ROOT / SEED_TRACE_RELATIVE_PATH

GENERIC_SEEDED_EVIDENCE_SENTENCE = (
    "has specification, use-case, implementation, test, and seed evidence"
)
GENERIC_ACCEPTANCE_STATEMENT_PARTS = (
    "maintain repo-owned functional behaviour evidence",
    "maintain repo-owned quality attribute evidence",
    "requirement-specific behavior",
    "requirement-specific behaviour",
    GENERIC_SEEDED_EVIDENCE_SENTENCE,
)

REQUIREMENT_ID_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)+\b")
AC_ID_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)+-AC\d{2}\b")

METADATA_REFERENCE_KEYS = {
    "metadata",
    "references",
    "reference",
    "traceability",
}
VALID_REPO_KINDS = {
    "runtime_service",
    "library_or_protocol",
    "non_service_documentation",
}


def load_json(path: Path) -> Any:
    assert path.exists(), f"Required acceptance-alignment file is missing: {path}"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_text(path: Path) -> str:
    assert path.exists(), f"Required acceptance-alignment file is missing: {path}"
    return path.read_text(encoding="utf-8")


def repo_kind() -> str:
    payload = load_json(REQUIREMENTS_MATRIX_PATH)
    candidates: list[Any] = [
        payload.get("repo_kind") if isinstance(payload, dict) else None,
        payload.get("service_evidence_policy") if isinstance(payload, dict) else None,
        payload.get("kind") if isinstance(payload, dict) else None,
    ]
    if isinstance(payload, dict):
        for key in ("metadata", "repo_metadata", "repository", "repo"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                candidates.extend(
                    [
                        nested.get("repo_kind"),
                        nested.get("service_evidence_policy"),
                        nested.get("kind"),
                    ]
                )

    for candidate in candidates:
        normalized = normalized_repo_kind(candidate)
        if not normalized:
            continue
        assert normalized in VALID_REPO_KINDS, (
            f"Unsupported repo_kind {candidate!r}; expected one of "
            f"{sorted(VALID_REPO_KINDS)}"
        )
        return normalized
    return "runtime_service"


def normalized_repo_kind(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s-]+", "_", value.strip().lower())


def rows_from_matrix(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("test_cases", "scenarios", "tests", "cases", "rows"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def requirement_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if requirement_id_from_record(value):
                records.append(value)
                return
            for key in (
                "requirements",
                "functional_requirements",
                "non_functional_requirements",
                "nonfunctional_requirements",
            ):
                child = value.get(key)
                if isinstance(child, list):
                    for item in child:
                        visit(item)
            if not records:
                for child in value.values():
                    if isinstance(child, dict | list):
                        visit(child)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return dedupe_records(records)


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        requirement_id = requirement_id_from_record(record)
        if not requirement_id or requirement_id in seen:
            continue
        seen.add(requirement_id)
        unique_records.append(record)
    return unique_records


def requirement_id_from_record(record: dict[str, Any]) -> str:
    for key in ("requirement_id", "id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def active_acceptance_criteria(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    criteria = requirement.get("acceptance_criteria", [])
    if not isinstance(criteria, list):
        return []
    active_records = []
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        status = str(criterion.get("status", "")).strip().lower()
        if criterion.get("ac_id") and status == "active":
            active_records.append(criterion)
    return active_records


def requirements_by_id() -> dict[str, dict[str, Any]]:
    payload = load_json(REQUIREMENTS_MATRIX_PATH)
    requirements = requirement_records(payload)
    assert requirements, "requirements_matrix.json did not contain requirements"
    return {requirement_id_from_record(item): item for item in requirements}


def active_acceptance_criteria_by_id() -> dict[str, dict[str, Any]]:
    criteria: dict[str, dict[str, Any]] = {}
    for requirement in requirements_by_id().values():
        for criterion in active_acceptance_criteria(requirement):
            criteria[str(criterion["ac_id"])] = criterion
    return criteria


def active_acceptance_ids_by_requirement() -> dict[str, set[str]]:
    ids_by_requirement: dict[str, set[str]] = {}
    for requirement_id, requirement in requirements_by_id().items():
        ids_by_requirement[requirement_id] = {
            str(criterion["ac_id"])
            for criterion in active_acceptance_criteria(requirement)
        }
    return ids_by_requirement


def load_14col_rows() -> list[tuple[Path, int, dict[str, Any]]]:
    rows: list[tuple[Path, int, dict[str, Any]]] = []
    for path in sorted(ROOT.glob(MATRIX_GLOB)):
        for index, row in enumerate(rows_from_matrix(load_json(path)), start=1):
            rows.append((path, index, row))
    assert rows, f"No 14-column matrix rows found with glob: {MATRIX_GLOB}"
    return rows


def requirement_ids_from_row(row: dict[str, Any]) -> list[str]:
    ids: list[str] = []

    def walk(value: Any, key_hint: str | None = None) -> None:
        key = (key_hint or "").lower()
        if key in {
            "acceptance_criteria",
            "acceptance_criteria_id",
            "acceptance_criteria_ids",
            "ac_id",
            "ac_ids",
        }:
            return

        if key in {"tags", "notes"} or key in METADATA_REFERENCE_KEYS:
            add_requirement_ids_from_value(value, ids)

        if "requirement" in key:
            add_requirement_ids_from_value(value, ids)
            return

        if isinstance(value, dict):
            for child_key, child_value in value.items():
                child_key_lower = str(child_key).lower()
                if child_key_lower in (
                    METADATA_REFERENCE_KEYS
                    | {
                        "security_context",
                        "test_data",
                        "tags",
                        "notes",
                    }
                ) or isinstance(child_value, dict | list | tuple | set):
                    walk(child_value, str(child_key))
                elif "requirement" in child_key_lower:
                    walk(child_value, str(child_key))
        elif isinstance(value, list | tuple | set):
            for item in value:
                walk(item, key_hint)

    walk(row)
    return ordered_unique(ids)


def add_requirement_ids_from_value(value: Any, ids: list[str]) -> None:
    if isinstance(value, str):
        ids.extend(requirement_ids_from_text(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {
                "acceptance_criteria",
                "acceptance_criteria_id",
                "acceptance_criteria_ids",
                "ac_id",
                "ac_ids",
            }:
                continue
            add_requirement_ids_from_value(child, ids)
    elif isinstance(value, list | tuple | set):
        for item in value:
            add_requirement_ids_from_value(item, ids)


def row_test_data_requirement_ids(row: dict[str, Any]) -> list[str]:
    test_data = row.get("test_data")
    if not isinstance(test_data, dict):
        return []
    ids: list[str] = []
    add_requirement_ids_from_value(test_data.get("requirement_ids"), ids)
    return ordered_unique(ids)


def row_test_data_acceptance_ids(row: dict[str, Any]) -> list[str]:
    test_data = row.get("test_data")
    if not isinstance(test_data, dict):
        return []
    ids: list[str] = []
    add_acceptance_ids_from_value(test_data.get("acceptance_criteria_ids"), ids)
    return ordered_unique(ids)


def acceptance_ids_from_row(row: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    add_acceptance_ids_from_value(row.get("test_data"), ids)
    add_acceptance_ids_from_value(row.get("metadata"), ids)
    add_acceptance_ids_from_value(row.get("traceability"), ids)
    add_acceptance_ids_from_value(row.get("tags"), ids)
    add_acceptance_ids_from_value(row.get("notes"), ids)
    return ordered_unique(ids)


def add_acceptance_ids_from_value(value: Any, ids: list[str]) -> None:
    if isinstance(value, str):
        ids.extend(AC_ID_RE.findall(value))
    elif isinstance(value, dict):
        for child in value.values():
            add_acceptance_ids_from_value(child, ids)
    elif isinstance(value, list | tuple | set):
        for item in value:
            add_acceptance_ids_from_value(item, ids)


def requirement_ids_from_text(text: str) -> list[str]:
    text_without_ac_ids = AC_ID_RE.sub(" ", text)
    return [
        candidate
        for candidate in REQUIREMENT_ID_RE.findall(text_without_ac_ids)
        if candidate_has_requirement_shape(candidate)
    ]


def candidate_has_requirement_shape(candidate: str) -> bool:
    return any(character.isdigit() for character in candidate) or candidate.startswith(
        ("FR-", "NFR-", "REQ-", "UC-")
    )


def ordered_unique(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def relative_row_id(path: Path, index: int, row: dict[str, Any]) -> str:
    row_id = row.get("use_case_id") or row.get("id") or row.get("scenario_id")
    if isinstance(row_id, str) and row_id.strip():
        return row_id.strip()
    return f"{path.relative_to(ROOT)}:{index}"


def is_generic_acceptance_statement(statement: Any) -> bool:
    if not isinstance(statement, str):
        return False
    normalized = statement.lower()
    return any(part in normalized for part in GENERIC_ACCEPTANCE_STATEMENT_PARTS)


def documented_non_service_exception(
    requirement: dict[str, Any],
    criterion: dict[str, Any],
    relevant_spec_lines: list[str],
) -> bool:
    requirement_context = {
        key: value for key, value in requirement.items() if key != "acceptance_criteria"
    }
    evidence_blob = json.dumps(
        {
            "requirement": requirement_context,
            "criterion": criterion,
            "spec_lines": relevant_spec_lines,
        },
        ensure_ascii=True,
        sort_keys=True,
    ).lower()
    non_service_markers = (
        "non-service",
        "non_service",
        "non_service_documentation",
        "declared non-service",
        "documentation evidence",
        "documentation_path",
    )
    return any(marker in evidence_blob for marker in non_service_markers)


def spec_lines_for(requirement_id: str, ac_id: str, specs: str) -> list[str]:
    requirement_key = requirement_id.lower()
    ac_key = ac_id.lower()
    return [
        line
        for line in specs.splitlines()
        if requirement_key in line.lower() or ac_key in line.lower()
    ]


def spec_has_acceptance_criteria_wording(spec_text: str) -> bool:
    normalized = spec_text.lower().replace("-", " ")
    return "acceptance criteria" in normalized


def test_every_requirement_has_acceptance_criteria() -> None:
    requirements = requirements_by_id()
    missing: list[str] = []
    duplicate_ac_ids: list[str] = []
    generic_ac_ids: list[str] = []
    seen_ac_ids: set[str] = set()

    for requirement_id, requirement in requirements.items():
        active_criteria = active_acceptance_criteria(requirement)
        if not active_criteria:
            missing.append(requirement_id)
            continue

        for criterion in active_criteria:
            ac_id = str(criterion["ac_id"])
            if ac_id in seen_ac_ids:
                duplicate_ac_ids.append(ac_id)
            seen_ac_ids.add(ac_id)
            if is_generic_acceptance_statement(criterion.get("statement")):
                generic_ac_ids.append(ac_id)

    assert not missing, (
        "Every requirement must have at least one active acceptance criterion. "
        f"Missing: {missing}"
    )
    assert not duplicate_ac_ids, (
        "Acceptance criterion IDs must be unique. "
        f"Duplicates: {sorted(set(duplicate_ac_ids))}"
    )
    assert not generic_ac_ids, (
        "Acceptance criteria must not use generic seeded evidence wording. "
        f"Generic AC IDs: {generic_ac_ids}"
    )


def test_every_14col_requirement_row_maps_to_acceptance_criteria() -> None:
    valid_ac_ids_by_requirement = active_acceptance_ids_by_requirement()
    valid_requirement_ids = set(valid_ac_ids_by_requirement)
    valid_ac_ids = set(active_acceptance_criteria_by_id())
    failures: list[str] = []

    for path, index, row in load_14col_rows():
        row_ref = relative_row_id(path, index, row)
        row_requirement_ids = row_test_data_requirement_ids(row)
        row_ac_ids = set(row_test_data_acceptance_ids(row))
        if not row_requirement_ids:
            failures.append(
                f"{row_ref} must include at least one requirement ID in test_data"
            )
        if not row_ac_ids:
            failures.append(f"{row_ref} must include at least one AC ID in test_data")

        unknown_ac_ids = sorted(row_ac_ids - valid_ac_ids)
        if unknown_ac_ids:
            failures.append(f"{row_ref} references unknown AC IDs {unknown_ac_ids}")

        if not row_requirement_ids:
            continue
        unknown_requirements = sorted(set(row_requirement_ids) - valid_requirement_ids)
        requirements_without_ac_coverage: list[str] = []

        for requirement_id in row_requirement_ids:
            requirement_ac_ids = valid_ac_ids_by_requirement.get(requirement_id)
            if not requirement_ac_ids:
                continue
            if not row_ac_ids.intersection(requirement_ac_ids):
                requirements_without_ac_coverage.append(requirement_id)

        if unknown_requirements:
            failures.append(
                f"{row_ref} references unknown requirements {unknown_requirements}"
            )
        if row_ac_ids and requirements_without_ac_coverage:
            failures.append(
                f"{row_ref} lacks row-level AC coverage for requirement IDs "
                f"{requirements_without_ac_coverage}"
            )

    assert not failures, "\n".join(failures)


def test_every_acceptance_criterion_has_matrix_evidence() -> None:
    current_repo_kind = repo_kind()
    requirements = requirements_by_id()
    all_active_ac_ids = active_acceptance_criteria_by_id()
    covered_ac_ids: set[str] = set()
    for _, _, row in load_14col_rows():
        covered_ac_ids.update(
            ac_id
            for ac_id in row_test_data_acceptance_ids(row)
            if ac_id in all_active_ac_ids
        )

    specs = "\n".join(
        [load_text(FUNCTIONAL_SPEC_PATH), load_text(NON_FUNCTIONAL_SPEC_PATH)]
    )
    missing: list[str] = []
    for requirement_id, requirement in requirements.items():
        for criterion in active_acceptance_criteria(requirement):
            ac_id = str(criterion["ac_id"])
            if ac_id in covered_ac_ids:
                continue
            has_non_service_exception = documented_non_service_exception(
                requirement,
                criterion,
                spec_lines_for(requirement_id, ac_id, specs),
            )
            if (
                current_repo_kind == "non_service_documentation"
                and has_non_service_exception
            ):
                continue
            if has_non_service_exception:
                missing.append(
                    f"{requirement_id}:{ac_id} uses a documented non-service "
                    f"exception, but repo_kind is {current_repo_kind}"
                )
                continue
            missing.append(f"{requirement_id}:{ac_id}")

    assert not missing, (
        "Every active AC ID must be covered by a 14-column row or a "
        f"documented non-service exception. Missing: {missing}"
    )


def test_specs_include_acceptance_criteria() -> None:
    functional_spec = load_text(FUNCTIONAL_SPEC_PATH)
    non_functional_spec = load_text(NON_FUNCTIONAL_SPEC_PATH)
    combined_specs = f"{functional_spec}\n{non_functional_spec}"

    assert spec_has_acceptance_criteria_wording(functional_spec), (
        "functional-requirements.md must include acceptance criteria wording "
        "or a dedicated acceptance criteria section"
    )
    assert spec_has_acceptance_criteria_wording(non_functional_spec), (
        "non-functional-requirements.md must include acceptance criteria "
        "wording or a dedicated acceptance criteria section"
    )

    missing_requirement_ids: list[str] = []
    missing_ac_ids: list[str] = []
    for requirement_id, requirement in requirements_by_id().items():
        if requirement_id not in combined_specs:
            missing_requirement_ids.append(requirement_id)
        for criterion in active_acceptance_criteria(requirement):
            ac_id = str(criterion["ac_id"])
            if ac_id not in combined_specs:
                missing_ac_ids.append(ac_id)

    assert not missing_requirement_ids, (
        f"Specs must include every requirement ID. Missing: {missing_requirement_ids}"
    )
    assert not missing_ac_ids, (
        "Specs must include every active acceptance criterion ID. "
        f"Missing: {missing_ac_ids}"
    )


def test_seed_trace_includes_acceptance_criteria() -> None:
    # Runtime and library repos must keep seed traceability; documentation-only
    # repos still prove acceptance coverage through the specification test.
    if repo_kind() == "non_service_documentation":
        return

    seed_trace = load_json(SEED_TRACE_PATH)
    seed_trace_ac_ids: list[str] = []
    add_acceptance_ids_from_value(seed_trace, seed_trace_ac_ids)
    seed_trace_ac_id_set = set(seed_trace_ac_ids)

    missing_ac_ids: list[str] = []
    for requirement in requirements_by_id().values():
        for criterion in active_acceptance_criteria(requirement):
            ac_id = str(criterion["ac_id"])
            if ac_id not in seed_trace_ac_id_set:
                missing_ac_ids.append(ac_id)

    assert not missing_ac_ids, (
        "seeded_requirement_traceability.json must include every active AC ID. "
        f"Missing: {missing_ac_ids}"
    )
