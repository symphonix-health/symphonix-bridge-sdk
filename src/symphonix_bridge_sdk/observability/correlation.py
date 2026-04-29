"""Request correlation ID context and ASGI middleware."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Return the current request correlation ID, if one has been set."""

    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the current correlation ID for non-HTTP workflows such as agents."""

    _correlation_id.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagate `X-Correlation-ID` on inbound and outbound HTTP messages."""

    HEADER = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get(self.HEADER) or str(uuid.uuid4())
        token = _correlation_id.set(cid)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(token)
        response.headers[self.HEADER] = cid
        return response

