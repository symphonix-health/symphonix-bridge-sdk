"""Tests for GHARRA registration payloads (Workstream 1c, FR-AEC-002).

Two layers, no mocks:

- Pure-shape tests run under any interpreter (root venv).
- ``test_payload_validates_against_real_gharra_agentrecord`` imports GHARRA's
  REAL ``AgentRecord`` model and constructs it from the builder output. It is
  skipped only if GHARRA's package is not importable in the current
  interpreter (it needs GHARRA's own venv for the ``ulid`` dependency); when it
  runs it is a genuine cross-repo contract check, not a stub.
"""

from __future__ import annotations

import importlib.util

import pytest

from bridge_sdk.agent_contract import reference_manifest
from bridge_sdk.gharra_registration import (
    GHARRA_PROTOCOL_REST,
    build_capabilities_payload,
    build_registration_payload,
)

_GHARRA_AVAILABLE = importlib.util.find_spec("gharra") is not None
TRIAGE_API_BASE_URL = "http://127.0.0.1:8400/triage-api"


def test_capabilities_payload_carries_intents_as_protocols() -> None:
    m = reference_manifest("lis")
    caps = build_capabilities_payload(m)
    assert set(caps["protocols"]) == {"lab.order", "result.retrieve"}
    assert caps["custom"]["intents"] == m.intent_names()
    assert caps["custom"]["safety_classes"]["lab.order"] == "sensitive"


def test_registration_payload_minimal_shape() -> None:
    m = reference_manifest("triage-api")
    payload = build_registration_payload(m, base_url=f"{TRIAGE_API_BASE_URL}/")
    assert payload["display_name"] == "triage-api"
    assert payload["jurisdiction"] == "GB"
    assert payload["capabilities"]["protocols"] == ["triage.start"]
    assert len(payload["endpoints"]) == 1
    ep = payload["endpoints"][0]
    assert ep["protocol"] == GHARRA_PROTOCOL_REST  # http-rest, not "rest"
    assert ep["url"] == TRIAGE_API_BASE_URL  # trailing slash stripped
    assert ep["agent_card_url"].endswith("/.well-known/agent-card.json")


def test_protocol_value_is_a_real_gharra_enum_member() -> None:
    # Guards against regressing to an invalid value like "rest"/"api".
    assert GHARRA_PROTOCOL_REST == "http-rest"


@pytest.mark.skipif(
    not _GHARRA_AVAILABLE,
    reason="GHARRA package not importable in this interpreter (needs GHARRA venv)",
)
def test_payload_validates_against_real_gharra_agentrecord() -> None:
    # FR-AEC-002: the registration body validates against GHARRA's REAL model.
    from gharra.core.models import AgentRecord  # type: ignore

    m = reference_manifest("triage-api")
    payload = build_registration_payload(m, base_url=TRIAGE_API_BASE_URL)
    record = AgentRecord.model_validate(payload)
    assert record.display_name == "triage-api"
    assert "triage.start" in record.capabilities.protocols
    assert record.endpoints[0].agent_card_url.endswith("/.well-known/agent-card.json")
