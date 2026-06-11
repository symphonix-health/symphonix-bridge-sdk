"""Build GHARRA registration payloads from an AgentActionManifest (FR-AEC-002).

Workstream 1c. Turns a component's :class:`AgentActionManifest` into the JSON
body GHARRA's ``POST /v1/agents`` accepts, and the ``/.well-known/agent-card.json``
body a component serves. The payload is shaped to validate against GHARRA's real
``gharra.core.models.AgentRecord`` / ``Capabilities`` / ``Endpoint`` models, so
discovery (``GET /v1/discover?capability=<intent>``) resolves the owning service
and routing returns its endpoint.

Pure and dependency-light (no GHARRA import) so it is testable in any venv; the
no-mock contract test in symphonix-bridge-sdk/tests feeds the output straight
into GHARRA's real ``AgentRecord`` model under GHARRA's own interpreter.

GHARRA facts this module encodes (verified against the live models):

- ``Protocol`` enum values are ``http-rest``, ``nexus-a2a-jsonrpc``,
  ``bullettrain-external``, ``fhir-r4``, ``grpc`` (NOT ``rest``/``api``).
- ``AgentRecord`` requires a non-empty ``endpoints`` list.
- Discovery filters on ``Capabilities.protocols`` (a list of capability
  strings); unrecognised keys fold into ``Capabilities.custom``.
"""

from __future__ import annotations

from typing import Any

from .agent_contract import AgentActionManifest

__all__ = [
    "GHARRA_PROTOCOL_REST",
    "build_capabilities_payload",
    "build_registration_payload",
]

# GHARRA Protocol enum value for a typed REST domain API (verified on disk).
GHARRA_PROTOCOL_REST = "http-rest"


def build_capabilities_payload(manifest: AgentActionManifest) -> dict[str, Any]:
    """Build the GHARRA ``Capabilities`` body for a manifest.

    Intents become discovery ``protocols`` (the field GHARRA filters on), and
    per-intent safety classes plus the manifest version fold into ``custom`` so
    no information is lost while staying within the validated schema.
    """
    return {
        "protocols": manifest.capabilities(),
        "fhir_r4": True,
        "custom": {
            "agent_execution_contract_version": manifest.version,
            "intents": manifest.intent_names(),
            "safety_classes": {
                i.intent: i.safety_class.value for i in manifest.intents
            },
        },
    }


def build_registration_payload(
    manifest: AgentActionManifest,
    *,
    base_url: str,
    jurisdiction: str = "GB",
) -> dict[str, Any]:
    """Build the GHARRA ``POST /v1/agents`` body for a component's manifest.

    The returned dict validates against ``gharra.core.models.AgentRecord``:
    a ``display_name``, a ``jurisdiction``, a ``capabilities`` block whose
    ``protocols`` carry the intents discovery filters on, and a non-empty
    ``endpoints`` list whose ``agent_card_url`` points at the well-known card.
    """
    base = base_url.rstrip("/")
    return {
        "display_name": manifest.component,
        "jurisdiction": jurisdiction,
        "description": (
            f"Agent Execution Contract surface for {manifest.component} "
            f"({len(manifest.intents)} typed intents)"
        ),
        "capabilities": build_capabilities_payload(manifest),
        "endpoints": [
            {
                "url": base,
                "protocol": GHARRA_PROTOCOL_REST,
                "agent_card_url": f"{base}/.well-known/agent-card.json",
                "priority": 100,
                "weight": 100,
            }
        ],
    }
