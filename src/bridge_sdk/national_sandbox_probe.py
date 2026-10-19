"""National Sandbox Contract Probe (E-11) for NHS Spine/PDS/EPS/e-RS/GP Connect/MESH and Kenya KHIS/SHA.

Provides deterministic header-contract validation, response-contract validation,
and live sandbox endpoint probing without synthetic or mocked fallback responses.
When a sandbox endpoint is unreachable or violates contract headers/payloads,
the probe fails closed with explicit diagnostic findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class NationalSandboxContractSpec:
    """Contract specification for a national healthcare integration sandbox."""

    sandbox_key: str
    jurisdiction: str
    display_name: str
    probe_method: str
    probe_path: str
    required_request_headers: tuple[str, ...]
    expected_status_codes: tuple[int, ...]
    expected_resource_types: tuple[str, ...]
    content_type_prefix: str = "application/fhir+json"


@dataclass
class NationalSandboxProbeResult:
    """Deterministic result of a national sandbox contract probe."""

    sandbox_key: str
    jurisdiction: str
    endpoint_url: str
    passed: bool
    status: str  # "PASS", "CONTRACT_VIOLATION", "REACHABILITY_FAILED"
    http_status: int | None = None
    resource_type: str | None = None
    missing_headers: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_key": self.sandbox_key,
            "jurisdiction": self.jurisdiction,
            "endpoint_url": self.endpoint_url,
            "passed": self.passed,
            "status": self.status,
            "http_status": self.http_status,
            "resource_type": self.resource_type,
            "missing_headers": list(self.missing_headers),
            "violations": list(self.violations),
        }


NATIONAL_SANDBOX_SPECS: dict[str, NationalSandboxContractSpec] = {
    "nhs_pds": NationalSandboxContractSpec(
        sandbox_key="nhs_pds",
        jurisdiction="UK",
        display_name="NHS Personal Demographics Service (PDS FHIR R4)",
        probe_method="GET",
        probe_path="/personal-demographics/FHIR/R4/Patient/9000000009",
        required_request_headers=("Authorization", "X-Request-ID", "X-Correlation-ID"),
        expected_status_codes=(200,),
        expected_resource_types=("Patient",),
    ),
    "nhs_eps": NationalSandboxContractSpec(
        sandbox_key="nhs_eps",
        jurisdiction="UK",
        display_name="NHS Electronic Prescription Service (EPS FHIR R4)",
        probe_method="GET",
        probe_path="/electronic-prescriptions/FHIR/R4/metadata",
        required_request_headers=("Authorization", "X-Request-ID", "NHSD-Session-URID"),
        expected_status_codes=(200,),
        expected_resource_types=("CapabilityStatement",),
    ),
    "nhs_ers": NationalSandboxContractSpec(
        sandbox_key="nhs_ers",
        jurisdiction="UK",
        display_name="NHS e-Referral Service (e-RS FHIR R4)",
        probe_method="GET",
        probe_path="/referrals/FHIR/R4/metadata",
        required_request_headers=("Authorization", "X-Correlation-ID", "NHSD-End-User-Organisation-ODS"),
        expected_status_codes=(200,),
        expected_resource_types=("CapabilityStatement",),
    ),
    "nhs_gp_connect": NationalSandboxContractSpec(
        sandbox_key="nhs_gp_connect",
        jurisdiction="UK",
        display_name="NHS GP Connect Access Record Structured (FHIR)",
        probe_method="GET",
        probe_path="/gpconnect/fhir/metadata",
        required_request_headers=("Authorization", "Ssp-TraceID", "Ssp-From", "Ssp-To", "Ssp-InteractionID"),
        expected_status_codes=(200,),
        expected_resource_types=("CapabilityStatement",),
    ),
    "nhs_mesh": NationalSandboxContractSpec(
        sandbox_key="nhs_mesh",
        jurisdiction="UK",
        display_name="NHS Message Exchange for Social Care and Health (MESH)",
        probe_method="GET",
        probe_path="/messageexchange/endpointlookup/mesh",
        required_request_headers=("Authorization", "Mex-ClientVersion", "Mex-OSName"),
        expected_status_codes=(200,),
        expected_resource_types=(),
        content_type_prefix="application/json",
    ),
    "kenya_khis": NationalSandboxContractSpec(
        sandbox_key="kenya_khis",
        jurisdiction="KE",
        display_name="Kenya Health Information System / DHA Interoperability Layer",
        probe_method="GET",
        probe_path="/fhir/metadata",
        required_request_headers=("Authorization", "X-Correlation-ID", "X-DHA-Facility-Code"),
        expected_status_codes=(200,),
        expected_resource_types=("CapabilityStatement",),
    ),
    "kenya_sha": NationalSandboxContractSpec(
        sandbox_key="kenya_sha",
        jurisdiction="KE",
        display_name="Kenya Social Health Authority (SHA / SHIF) Claims Sandbox",
        probe_method="GET",
        probe_path="/fhir/metadata",
        required_request_headers=("Authorization", "X-Correlation-ID", "X-SHA-Partner-ID"),
        expected_status_codes=(200,),
        expected_resource_types=("CapabilityStatement",),
    ),
}


def get_national_sandbox_spec(sandbox_key: str) -> NationalSandboxContractSpec:
    """Resolve a NationalSandboxContractSpec by key or raise KeyError."""
    key = (sandbox_key or "").strip().lower()
    if key not in NATIONAL_SANDBOX_SPECS:
        raise KeyError(
            f"Unknown national sandbox key {sandbox_key!r}; expected one of {sorted(NATIONAL_SANDBOX_SPECS)}"
        )
    return NATIONAL_SANDBOX_SPECS[key]


def validate_national_sandbox_headers(
    sandbox_key: str,
    headers: dict[str, str],
) -> list[str]:
    """Return list of missing or blank required headers for the given national sandbox."""
    spec = get_national_sandbox_spec(sandbox_key)
    lower_map = {k.lower(): str(v).strip() for k, v in (headers or {}).items()}
    missing: list[str] = []
    for req_hdr in spec.required_request_headers:
        val = lower_map.get(req_hdr.lower(), "")
        if not val:
            missing.append(req_hdr)
    return missing


def validate_national_sandbox_response(
    sandbox_key: str,
    status_code: int,
    headers: dict[str, str],
    body: dict[str, Any] | str | None,
) -> list[str]:
    """Validate an HTTP response from a national sandbox against its contract spec."""
    spec = get_national_sandbox_spec(sandbox_key)
    violations: list[str] = []

    if status_code not in spec.expected_status_codes:
        violations.append(
            f"HTTP status {status_code} not in expected {list(spec.expected_status_codes)}"
        )

    lower_headers = {k.lower(): str(v) for k, v in (headers or {}).items()}
    ctype = lower_headers.get("content-type", "")
    if spec.content_type_prefix and ctype:
        allowed_prefixes = {spec.content_type_prefix.lower(), "application/json"}
        if not any(ctype.lower().startswith(p) for p in allowed_prefixes):
            violations.append(
                f"Content-Type {ctype!r} does not match expected prefix {spec.content_type_prefix!r}"
            )

    if spec.expected_resource_types:
        if not isinstance(body, dict):
            violations.append("Response body is not a parsed JSON object")
        else:
            rtype = str(body.get("resourceType") or "")
            if rtype not in spec.expected_resource_types:
                violations.append(
                    f"FHIR resourceType {rtype!r} not in expected {list(spec.expected_resource_types)}"
                )

    return violations


async def probe_national_sandbox(
    sandbox_key: str,
    base_url: str,
    headers: dict[str, str],
    timeout: float = 10.0,
) -> NationalSandboxProbeResult:
    """Execute a live, fail-closed contract probe against a national sandbox endpoint.

    Never fabricates a synthetic response when the endpoint is unreachable or
    misconfigured.
    """
    spec = get_national_sandbox_spec(sandbox_key)
    cleaned_base = (base_url or "").strip().rstrip("/")
    parsed = urlparse(cleaned_base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return NationalSandboxProbeResult(
            sandbox_key=spec.sandbox_key,
            jurisdiction=spec.jurisdiction,
            endpoint_url=cleaned_base,
            passed=False,
            status="CONTRACT_VIOLATION",
            violations=[f"Invalid base_url {base_url!r}: must include http/https scheme and hostname"],
        )

    endpoint_url = f"{cleaned_base}{spec.probe_path}"
    missing_headers = validate_national_sandbox_headers(spec.sandbox_key, headers)
    if missing_headers:
        return NationalSandboxProbeResult(
            sandbox_key=spec.sandbox_key,
            jurisdiction=spec.jurisdiction,
            endpoint_url=endpoint_url,
            passed=False,
            status="CONTRACT_VIOLATION",
            missing_headers=missing_headers,
            violations=[f"Missing required request headers: {', '.join(missing_headers)}"],
        )

    req_headers = {"Accept": spec.content_type_prefix, **headers}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(spec.probe_method, endpoint_url, headers=req_headers)
    except Exception as exc:
        return NationalSandboxProbeResult(
            sandbox_key=spec.sandbox_key,
            jurisdiction=spec.jurisdiction,
            endpoint_url=endpoint_url,
            passed=False,
            status="REACHABILITY_FAILED",
            violations=[f"Sandbox endpoint unreachable ({type(exc).__name__}): {exc}"],
        )

    parsed_body: dict[str, Any] | str | None = None
    try:
        parsed_body = resp.json()
    except Exception:
        parsed_body = resp.text

    resp_violations = validate_national_sandbox_response(
        spec.sandbox_key,
        resp.status_code,
        dict(resp.headers),
        parsed_body,
    )
    rtype = parsed_body.get("resourceType") if isinstance(parsed_body, dict) else None
    passed = len(resp_violations) == 0
    return NationalSandboxProbeResult(
        sandbox_key=spec.sandbox_key,
        jurisdiction=spec.jurisdiction,
        endpoint_url=endpoint_url,
        passed=passed,
        status="PASS" if passed else "CONTRACT_VIOLATION",
        http_status=resp.status_code,
        resource_type=rtype,
        violations=resp_violations,
    )
