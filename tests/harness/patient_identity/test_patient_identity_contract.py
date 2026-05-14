from __future__ import annotations

import json
import re
import shutil
import subprocess
from os import walk
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT.parent
MATRIX_PATH = Path(__file__).with_name("requirements_matrix.json")
SCENARIOS_PATH = Path(__file__).with_name("patient_identity_scenarios.json")

CANONICAL_PATIENT_SYSTEM = "https://fhir.symphonix.health/Id/patient"
NHS_NUMBER_SYSTEM = "https://fhir.nhs.uk/Id/nhs-number"
MAX_STATIC_SCAN_FINDINGS_PER_REPO = 10
LOCAL_PATIENT_ID_PATTERN = (
    r"(?:Patient/|patient[_-]?id[^\n]{0,80}|patient[_-]?ref[^\n]{0,80}|subject[^\n]{0,80})"
    r"\b(?:ke-)?pat-\d{3,}(?:-\d+)?\b"
    r"|\b(?:ke-)?pat-\d{3,}(?:-\d+)?\b[^\n]{0,80}(?:patient[_-]?id|patient[_-]?ref)"
)
STATIC_SCAN_PATTERN = (
    r"\bnhs_number\b"
    r"|\bpatient_nhs_number\b"
    r"|\bnhsNumber\b"
    r"|NHS Number as primary patient identifier"
    r"|generate_id\([^)]*PAT-"
    rf"|{LOCAL_PATIENT_ID_PATTERN}"
    r"|\bmpiId\s+TEXT\s+PRIMARY\s+KEY\b"
)
CANONICAL_COLUMNS = {
    "use_case_id",
    "subsystem",
    "requirement_ids",
    "scenario_category",
    "title",
    "description",
    "preconditions",
    "trigger",
    "input_payload",
    "expected_connector_calls",
    "expected_events",
    "expected_outputs",
    "fault_profile",
    "security_profile",
    "priority",
    "automation_status",
    "estimated_duration_seconds",
    "tags",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk(obj: Any) -> list[Any]:
    values = [obj]
    if isinstance(obj, dict):
        for value in obj.values():
            values.extend(_walk(value))
    elif isinstance(obj, list):
        for value in obj:
            values.extend(_walk(value))
    return values


def _is_valid_modulus_11(value: str) -> bool:
    if not re.fullmatch(r"\d{10}", value):
        return False
    if len(set(value)) == 1:
        return False
    total = sum(int(digit) * weight for digit, weight in zip(value[:9], range(10, 1, -1), strict=True))
    check_digit = 11 - (total % 11)
    if check_digit == 11:
        check_digit = 0
    if check_digit == 10:
        return False
    return check_digit == int(value[-1])


def _scan_repo_with_rg(repo: Path) -> list[str] | None:
    rg = shutil.which("rg")
    if not rg:
        return None

    ignored_globs = [
        "!.cache/**",
        "!.claude/**",
        "!.codex/**",
        "!.git/**",
        "!.mypy_cache/**",
        "!.next/**",
        "!.pytest_cache/**",
        "!.ruff_cache/**",
        "!.turbo/**",
        "!.venv/**",
        "!__pycache__/**",
        "!build/**",
        "!coverage/**",
        "!dist/**",
        "!htmlcov/**",
        "!node_modules/**",
        "!playwright-report/**",
        "!site-packages/**",
        "!test-results/**",
        "!venv/**",
    ]
    suffix_globs = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.md", "*.json", "*.yaml", "*.yml"]
    command = [
        rg,
        "--files-with-matches",
        "--ignore-case",
        "--no-messages",
        "--regexp",
        STATIC_SCAN_PATTERN,
    ]
    for glob in ignored_globs + suffix_globs:
        command.extend(["--glob", glob])
    command.append(str(repo))

    findings: list[str] = []
    process = subprocess.Popen(
        command,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            path = Path(line.strip())
            if not path.exists():
                continue
            findings.append(str(path.relative_to(WORKSPACE)))
            if len(findings) >= MAX_STATIC_SCAN_FINDINGS_PER_REPO:
                process.kill()
                break
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        if findings:
            return findings
        return None

    if process.returncode not in {0, 1, -9, 1_073_741_515} and not findings:
        return None
    return findings


def _scan_repo_with_git_grep(repo: Path) -> list[str] | None:
    suffix_globs = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.md", "*.json", "*.yaml", "*.yml"]
    command = [
        "git",
        "-C",
        str(repo),
        "grep",
        "-I",
        "-l",
        "-i",
        "-P",
        "-e",
        STATIC_SCAN_PATTERN,
        "--",
        *suffix_globs,
    ]

    findings: list[str] = []
    process = subprocess.Popen(
        command,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            path = repo / line.strip()
            if not path.exists():
                continue
            findings.append(str(path.relative_to(WORKSPACE)))
            if len(findings) >= MAX_STATIC_SCAN_FINDINGS_PER_REPO:
                process.kill()
                break
        process.wait(timeout=35)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        if findings:
            return findings
        return [f"{repo.relative_to(WORKSPACE)} static identity scan timed out"]

    if process.returncode not in {0, 1, -9} and not findings:
        return None
    return findings


def _origin_url(repo: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def _github_owner_and_repo(origin_url: str) -> tuple[str, str]:
    match = re.search(
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        origin_url,
        re.IGNORECASE,
    )
    if not match:
        return "", ""
    return match.group("owner"), match.group("repo")


def _discover_symphonix_patient_data_repos() -> list[Path]:
    candidates: dict[str, list[Path]] = {}
    for repo in sorted(WORKSPACE.iterdir(), key=lambda path: path.name.lower()):
        if not repo.is_dir() or not (repo / ".git").exists():
            continue
        if repo == ROOT:
            continue
        origin_url = _origin_url(repo)
        owner, remote_repo = _github_owner_and_repo(origin_url)
        if owner.lower() != "symphonix-health":
            continue
        candidates.setdefault(f"{owner.lower()}/{remote_repo.lower()}", []).append(repo)

    selected: list[Path] = []
    for remote_key, repos in sorted(candidates.items(), key=lambda item: item[0].lower()):
        slug = remote_key.rsplit("/", 1)[-1]
        canonical = next((repo for repo in repos if repo.name.lower() == slug), repos[0])
        selected.append(canonical)
    return selected


def test_patient_identity_static_repo_discovery_covers_local_symphonix_health_repos() -> None:
    candidates: dict[str, list[Path]] = {}
    for repo in sorted(WORKSPACE.iterdir(), key=lambda path: path.name.lower()):
        if not repo.is_dir() or not (repo / ".git").exists() or repo == ROOT:
            continue
        owner, remote_repo = _github_owner_and_repo(_origin_url(repo))
        if owner.lower() != "symphonix-health":
            continue
        candidates.setdefault(f"{owner.lower()}/{remote_repo.lower()}", []).append(repo)

    expected: list[str] = []
    for remote_key, repos in sorted(candidates.items(), key=lambda item: item[0].lower()):
        slug = remote_key.rsplit("/", 1)[-1]
        canonical = next((repo for repo in repos if repo.name.lower() == slug), repos[0])
        expected.append(canonical.name)

    discovered = [repo.name for repo in _discover_symphonix_patient_data_repos()]

    assert discovered == expected
    assert "HMIS" in discovered
    assert "mha-administration" in discovered
    assert "africa-marketplace" not in discovered
    assert "symphonix-health-docs" not in discovered
    assert "BulletTrain-gap-2-signatures" not in discovered


def test_patient_identity_requirements_are_traced_to_scenarios() -> None:
    matrix = _load_json(MATRIX_PATH)
    scenarios = _load_json(SCENARIOS_PATH)["scenarios"]
    scenario_ids = {scenario["use_case_id"] for scenario in scenarios}

    requirements = matrix["requirements"]
    requirement_ids = [requirement["requirement_id"] for requirement in requirements]

    assert matrix["metadata"]["canonical_identifier_system"] == CANONICAL_PATIENT_SYSTEM
    assert matrix["metadata"]["nhs_number_system"] == NHS_NUMBER_SYSTEM
    assert matrix["metadata"]["requirement_count"] == len(requirements)
    assert len(requirement_ids) == len(set(requirement_ids))

    for requirement in requirements:
        assert requirement["priority"] in {"P0", "P1", "P2"}
        assert requirement["scenario_ids"], requirement["requirement_id"]
        assert set(requirement["scenario_ids"]).issubset(scenario_ids)


def test_patient_identity_scenarios_follow_canonical_matrix_shape() -> None:
    payload = _load_json(SCENARIOS_PATH)
    scenarios = payload["scenarios"]
    distribution = payload["metadata"]["distribution"]

    assert payload["metadata"]["scenario_count"] == len(scenarios)
    assert distribution["positive"] == sum(s["scenario_category"] == "Positive" for s in scenarios)
    assert distribution["negative"] == sum(s["scenario_category"] == "Negative" for s in scenarios)
    assert distribution["edge"] == sum(s["scenario_category"] == "Edge" for s in scenarios)

    for scenario in scenarios:
        assert CANONICAL_COLUMNS.issubset(scenario.keys()), scenario["use_case_id"]
        assert scenario["trigger"]["idempotency_key"].startswith("idem-")
        assert scenario["input_payload"]
        assert scenario["expected_events"]
        assert scenario["security_profile"]["expected_auth_result"] in {"ALLOW", "DENY"}


def test_patient_identity_scenarios_use_spid_fields_not_internal_nhs_number_fields() -> None:
    scenarios = _load_json(SCENARIOS_PATH)["scenarios"]
    forbidden_internal_keys = {"nhs_number", "nhsNumber", "patient_nhs_number", "nationalID"}

    for scenario in scenarios:
        for value in _walk(scenario):
            if isinstance(value, dict):
                assert forbidden_internal_keys.isdisjoint(value.keys()), scenario["use_case_id"]
                if value.get("identifier_system"):
                    assert value["identifier_system"] == CANONICAL_PATIENT_SYSTEM
                if value.get("system") == NHS_NUMBER_SYSTEM:
                    assert "external" in scenario["description"].lower() or "alias" in scenario["description"].lower()


def test_patient_identity_scenario_patient_ids_are_modulus_11_valid() -> None:
    scenarios = _load_json(SCENARIOS_PATH)["scenarios"]
    patient_id_keys = {"patient_id", "candidate_patient_id", "source_patient_id", "target_patient_id"}

    for scenario in scenarios:
        expects_invalid_checksum = scenario["fault_profile"]["mode"] == "invalid_check_digit"
        for value in _walk(scenario):
            if isinstance(value, dict):
                for key in patient_id_keys.intersection(value.keys()):
                    patient_id = value[key]
                    if isinstance(patient_id, str) and re.fullmatch(r"\d{10}", patient_id):
                        if expects_invalid_checksum:
                            assert not _is_valid_modulus_11(patient_id), (scenario["use_case_id"], key, patient_id)
                        else:
                            assert _is_valid_modulus_11(patient_id), (scenario["use_case_id"], key, patient_id)


@pytest.mark.contract
def test_patient_identity_static_repo_scan_enforce_mode() -> None:
    patient_data_repos = _discover_symphonix_patient_data_repos()
    forbidden_patterns = [
        re.compile(r"\bnhs_number\b"),
        re.compile(r"\bpatient_nhs_number\b"),
        re.compile(r"\bnhsNumber\b"),
        re.compile(r"NHS Number as primary patient identifier", re.IGNORECASE),
        re.compile(r"generate_id\([^)]*PAT-"),
        re.compile(LOCAL_PATIENT_ID_PATTERN, re.IGNORECASE),
        re.compile(r"\bmpiId\s+TEXT\s+PRIMARY\s+KEY\b", re.IGNORECASE),
    ]
    suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".yaml", ".yml"}
    ignored_dirs = {
        ".cache",
        ".claude",
        ".codex",
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".turbo",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "playwright-report",
        "site-packages",
        "test-results",
        "venv",
    }

    findings: list[str] = []
    for repo in patient_data_repos:
        if not repo.exists():
            continue
        git_grep_findings = _scan_repo_with_git_grep(repo)
        if git_grep_findings is not None:
            findings.extend(git_grep_findings)
            continue

        rg_findings = _scan_repo_with_rg(repo)
        if rg_findings is not None:
            findings.extend(rg_findings)
            continue

        repo_findings: list[str] = []
        for root, dirs, files in walk(repo):
            dirs[:] = [directory for directory in dirs if directory not in ignored_dirs]
            root_path = Path(root)
            for filename in files:
                path = root_path / filename
                if path.suffix not in suffixes:
                    continue
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                for pattern in forbidden_patterns:
                    if pattern.search(text):
                        repo_findings.append(str(path.relative_to(WORKSPACE)))
                        break
                if len(repo_findings) >= MAX_STATIC_SCAN_FINDINGS_PER_REPO:
                    break
            if len(repo_findings) >= MAX_STATIC_SCAN_FINDINGS_PER_REPO:
                break
        findings.extend(repo_findings)

    assert not findings, (
        "Every Symphonix patient-data sibling must use the same internal SPID; "
        "external identifiers must be aliases only.\n"
        "Legacy patient identity patterns remain:\n" + "\n".join(findings)
    )
