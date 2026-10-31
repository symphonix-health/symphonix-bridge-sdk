"""Execute the dispatchable system1-reflex rows against the REAL bridge_sdk callables.

eps/vr-therapy (Option C) pattern, adapted for an SDK/library that boots no HTTP
app. symphonix-bridge-sdk mounts no ASGI route; its one genuinely
app-dispatchable surface is the System 1 Reflex Fabric's pure, deterministic
engine callables in the repo's own non-test code (``bridge_sdk.system1_reflex``).
This harness DISPATCHES each genuinely-single-shot-dispatchable system1-reflex
row into the REAL engine named by its ``body.engine``, on inputs FULLY determined
by the row body, and asserts the OBSERVED deterministic result reproduces a
committed expected snapshot.

Dispatchable = self-complete + determinate: a real callable into the repo's own
non-test code, every input it needs supplied by the row body, reproducing its
observed result on a FRESH call with no prior state, no network and no ordering
dependence. Three of the ten system1 engines qualify -- ``Tier0SafetyFloor``,
``ConsultationStateReflex`` and ``ReferralSatisficingReflex`` -- each a pure
static method fed entirely by the row's ``clinical_text`` / ``vitals`` /
``allergies`` / ``specialty``. The other seven engines need inputs the generic
row body does not carry: a hidden state vector (``CfCStateCell``), a timestamped
vital sample (``PhysiologicalTrajectoryReflex``), an HL7v2 payload
(``Hl7v2SemanticReflex``), a live local-SLM network endpoint
(``LocalSlmReflexAdapter``), prior calibration feedback
(``System1CalibrationTracker``), staffing census inputs unrelated to the body
(``StaffingSatisficingReflex``), or signal-action inputs
(``SignalBoxGovernanceBridge``). Those rows are left UNEXECUTED and counted
honestly in ``scenario_success_evidence.json`` -- they are NOT asserted against a
contrived call. The FILE-EXISTS compliance-policy and TRACEABILITY_LEDGER
seeded-alignment scenario families are descriptor-only (no app/callable surface)
and are not part of this runtime matrix.

caid's ``direct.scenario_app_harness`` gate remains RED by design (its managed set
is the full reduced + NFR matrices); this harness is an honest record of what IS
executed against real repo code, not an attempt to satisfy that gate.

Each row is its own pytest node on a fresh call. Set ``SYS1_RECORD=1`` to
re-derive the observed snapshot from a live run.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bridge_sdk.system1_reflex import (  # noqa: E402
    ConsultationStateReflex,
    ReferralSatisficingReflex,
    Tier0SafetyFloor,
)

MATRIX = ROOT / "tests" / "harness" / "json_matrices" / "system1-reflex_scenarios.json"
EVIDENCE_PATH = ROOT / "tests" / "harness" / "scenario_success_evidence.json"
EXPECTED_PATH = Path(__file__).with_name("scenario_execution_expected.json")
PYTEST_FILE = "tests/harness/test_matrix_scenario_execution.py"
PYTEST_FUNCTION = "test_system1_reflex_row_against_the_real_engine"

# Non-deterministic (wall-clock latency) result fields are dropped before the
# observed snapshot is taken -- they are timing, not behaviour.
_TIMING_KEY_FRAGMENTS = ("latency", "elapsed")
_FLOAT_PRECISION = 6


def _dispatch_tier0(body: dict[str, Any]) -> Any:
    return Tier0SafetyFloor.evaluate(
        vitals=body.get("vitals"),
        allergies=tuple(body.get("allergies") or ()),
        free_text_plan=body.get("clinical_text") or "",
    )


def _dispatch_consultation(body: dict[str, Any]) -> Any:
    return ConsultationStateReflex.evaluate(
        body.get("clinical_text") or "",
        vitals=body.get("vitals"),
        allergies=tuple(body.get("allergies") or ()),
    )


def _dispatch_referral(body: dict[str, Any]) -> Any:
    return ReferralSatisficingReflex.evaluate(
        clinical_text=body.get("clinical_text") or "",
        specialty_requested=body.get("specialty"),
        vitals=body.get("vitals"),
    )


# engine name (row body.engine) -> real callable fully determined by the row body.
DISPATCH: dict[str, Callable[[dict[str, Any]], Any]] = {
    "Tier0SafetyFloor": _dispatch_tier0,
    "ConsultationStateReflex": _dispatch_consultation,
    "ReferralSatisficingReflex": _dispatch_referral,
}

# Real source files the dispatched callables exercise (schema V1
# app_paths_exercised anchors; kept in lockstep with the evidence builder).
APP_PATHS_EXERCISED = (
    "src/bridge_sdk/__init__.py",
    "src/bridge_sdk/system1_reflex.py",
)


def _is_timing_key(key: str) -> bool:
    low = key.lower()
    return any(frag in low for frag in _TIMING_KEY_FRAGMENTS) or low.endswith("_ms")


def _canonical(obj: Any, *, _key: str | None = None) -> Any:
    """JSON-native, timing-free, float-rounded projection of a result value."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out: dict[str, Any] = {}
        for field in dataclasses.fields(obj):
            if _is_timing_key(field.name):
                continue
            out[field.name] = _canonical(getattr(obj, field.name), _key=field.name)
        return out
    if isinstance(obj, enum.Enum):
        return _canonical(obj.value)
    if isinstance(obj, dict):
        return {
            str(k): _canonical(v, _key=str(k))
            for k, v in obj.items()
            if not _is_timing_key(str(k))
        }
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, _FLOAT_PRECISION)
    return obj


def _load_rows() -> list[dict[str, Any]]:
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    return [r for r in payload.get("scenarios", []) if isinstance(r, dict)]


def _engine(row: dict[str, Any]) -> str:
    return str((row.get("input_payload") or {}).get("body", {}).get("engine", ""))


ROWS = _load_rows()
ROW_BY_ID = {str(r["use_case_id"]): r for r in ROWS}
EXECUTED_IDS = sorted(
    str(r["use_case_id"]) for r in ROWS if _engine(r) in DISPATCH
)
UNEXECUTED_IDS = sorted(
    str(r["use_case_id"]) for r in ROWS if _engine(r) not in DISPATCH
)

_RECORD = os.environ.get("SYS1_RECORD") == "1"


def _observe(uc: str) -> Any:
    row = ROW_BY_ID[uc]
    body = (row.get("input_payload") or {}).get("body") or {}
    result = DISPATCH[_engine(row)](body)
    return _canonical(result)


def _load_expected() -> dict[str, Any]:
    try:
        return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


EXPECTED = _load_expected()
_RECORDED: dict[str, Any] = {}


@pytest.mark.parametrize("uc", EXECUTED_IDS)
def test_system1_reflex_row_against_the_real_engine(uc: str) -> None:
    """Dispatch one dispatchable system1-reflex row into its REAL engine.

    The call is fully determined by the row body and deterministic on a fresh
    call; the OBSERVED canonical result must reproduce the committed snapshot.
    """
    observed = _observe(uc)
    if _RECORD:
        _RECORDED[uc] = observed
        return
    assert uc in EXPECTED, f"{uc} has no recorded expected snapshot (run SYS1_RECORD=1)"
    assert observed == EXPECTED[uc], (
        f"{uc} ({_engine(ROW_BY_ID[uc])}) observed result drifted from the "
        f"committed snapshot"
    )


def test_zz_write_recorded_snapshot() -> None:
    if not _RECORD:
        pytest.skip("not in record mode")
    EXPECTED_PATH.write_text(
        json.dumps(_RECORDED, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"[OK] recorded {len(_RECORDED)} observed snapshots to {EXPECTED_PATH}")


def test_dispatchable_set_is_nonempty_and_pure() -> None:
    """Guard: at least one row dispatches, and every dispatched engine is real."""
    assert EXECUTED_IDS, "no dispatchable system1-reflex rows -- harness is hollow"
    for uc in EXECUTED_IDS:
        assert _engine(ROW_BY_ID[uc]) in DISPATCH


def test_every_dispatchable_row_has_expected_snapshot() -> None:
    """Drift guard: the committed snapshot covers exactly the dispatchable rows."""
    if _RECORD:
        pytest.skip("record mode rewrites the snapshot")
    assert set(EXPECTED) == set(EXECUTED_IDS), (
        "expected-snapshot keys drifted from the dispatchable row set: "
        f"missing={sorted(set(EXECUTED_IDS) - set(EXPECTED))}, "
        f"stale={sorted(set(EXPECTED) - set(EXECUTED_IDS))}"
    )


def _load_evidence() -> dict[str, Any]:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_evidence_cites_exactly_executed_nodes() -> None:
    """The success evidence cites only this harness's executed, dispatchable nodes."""
    payload = _load_evidence()
    assert payload["schema_version"] == "SYMPHONIX_SCENARIO_SUCCESS_EVIDENCE_V1"
    assert payload["pytest_file"] == PYTEST_FILE
    assert payload["pytest_function"] == PYTEST_FUNCTION
    rows = payload["evidence"]
    cited = sorted(str(r["use_case_id"]) for r in rows)
    assert cited == EXECUTED_IDS
    for r in rows:
        assert r["expected_status"] == "passed"
        assert r["pytest_node_id"] == (
            f"{PYTEST_FILE}::{PYTEST_FUNCTION}[{r['use_case_id']}]"
        )
        exercised = r["app_paths_exercised"]
        assert isinstance(exercised, list) and exercised
        for app_path in exercised:
            assert (ROOT / app_path).exists(), f"anchor source missing: {app_path}"


def test_unexecuted_row_count_is_honest() -> None:
    """The evidence records the honest count of rows left unexecuted."""
    payload = _load_evidence()
    assert payload["executed_row_count"] == len(EXECUTED_IDS)
    assert payload["unexecuted_row_count"] == len(UNEXECUTED_IDS)
    assert sorted(payload["unexecuted_rows"]) == UNEXECUTED_IDS
    assert payload["executed_row_count"] + payload["unexecuted_row_count"] == len(ROWS)
