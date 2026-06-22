import asyncio

import pytest

from bridge_sdk.discovery import GharraDiscoveryClient


class CoordinatedDiscoveryClient(GharraDiscoveryClient):
    def __init__(self) -> None:
        super().__init__()
        self.route_started = asyncio.Event()
        self.trust_started = asyncio.Event()

    async def discover(
        self,
        capability: str,
        jurisdiction: str | None = None,
        protocol: str | None = None,
        limit: int = 10,
        correlation_id: str = "",
    ) -> list[dict]:
        return [
            {
                "agent_id": "agent-1",
                "trust": {"agent_card": "trusted"},
                "endpoints": [
                    {"url": "https://agent.example/fhir", "protocol": "fhir-r4"}
                ],
                "policy_tags": {"phi_allowed": True, "residency": ["GB"]},
            }
        ]

    async def route(
        self,
        agent_id: str,
        purpose_of_use: str = "treatment",
        correlation_id: str = "",
    ) -> dict:
        self.route_started.set()
        await asyncio.wait_for(self.trust_started.wait(), timeout=0.2)
        return {"trust_bundle": {"route_policy": purpose_of_use, "mtls_required": True}}

    async def get_trust_bundle(self, agent_id: str) -> dict:
        self.trust_started.set()
        await asyncio.wait_for(self.route_started.wait(), timeout=0.2)
        return {"direct_bundle": "present", "mtls_required": False}


@pytest.mark.asyncio
async def test_discover_and_resolve_fetches_route_and_trust_bundle_concurrently():
    client = CoordinatedDiscoveryClient()

    result = await asyncio.wait_for(
        client.discover_and_resolve(
            capability="diagnostic-report",
            preferred_protocol="fhir-r4",
            purpose_of_use="treatment",
        ),
        timeout=0.5,
    )

    assert result is not None
    assert result.url == "https://agent.example/fhir"
    assert result.trust["agent_card"] == "trusted"
    assert result.trust["direct_bundle"] == "present"
    assert result.trust["route_policy"] == "treatment"
    assert result.trust["mtls_required"] is True
