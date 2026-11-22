"""Tests for default-off DecisionPort shadow mode in `symphonix-bridge-sdk` (DF4, DF5)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any

import pytest

from bridge_sdk import decision_port_shadow as shadow_mod
from bridge_sdk.conductor_coordination import ConductorCoordinator
from bridge_sdk.durable_agent import DurableLedgerAdapter
from bridge_sdk.system1_reflex import Tier0SafetyFloor


class _StubHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        opts = list(body["questions"]["decision"]["criteria"].keys())
        chosen = opts[0]
        probs = {k: (0.95 if k == chosen else 0.05 / max(1, len(opts) - 1)) for k in opts}
        raw = json.dumps(
            {
                "answers": {
                    "decision": {
                        "type": "choice",
                        "choice": chosen,
                        "probabilities": probs,
                        "confidence": probs[chosen],
                    }
                },
                "weights_hash": "sha256-bridge-test",
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: Any) -> None:
        return


def test_bridge_shadow_default_off_and_enabled_loopback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SYMPHONIX_DECISION_PORT_SHADOW_ENABLED", raising=False)
    monkeypatch.delenv("SYMPHONIX_DECISION_PORT_SHADOW_DF4", raising=False)
    monkeypatch.delenv("SYMPHONIX_DECISION_PORT_SHADOW_DF5", raising=False)
    log_file = tmp_path / "bridge_shadow.jsonl"
    monkeypatch.setenv("SYMPHONIX_DECISION_PORT_SHADOW_LOG", str(log_file))

    r_off = Tier0SafetyFloor.evaluate(
        proposed_medications=["amoxicillin"], allergies=["penicillin"]
    )
    assert r_off.blocked is True
    assert not log_file.exists()

    coord = ConductorCoordinator(DurableLedgerAdapter(tmp_path / "conductor.db"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        monkeypatch.setenv("SYMPHONIX_DECISION_PORT_SHADOW_ENABLED", "1")
        monkeypatch.setenv("SYMPHONIX_DECISION_PORT_SHADOW_DF4", "1")
        monkeypatch.setenv("SYMPHONIX_DECISION_PORT_SHADOW_DF5", "1")
        monkeypatch.setenv("SYMPHONIX_DECISION_PORT_S1_URL", f"http://127.0.0.1:{port}")

        r_df4 = Tier0SafetyFloor.evaluate(
            proposed_medications=["amoxicillin"], allergies=["penicillin"]
        )
        assert r_df4.blocked is True

        comp, _ = coord.admit_skill_and_tool(
            skill_id="baseline-governed-agent",
            intent="epr.encounter.read",
            payload={"patient": "Patient/9434765919"},
        )
        assert comp

        rows = [json.loads(x) for x in log_file.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert [r["decision_family"] for r in rows] == ["DF4", "DF5"]
        assert all(set(shadow_mod.REQUIRED_AUDIT_FIELDS).issubset(r.keys()) for r in rows)
    finally:
        srv.shutdown()
        srv.server_close()


def test_bridge_no_hazard_downgrade_and_non_loopback() -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        shadow_mod.validate_loopback_url("http://192.168.1.10:18434")

    tier, final_dec, pred_sc = shadow_mod.enforce_no_hazard_downgrade(
        family="DF5",
        risk_class="C",
        s1_sc_flag=True,
        s2_decision="complete_valid_routine_file",
        s2_sc_flag=False,
        s2_confidence=0.98,
    )
    assert tier == "HUMAN_ESCALATED"
    assert final_dec is None
    assert pred_sc is True
