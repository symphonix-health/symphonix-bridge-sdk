"""GHARRA discovery client — resolves agents by capability for bridge routing.

Fixes: G7 (trust), G8 (unified client), G10 (priority/weight ranking),
       G14 (fallback cache), G15 (correlation propagation).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ResolvedEndpoint:
    """Fully resolved endpoint with metadata — not just a URL string."""

    def __init__(self, raw: dict[str, Any]):
        self.url: str = raw.get("url", "")
        self.protocol: str = raw.get("protocol", "")
        self.region: str = raw.get("region", "")
        self.priority: int = raw.get("priority", 100)
        self.weight: int = raw.get("weight", 100)
        self.health_url: str = raw.get("health_url", "")
        bp = raw.get("backpressure") or {}
        self.max_concurrency: int = bp.get("max_concurrency", 0)
        self.rate_limit_rps: int = bp.get("rate_limit_rps", 0)

    def __repr__(self) -> str:
        return (
            f"ResolvedEndpoint({self.url}, proto={self.protocol}, pri={self.priority})"
        )


class DiscoveryResult:
    """Structured discovery result with agent info, selected endpoint, trust, and alternatives."""

    def __init__(
        self,
        agent: dict[str, Any],
        endpoint: ResolvedEndpoint,
        alternatives: list[ResolvedEndpoint],
        trust: dict[str, Any],
        policy_tags: dict[str, Any],
    ):
        self.agent = agent
        self.agent_id: str = agent.get("agent_id", "")
        self.endpoint = endpoint
        self.alternatives = alternatives
        self.trust = trust
        self.policy_tags = policy_tags

    @property
    def url(self) -> str:
        return self.endpoint.url

    @property
    def phi_allowed(self) -> bool:
        return self.policy_tags.get("phi_allowed", False)

    @property
    def residency(self) -> list[str]:
        return self.policy_tags.get("residency", [])

    @property
    def mtls_required(self) -> bool:
        return self.trust.get("mtls_required", False)


def select_endpoint(
    endpoints: list[dict[str, Any]],
    preferred_protocol: str | None = None,
    preferred_region: str | None = None,
) -> tuple[ResolvedEndpoint | None, list[ResolvedEndpoint]]:
    """Pick best endpoint by (priority ASC, weight DESC), with optional protocol/region preference.

    Returns (primary, alternatives).
    """
    if not endpoints:
        return None, []

    resolved = [ResolvedEndpoint(ep) for ep in endpoints]

    # Filter by preferred protocol/region if specified
    if preferred_protocol:
        filtered = [ep for ep in resolved if ep.protocol == preferred_protocol]
        if filtered:
            resolved = filtered
    if preferred_region:
        filtered = [ep for ep in resolved if ep.region == preferred_region]
        if filtered:
            resolved = filtered

    # Sort by priority ASC (lower = better), then weight DESC (higher = better)
    resolved.sort(key=lambda ep: (ep.priority, -ep.weight))
    return resolved[0], resolved[1:]


class GharraDiscoveryClient:
    """Client for GHARRA agent discovery and routing.

    Works with any GHARRA instance — not BulletTrain-specific.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8400",
        api_key: str | None = None,
        timeout: float = 10.0,
        cache_ttl: float = 300.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._cache: dict[str, tuple[float, Any]] = {}  # (expiry, data)
        self._cache_ttl = cache_ttl
        # G14: Fallback cache — persists beyond TTL when GHARRA is unreachable
        self._fallback_cache: dict[str, Any] = {}

    def _headers(self, correlation_id: str = "") -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        # G15: Propagate correlation_id to GHARRA
        if correlation_id:
            h["X-Correlation-ID"] = correlation_id
        return h

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/health", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def discover(
        self,
        capability: str,
        jurisdiction: str | None = None,
        protocol: str | None = None,
        limit: int = 10,
        correlation_id: str = "",
    ) -> list[dict[str, Any]]:
        """Discover agents by capability. Returns full agent records sorted by priority."""
        cache_key = f"discover:{capability}:{jurisdiction}:{protocol}:{limit}"
        cached = self._cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        params: dict[str, Any] = {"capability": capability, "limit": limit}
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        if protocol:
            params["protocol"] = protocol

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/discover",
                    params=params,
                    headers=self._headers(correlation_id),
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])

            # G10: Sort by endpoint priority/weight
            for agent in results:
                endpoints = agent.get("endpoints", [])
                endpoints.sort(
                    key=lambda ep: (ep.get("priority", 100), -ep.get("weight", 100))
                )

            self._cache[cache_key] = (time.monotonic() + self._cache_ttl, results)
            self._fallback_cache[cache_key] = results  # G14: persist for fallback
            return results

        except Exception as e:
            logger.warning("GHARRA discovery failed: %s — checking fallback cache", e)
            # G14: Return stale fallback if available
            fallback = self._fallback_cache.get(cache_key)
            if fallback:
                logger.info(
                    "Returning %d stale agents from fallback cache", len(fallback)
                )
                return fallback
            raise

    async def discover_and_resolve(
        self,
        capability: str,
        jurisdiction: str | None = None,
        preferred_protocol: str | None = None,
        preferred_region: str | None = None,
        correlation_id: str = "",
        purpose_of_use: str = "treatment",
    ) -> DiscoveryResult | None:
        """Discover + route + trust in one call. Returns fully resolved endpoint."""
        agents = await self.discover(
            capability=capability,
            jurisdiction=jurisdiction,
            protocol=preferred_protocol,
            correlation_id=correlation_id,
        )
        if not agents:
            return None

        agent = agents[0]
        endpoints = agent.get("endpoints", [])
        primary, alternatives = select_endpoint(
            endpoints, preferred_protocol, preferred_region
        )
        if not primary:
            return None

        # G7: Fetch trust bundle
        trust = agent.get("trust", {})
        agent_id = agent.get("agent_id", "")
        if agent_id:
            route_info: dict[str, Any] = {}
            direct_trust: dict[str, Any] = {}
            route_result, bundle_result = await asyncio.gather(
                self.route(agent_id, purpose_of_use, correlation_id),
                self.get_trust_bundle(agent_id),
                return_exceptions=True,
            )

            if isinstance(route_result, Exception):
                logger.debug("Route advisory failed for %s: %s", agent_id, route_result)
            elif isinstance(route_result, dict):
                route_info = route_result

            if isinstance(bundle_result, Exception):
                logger.debug(
                    "Trust bundle fetch failed for %s: %s", agent_id, bundle_result
                )
            elif isinstance(bundle_result, dict):
                direct_trust = bundle_result.get("trust_bundle", bundle_result)

            route_trust = route_info.get("trust_bundle", {})
            if direct_trust or route_trust:
                trust = {**trust, **direct_trust, **route_trust}

        policy_tags = agent.get("policy_tags", {})

        return DiscoveryResult(
            agent=agent,
            endpoint=primary,
            alternatives=alternatives,
            trust=trust,
            policy_tags=policy_tags,
        )

    async def route(
        self,
        agent_id: str,
        purpose_of_use: str = "treatment",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/route",
                json={"agent_id": agent_id, "purpose_of_use": purpose_of_use},
                headers=self._headers(correlation_id),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/v1/agents/{agent_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def register_agent(self, agent_card: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/agents",
                json=agent_card,
                headers={**self._headers(), "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_trust_bundle(self, agent_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/v1/trust/bundles/{agent_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
