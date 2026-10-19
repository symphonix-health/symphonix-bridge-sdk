"""Unit tests for National Sandbox Contract Probe (E-11) and fail-closed discovery."""

from __future__ import annotations

import pytest

from bridge_sdk.discovery import GharraDiscoveryClient
from bridge_sdk.national_sandbox_probe import (
    NATIONAL_SANDBOX_SPECS,
    get_national_sandbox_spec,
    probe_national_sandbox,
    validate_national_sandbox_headers,
    validate_national_sandbox_response,
)


@pytest.mark.unit
def test_national_sandbox_specs_catalog() -> None:
    expected = {
        "nhs_pds",
        "nhs_eps",
        "nhs_ers",
        "nhs_gp_connect",
        "nhs_mesh",
        "kenya_khis",
        "kenya_sha",
    }
    assert expected.issubset(set(NATIONAL_SANDBOX_SPECS.keys()))
    pds = get_national_sandbox_spec("nhs_pds")
    assert pds.jurisdiction == "UK"
    sha = get_national_sandbox_spec("kenya_sha")
    assert sha.jurisdiction == "KE"


@pytest.mark.unit
def test_validate_national_sandbox_headers_detects_missing() -> None:
    missing = validate_national_sandbox_headers(
        "nhs_gp_connect",
        {"Authorization": "Bearer tok", "Ssp-TraceID": "trace-1"},
    )
    assert "Ssp-From" in missing
    assert "Ssp-To" in missing
    assert "Ssp-InteractionID" in missing


@pytest.mark.unit
def test_validate_national_sandbox_response_checks_fhir_resource_type() -> None:
    ok = validate_national_sandbox_response(
        "nhs_pds",
        200,
        {"Content-Type": "application/fhir+json; charset=utf-8"},
        {"resourceType": "Patient", "id": "9000000009"},
    )
    assert ok == []

    bad = validate_national_sandbox_response(
        "nhs_pds",
        200,
        {"Content-Type": "application/fhir+json"},
        {"resourceType": "OperationOutcome"},
    )
    assert len(bad) == 1
    assert "Patient" in bad[0]


@pytest.mark.asyncio
async def test_probe_national_sandbox_fails_closed_on_missing_headers_or_unreachable() -> None:
    missing_hdr_res = await probe_national_sandbox(
        "kenya_sha",
        "https://sandbox.dha.go.ke",
        {"Authorization": "Bearer test-token"},
    )
    assert missing_hdr_res.passed is False
    assert missing_hdr_res.status == "CONTRACT_VIOLATION"
    assert "X-Correlation-ID" in missing_hdr_res.missing_headers

    unreachable_res = await probe_national_sandbox(
        "nhs_pds",
        "http://127.0.0.1:1",
        {
            "Authorization": "Bearer tok",
            "X-Request-ID": "req-1",
            "X-Correlation-ID": "corr-1",
        },
        timeout=0.2,
    )
    assert unreachable_res.passed is False
    assert unreachable_res.status == "REACHABILITY_FAILED"


@pytest.mark.asyncio
async def test_gharra_discovery_client_fails_closed_by_default() -> None:
    client = GharraDiscoveryClient(base_url="http://127.0.0.1:1", timeout=0.1)
    assert client.allow_stale_fallback is False
    client._fallback_cache["discover:clinical-triage:None:None:10"] = [{"agent_id": "stale"}]
    with pytest.raises(Exception):
        await client.discover("clinical-triage")
