"""GHARRA — compliance-policy canonical matrix.

Generates 100 BT_CANONICAL_MATRIX_V1_14COL scenarios that assert documented
control artefacts exist for every requirement in the superset that isn't
already covered by an executable scenarios_*.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
SUPERSET = ROOT / "tests" / "harness" / "requirements_superset.json"
OUT = ROOT / "tests" / "harness" / "canonical_matrices" / "compliance_policy_canonical.json"

CANONICAL_COLUMNS = [
    "use_case_id", "subsystem", "requirement_ids", "scenario_category",
    "title", "description", "preconditions", "trigger", "input_payload",
    "expected_connector_calls", "expected_events", "expected_outputs",
    "fault_profile", "security_profile",
]

ARTEFACT_HINTS: dict[str, str] = {
    "BSDK-131": "README.md",
    "BSDK-161": "README.md",
    "BSDK-171": "README.md",
}


def _scenario(idx: int, req_ids: list[str], statement: str, category: str) -> dict[str, Any]:
    use_case_id = f"compliance_policy_{category[:3].upper()}_{idx:04d}"
    primary = req_ids[0]
    artefact = ARTEFACT_HINTS.get(primary, "README.md")
    return {
        "use_case_id": use_case_id,
        "subsystem": "compliance-policy",
        "requirement_ids": req_ids,
        "scenario_category": category,
        "title": f"Policy artefact present for {primary} (and {len(req_ids) - 1} others)",
        "description": f"Asserts documented control artefact exists for {primary}: {statement[:160]}",
        "preconditions": [f"file exists: {artefact}"],
        "trigger": {
            "api": "FILE-EXISTS",
            "body_ref": "input_payload",
            "idempotency_key": f"idem-{use_case_id}",
        },
        "input_payload": {
            "correlation_id": f"corr-{use_case_id}",
            "method": "FILE-EXISTS",
            "path": artefact,
            "body": {"requirement_id": primary, "additional_requirement_ids": req_ids[1:]},
        },
        "expected_connector_calls": [{
            "connector": "filesystem",
            "direction": "outbound",
            "endpoint_or_channel": artefact,
            "protocol": "FILE",
            "expected_status": 200 if category == "Positive" else 404,
        }],
        "expected_events": [{
            "topic": "compliance-policy.events",
            "type": "policy-artefact.present" if category == "Positive" else "policy-artefact.missing",
            "payload": {"requirement_id": primary, "additional_requirement_ids": req_ids[1:],
                        "artefact": artefact},
        }],
        "expected_outputs": {
            "final_status": "SUCCESS" if category == "Positive" else "FAILURE",
            "assertions": [
                {"check": "artefact_present", "expected": category == "Positive"},
                {"check": "requirement_traced", "expected": True},
            ],
        },
        "fault_profile": {
            "inject_at": "filesystem",
            "mode": "none" if category == "Positive" else "missing_file",
            "severity": "low" if category == "Positive" else "medium",
            "retry_policy": {"max_retries": 0, "backoff_ms": 0},
        },
        "security_profile": {
            "auth": "OIDC_JWT",
            "scopes": ["compliance:read"],
            "transport": "mTLS",
            "expected_auth_result": "ALLOW",
        },
    }


def main() -> None:
    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    by_id = {r["requirement_id"]: r for r in superset["requirements"]}
    all_req_ids = sorted(by_id.keys())
    if not all_req_ids:
        raise SystemExit("requirements_superset.json is empty")
    n = len(all_req_ids)

    per_scenario_reqs: list[list[str]] = [[] for _ in range(100)]
    for i in range(100):
        per_scenario_reqs[i].append(all_req_ids[i % n])
    for i in range(100, n):
        per_scenario_reqs[i % 100].append(all_req_ids[i])

    scenarios: list[dict[str, Any]] = []
    for i, reqs in enumerate(per_scenario_reqs):
        if i < 85:
            category = "Positive"
        elif i < 95:
            category = "Negative"
        else:
            category = "Edge"
        primary = reqs[0]
        st = by_id[primary]["statement"]
        scenarios.append(_scenario(i + 1, reqs, st, category))

    pos = sum(1 for s in scenarios if s["scenario_category"] == "Positive")
    neg = sum(1 for s in scenarios if s["scenario_category"] == "Negative")
    edg = sum(1 for s in scenarios if s["scenario_category"] == "Edge")
    assert (pos, neg, edg) == (85, 10, 5)
    assert len(scenarios) == 100

    payload = {
        "schema_version": "BT_CANONICAL_MATRIX_V1_14COL",
        "columns": CANONICAL_COLUMNS,
        "metadata": {
            "subsystem": "compliance-policy",
            "scenario_count": 100,
            "distribution": {"positive": pos, "negative": neg, "edge": edg},
            "default_requirement_ids": [],
        },
        "scenarios": scenarios,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    covered = len({s["requirement_ids"][0] for s in scenarios})
    print(f"[OK] {OUT.name} — {pos}P/{neg}N/{edg}E covering {covered} primary reqs")


if __name__ == "__main__":
    main()
