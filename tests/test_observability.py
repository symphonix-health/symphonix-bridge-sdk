import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from symphonix_bridge_sdk.observability import (
    AuditLogger,
    CorrelationIdMiddleware,
    make_health_router,
)
from symphonix_bridge_sdk.observability.sentry import _before_send


def test_correlation_id_middleware_preserves_inbound_header():
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/ping", headers={"X-Correlation-ID": "plan-123"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "plan-123"


def test_health_router_exposes_ops_endpoints():
    app = FastAPI()
    app.include_router(make_health_router("unit-service", "1.2.3"))
    client = TestClient(app)

    for path in ("/health", "/readiness", "/liveness"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "unit-service",
            "version": "1.2.3",
        }


def test_sentry_before_send_strips_phi_from_payload_sections():
    event = {
        "extra": {"patient_id": "p1", "safe": "value"},
        "contexts": {"request": {"email": "person@example.test", "path": "/x"}},
        "tags": {"nhs_number": "123", "team": "ops"},
    }

    scrubbed = _before_send(event, {})

    assert scrubbed["extra"] == {"safe": "value"}
    assert scrubbed["contexts"]["request"] == {"path": "/x"}
    assert scrubbed["tags"] == {"team": "ops"}


def test_audit_logger_emits_fhir_audit_event(caplog):
    caplog.set_level(logging.INFO, logger="audit")
    logger = AuditLogger("unit-service")

    logger.log(
        action="R",
        resource_type="Patient",
        resource_id="p-123",
        actor_id="clinician-1",
        details={"reason": "clinical_review"},
    )

    payload = json.loads(caplog.records[-1].message)
    assert payload["resourceType"] == "AuditEvent"
    assert payload["action"] == "R"
    assert payload["entity"][0]["what"]["reference"] == "Patient/p-123"
    assert payload["source"]["observer"]["display"] == "unit-service"
