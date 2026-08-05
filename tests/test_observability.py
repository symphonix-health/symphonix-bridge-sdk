import importlib
import json
import logging
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

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


def test_observability_import_emits_deprecation_warning():
    """Importing symphonix_bridge_sdk.observability must emit a DeprecationWarning."""
    # Reload the module to trigger the warning again (it may already be cached).
    mod = sys.modules.get("symphonix_bridge_sdk.observability")
    if mod is not None:
        del sys.modules["symphonix_bridge_sdk.observability"]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("symphonix_bridge_sdk.observability")

    deprecation_warnings = [
        w for w in caught if issubclass(w.category, DeprecationWarning)
        and "observability" in str(w.message).lower()
    ]
    assert deprecation_warnings, (
        "Expected a DeprecationWarning about the observability extra, got none"
    )
    assert "observability" in str(deprecation_warnings[0].message).lower()


def test_observability_import_error_when_stack_missing(tmp_path):
    """When the OTEL/Sentry stack is absent, importing observability raises ImportError.

    The absence is real, not mocked: the guard runs inside a child interpreter
    started with ``-I -S``, so site-packages is genuinely off ``sys.path`` and
    the stack is genuinely unimportable.  The module is executed straight from
    its own file under a dotless name because the parent package pulls in
    pydantic, which ``-S`` also removes; the guard is name-independent, so this
    exercises the real code path with the real ``importlib.util.find_spec``.

    Patching ``find_spec`` (the previous approach) made it *return None* where
    reality *raises* ModuleNotFoundError, so it asserted a branch that could
    never be reached in production.
    """
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "symphonix_bridge_sdk"
        / "observability"
        / "__init__.py"
    )
    probe = tmp_path / "probe_missing_observability_stack.py"
    probe.write_text(
        textwrap.dedent(
            f"""
            import importlib.util
            import sys

            # Known-true control: prove the interpreter really is stack-free,
            # so a broken isolation surfaces as a failure, not a false pass.
            for _name in ("opentelemetry", "sentry_sdk", "prometheus_client"):
                if importlib.util.find_spec(_name) is not None:
                    print("NOT_ISOLATED:" + _name)
                    sys.exit(2)

            spec = importlib.util.spec_from_file_location(
                "observability_absent_stack_probe", r"{module_path}"
            )
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except ImportError as exc:
                print("IMPORT_ERROR:" + " ".join(str(exc).split()))
                sys.exit(0)
            print("NO_ERROR")
            sys.exit(1)
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-I", "-S", str(probe)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    stdout = result.stdout.strip()

    assert not stdout.startswith("NOT_ISOLATED"), (
        f"child interpreter was not stack-free, so the test proves nothing: {stdout}"
    )
    assert stdout.startswith("IMPORT_ERROR:"), (
        "Expected ImportError was not raised with the stack genuinely missing "
        f"(stdout={stdout!r}, stderr={result.stderr.strip()!r})"
    )
    message = stdout[len("IMPORT_ERROR:") :]
    assert "symphonix-bridge-sdk[observability]" in message, (
        "The guard must name the [observability] extra rather than surfacing a "
        f"bare ModuleNotFoundError; got: {message!r}"
    )
