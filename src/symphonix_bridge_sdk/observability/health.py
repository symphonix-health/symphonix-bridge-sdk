"""Standard operational health routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


def make_health_router(service_name: str, version: str = "unknown") -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["ops"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service=service_name, version=version)

    @router.get("/readiness", response_model=HealthResponse, tags=["ops"])
    async def readiness() -> HealthResponse:
        return HealthResponse(status="ok", service=service_name, version=version)

    @router.get("/liveness", response_model=HealthResponse, tags=["ops"])
    async def liveness() -> HealthResponse:
        return HealthResponse(status="ok", service=service_name, version=version)

    return router
