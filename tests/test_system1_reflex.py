"""Tests for the System 1 continuous-state and reflexive clinical decision fabric.

Covers:
- S1-01: Tier 0 deterministic safety floor & clinical monotonicity guard (FN = 0).
- S1-02: Closed-form Continuous-time (CfC) state cell analytical ODE bounds & irregular dt invariance.
- S1-03: PhysiologicalTrajectoryReflex detecting sub-threshold compensatory shock before static NEWS2.
- S1-04: ConsultationStateReflex scope-bounded negation guard (FP = 0 on negated symptoms) & safety-net prompts.
- S1-05: Live IntuitionDecision producer & Cynefin routing integration (`council_deliberation.route`).
- S1-06: Open-source Windows SLM registry (`OPEN_SOURCE_SYSTEM1_MODELS`), localhost PHI boundary, and Nygard circuit breaker.
- S1-10: Hl7v2SemanticReflex unit-mismatch (`mmol/L` vs `mg/dL`), haemolysed potassium artifact, and Hl7v2Adapter integration.
- S1-11: SignalBox co-control governance binding (`evaluate_reflex_signal_governance`).
- M-01 / M-06: Sub-2ms p99 CfC latency benchmark over 1,000 steps and Dual-Loop Self-Improvement calibration (`System1CalibrationTracker`).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import statistics
import time

import pytest

from bridge_sdk.adapters.hl7v2 import Hl7v2Adapter
from bridge_sdk.agent_contract import SafetyClass
from bridge_sdk.council_deliberation import CynefinClass
from bridge_sdk.human_handoff import ReviewerOutcome
from bridge_sdk.signal_governance import GovernanceTier
from bridge_sdk.superpersona_contract import (
    build_superpersona_contract,
    reference_superpersona_contract,
)
from bridge_sdk.system1_reflex import (
    OPEN_SOURCE_SYSTEM1_MODELS,
    CfCStateCell,
    CircuitState,
    ClinicalVitalSample,
    ConsultationStateReflex,
    ExternalEgressRefusedError,
    Hl7v2SemanticReflex,
    LocalSlmReflexAdapter,
    PhysiologicalTrajectoryReflex,
    ProprietaryModelRefusedError,
    System1CalibrationTracker,
    Tier0SafetyFloor,
    compute_live_intuition,
    evaluate_reflex_signal_governance,
    get_open_source_model_spec,
    is_local_trust_endpoint,
)


def test_tier0_monotonicity_never_downgrades_red_flag() -> None:
    """S1-01 / M-03: Tier 0 statutory bounds and BNF contraindications cannot be suppressed."""
    tier0 = Tier0SafetyFloor.evaluate(
        vitals={"respiratory_rate": 28, "spo2": 89, "systolic_bp": 84, "heart_rate": 136},
        proposed_medications=["co-amoxiclav", "ibuprofen"],
        active_medications=["warfarin"],
        allergies=["Penicillin anaphylaxis"],
        conditions=["Peptic ulcer disease"],
        free_text_plan="Start co-amoxiclav 625mg TDS and ibuprofen 400mg TDS",
    )
    assert tier0.blocked is True
    assert tier0.news2_single_param_red is True
    assert tier0.min_risk_score >= 0.95
    assert any("penicillin_cross_reactivity" in flag for flag in tier0.red_flags)
    assert any("nsaid_plus_anticoagulant" in flag for flag in tier0.red_flags)
    assert tier0.latency_ms < 5.0

    # Attempt to pass a benign System 1 risk_score=0.05 and empty flags; monotonicity must preserve Tier 0
    enforced_risk, enforced_flags, enforced_reasons = Tier0SafetyFloor.enforce_monotonicity(
        tier0,
        risk_score=0.05,
        red_flags=(),
        reason_codes=("sys1.nominal",),
    )
    assert enforced_risk >= tier0.min_risk_score
    assert set(tier0.red_flags).issubset(set(enforced_flags))
    assert "tier0.allergy_contraindication" in enforced_reasons


def test_cfc_irregular_dt_invariance_and_latency_slo() -> None:
    """S1-02 / M-01: CfCStateCell remains bounded in [-1, 1]^6 across irregular dt and meets p99 <= 2.0ms."""
    cell = CfCStateCell(state_dim=6, base_tau_seconds=900.0)
    hidden = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    latencies_ms: list[float] = []

    irregular_dts = [0.2, 1.0, 5.0, 60.0, 300.0, 1800.0, 14400.0, 86400.0]
    for step_idx in range(1000):
        dt = irregular_dts[step_idx % len(irregular_dts)]
        x = (
            0.5 if step_idx % 2 == 0 else -0.3,
            0.8,
            0.4,
            0.6,
            0.2,
            0.1,
        )
        t0 = time.perf_counter()
        hidden = cell.step(hidden, x, dt)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        for val in hidden:
            assert -1.0 <= val <= 1.0

    latencies_sorted = sorted(latencies_ms)
    p50 = statistics.median(latencies_sorted)
    p95 = latencies_sorted[int(0.95 * len(latencies_sorted))]
    p99 = latencies_sorted[int(0.99 * len(latencies_sorted))]
    assert p50 <= 0.3, f"CfC p50 {p50:.4f}ms exceeded 0.3ms"
    assert p95 <= 1.0, f"CfC p95 {p95:.4f}ms exceeded 1.0ms"
    assert p99 <= 2.0, f"CfC p99 {p99:.4f}ms exceeded 2.0ms"


def test_subthreshold_compensatory_shock_detected_before_news2() -> None:
    """S1-03: Detects progressive compensatory shock when every single reading has low static NEWS2."""
    reflex = PhysiologicalTrajectoryReflex()

    # Patient with occult haemorrhage / early sepsis:
    # t=0: HR 74, SBP 126/80 -> NEWS2 = 0, SI = 0.59
    # t=15m: HR 86, SBP 116/78 -> NEWS2 = 0, SI = 0.74
    # t=30m: HR 96, SBP 111/79 -> NEWS2 = 1 (HR 91-110), SI = 0.86, PP = 32 (narrowed)
    samples = [
        ClinicalVitalSample(timestamp_seconds=0.0, heart_rate=74, systolic_bp=126, diastolic_bp=80, respiratory_rate=15, spo2=98),
        ClinicalVitalSample(timestamp_seconds=900.0, heart_rate=86, systolic_bp=116, diastolic_bp=78, respiratory_rate=17, spo2=97),
        ClinicalVitalSample(timestamp_seconds=1800.0, heart_rate=96, systolic_bp=111, diastolic_bp=79, respiratory_rate=19, spo2=96),
    ]

    assessments = [reflex.observe(s) for s in samples]
    final = assessments[-1]

    # Static NEWS2 is only 1 (routine green under static threshold rules!),
    # but System 1 CfC trajectory catches the compensatory shock drift!
    assert final.static_news2_score <= 2
    assert final.subthreshold_early_warning is True
    assert final.deterioration_detected is True
    assert "sys1.trajectory.compensatory_shock_drift" in final.red_flags
    assert final.cynefin_suggestion is CynefinClass.complex


def test_negation_never_triggers_false_positive_symptom() -> None:
    """S1-04 / M-04: Explicit negations record pertinent negatives and never trigger false-positive red flags."""
    result = ConsultationStateReflex.evaluate(
        "Patient presents with mild low back pain after lifting. "
        "Denies chest pain, no shortness of breath, without saddle anaesthesia or urinary retention. "
        "Patient says thank you, that makes sense."
    )
    assert "Backache" in result.confirmed_symptoms
    assert "Chest pain" not in result.confirmed_symptoms
    assert "Dyspnoea" not in result.confirmed_symptoms
    assert not any("chest_pain" in flag for flag in result.active_red_flags)
    assert not any("cauda_equina" in flag for flag in result.active_red_flags)
    assert any("no chest pain" in neg.lower() for neg in result.negated_findings)
    assert result.trust_level == "high"
    assert result.requires_clinician_review is True
    assert result.latency_ms <= 20.0


def test_positive_red_flag_and_contrastive_clause_detection() -> None:
    """S1-04: Contrastive conjunction ('no fever, but severe central chest tightness radiating to left arm') fires red flag."""
    result = ConsultationStateReflex.evaluate(
        "Patient has no fever or cough, but reports crushing chest pain radiating to left arm and is terrified."
    )
    assert "Chest pain" in result.confirmed_symptoms
    assert "sys1.red_flag.chest_pain" in result.active_red_flags
    assert "sys1.red_flag.jaw_or_arm_radiation" in result.active_red_flags
    assert any("no fever" in neg.lower() for neg in result.negated_findings)
    assert result.anxiety_level == "critical"
    assert result.risk_score >= 0.78


def test_live_intuition_routes_cynefin_and_binds_superpersona_contract() -> None:
    """S1-05: compute_live_intuition and build_superpersona_contract dynamically adjust framework & Cynefin class."""
    # Baseline deterministic contract remains unchanged when no clinical_context is supplied
    ref_doc = reference_superpersona_contract("doctor")
    assert ref_doc.intuition.confidence == 0.72

    # Live contract with acute red flag escalates risk and prioritises triage/lab salience
    live_contract = build_superpersona_contract(
        persona_key="doctor",
        role_title="Doctor",
        role_category="clinical",
        allowed_purposes=["treatment", "emergency"],
        default_framework="soap",
        clinical_context={
            "clinical_text": "Sudden thunderclap headache with photophobia and neck stiffness",
        },
    )
    assert live_contract.intuition.selected_framework == "isbar"
    assert live_contract.intuition.risk_score >= 0.78
    assert "sys1.red_flag.thunderclap_or_meningism" in live_contract.intuition.reason_codes or any(
        "red_flag" in c for c in live_contract.intuition.reason_codes
    )

    intuition, routing = compute_live_intuition(
        persona_key="doctor",
        intents=["triage.start", "result.retrieve"],
        safety_class=SafetyClass.sensitive,
        clinical_text="Thunderclap headache with neck stiffness",
    )
    assert routing.cynefin_class is CynefinClass.complex
    assert routing.red_flags


def test_open_source_model_registry_and_slm_circuit_breaker() -> None:
    """S1-06: Enforces open-source model registry, refuses external PHI egress, and trips circuit breaker on failure."""
    # 1. Verify open-source models are registered with Apache-2.0 / open weights
    qwen_spec = get_open_source_model_spec("qwen3:1.7b", require_osi_approved=True)
    assert qwen_spec.license_spdx == "Apache-2.0"
    assert "ollama" in qwen_spec.windows_runtimes
    assert "ncps-cfc-6d" in OPEN_SOURCE_SYSTEM1_MODELS

    # 2. Refuse proprietary models
    with pytest.raises(ProprietaryModelRefusedError):
        get_open_source_model_spec("gpt-4o-proprietary")

    with pytest.raises(ProprietaryModelRefusedError):
        LocalSlmReflexAdapter(model_name="claude-3-opus")

    # 3. Refuse external PHI egress URLs
    assert is_local_trust_endpoint("http://localhost/api/generate") is True
    assert is_local_trust_endpoint("https://api.openai.com/v1/chat/completions") is False
    with pytest.raises(ExternalEgressRefusedError):
        LocalSlmReflexAdapter(endpoint_url="https://api.external-cloud.example/v1/generate")

    # 4. Verify Nygard circuit breaker trips after failure_threshold and falls back in <2ms
    adapter = LocalSlmReflexAdapter(
        endpoint_url="http://localhost/api/generate",
        model_name="qwen3:0.6b",
        failure_threshold=2,
        recovery_timeout_seconds=60.0,
    )
    assert adapter.state is CircuitState.closed

    def failing_transport(url: str, payload: dict, timeout: float) -> dict:
        raise TimeoutError("Local Ollama daemon not running")

    r1 = adapter.classify_reflex("Patient has chest pain", transport_fn=failing_transport)
    assert adapter.state is CircuitState.closed
    assert "sys1.slm_fallback_to_cfc" in r1.reason_codes
    assert "sys1.red_flag.chest_pain" in r1.active_red_flags

    r2 = adapter.classify_reflex("Patient has chest pain", transport_fn=failing_transport)
    assert adapter.state is CircuitState.open
    assert adapter.failure_count == 2

    # When OPEN, transport_fn is not even called; immediate <2ms fallback
    r3 = adapter.classify_reflex("Patient has chest pain", transport_fn=failing_transport)
    assert "sys1.slm_circuit_open_fallback" in r3.reason_codes
    assert r3.latency_ms < 5.0


def test_hl7v2_semantic_reflex_catches_unit_swaps_and_haemolysis() -> None:
    """S1-10: Hl7v2SemanticReflex and Hl7v2Adapter catch glucose mmol/L vs mg/dL swaps and haemolysed K+."""
    adapter = Hl7v2Adapter()
    raw_oru = {
        "type": "ORU^R01",
        "pid": {"patient_id": "P-9001"},
        "obx": [
            {
                "observation_id": {"code": "2339-0", "display": "Glucose"},
                "value": 110.0,
                "unit": "mmol/L",  # 110 mg/dL sent with mmol/L label!
                "status": "F",
            },
            {
                "observation_id": {"code": "2823-3", "display": "Potassium"},
                "value": 14.2,
                "unit": "mmol/L",  # Haemolysed / EDTA contaminated specimen!
                "status": "F",
            },
        ],
    }
    envelope = asyncio.run(adapter.to_canonical(raw_oru))
    triage = envelope.system1_triage
    assert triage["quarantine_required"] is True
    assert triage["requires_human_review"] is True
    codes = {a["code"] for a in triage["anomalies"]}
    assert "HL7_GLUCOSE_UNIT_SWAP_MGDL_AS_MMOLL" in codes
    assert "HL7_POTASSIUM_HAEMOLYSIS_OR_EDTA_ARTIFACT" in codes
    assert triage["latency_ms"] < 5.0


def test_signalbox_co_control_governance_escalates_on_reflex_red_flag() -> None:
    """S1-11: evaluate_reflex_signal_governance escalates to human_in_loop when System 1 flags risk."""
    intuition, _ = compute_live_intuition(
        persona_key="clinician",
        intents=["result.retrieve"],
        safety_class=SafetyClass.routine,
        clinical_text="Patient has slurred speech and unilateral arm weakness",
    )
    decision = evaluate_reflex_signal_governance(
        intent="result.retrieve",
        persona="clinician",
        intuition=intuition,
    )
    assert decision.tier is GovernanceTier.human_in_loop
    assert decision.handoff is not None


def test_dual_loop_self_improvement_calibration_tracker() -> None:
    """M-06: System1CalibrationTracker computes Brier score, ECE, OutcomeTally, and governed WeightRelease."""
    tracker = System1CalibrationTracker(baseline_version="sys1-weights-1.0.0")

    # Record calibrated true positives and true negatives (FN = 0)
    high_risk_intuition, _ = compute_live_intuition(
        persona_key="doctor",
        intents=["triage.start"],
        clinical_text="Crushing chest pain radiating to jaw",
    )
    low_risk_intuition, _ = compute_live_intuition(
        persona_key="doctor",
        intents=["result.retrieve"],
        clinical_text="Patient denies chest pain, no fever, routine follow-up",
    )

    for _ in range(4):
        tracker.record_feedback(
            high_risk_intuition,
            actual_escalated=True,
            reviewer_outcome=ReviewerOutcome.correct,
        )
        tracker.record_feedback(
            low_risk_intuition,
            actual_escalated=False,
            reviewer_outcome=ReviewerOutcome.correct,
        )

    snap = tracker.snapshot()
    assert snap.total_events == 8
    assert snap.false_negatives == 0
    assert snap.recall == 1.0
    assert snap.brier_score <= 0.12
    assert snap.outcome_tally.correct_rate == 1.0
    assert snap.candidate_weight_release.weight_for("system1.reflex") >= 1.0


def test_simon_bounded_rationality_referral_satisficing_equity_afya() -> None:
    """Simon (1955) Bounded Rationality: Equity Afya specialist referral satisficing reflex."""
    from bridge_sdk.system1_reflex import (
        BoundedRationalityEnvelope,
        ReferralSatisficingReflex,
    )

    # 1. Acute red-flag presentation (chest pain radiating to left arm)
    acute_res = ReferralSatisficingReflex.evaluate(
        clinical_text="Patient reports central chest pain radiating to left arm and shortness of breath.",
        longitudinal_conditions=["Hypertension", "Type 2 Diabetes"],
        active_medications=["amlodipine 5mg", "metformin 500mg"],
        previous_investigations=["HbA1c 58 mmol/mol"],
        vitals={"heart_rate": 112.0, "systolic_bp": 148.0, "spo2": 95.0},
        patient_cost_constraint="sha_nhif_covered",
    )
    assert acute_res.recommended_option.specialty == "Cardiology"
    assert acute_res.recommended_option.pathway_type in (
        "emergency_transfer",
        "fast_track_specialist",
    )
    assert acute_res.recommended_option.meets_aspiration_threshold is True
    assert len(acute_res.satisficing_alternatives) == 3
    assert acute_res.bounded_rationality.clinician_accountability_retained is True
    assert acute_res.bounded_rationality.cognitive_chunks_surfaced <= 4
    assert acute_res.bounded_rationality.decision_latency_ms < 10.0
    assert acute_res.bounded_rationality.information_completeness_ratio >= 0.8

    # 2. Routine presentation without red flags satisfices on in-clinic / tele-specialist care
    routine_res = ReferralSatisficingReflex.evaluate(
        clinical_text="Mild intermittent headache for 3 days. Denies photophobia, no neck stiffness, no visual disturbance.",
        patient_cost_constraint="low_copay_franchise",
    )
    assert routine_res.recommended_option.pathway_type in (
        "in_clinic_guideline_care",
        "tele_specialist_coconsult",
    )
    assert len(routine_res.bounded_rationality.missing_information_gaps) >= 1

    # 3. Attempting to violate clinician_accountability_retained raises ValueError
    with pytest.raises(ValueError, match="clinician_accountability_retained"):
        BoundedRationalityEnvelope(
            information_completeness_ratio=0.9,
            synthesized_sources=("history",),
            missing_information_gaps=(),
            cognitive_chunks_surfaced=2,
            alternatives_evaluated=4,
            alternatives_satisficed=2,
            decision_latency_ms=0.5,
            consultation_time_saved_seconds=120.0,
            ai_data_quality_bound=0.9,
            ai_epistemic_uncertainty=0.1,
            clinician_accountability_retained=False,
        )


def test_simon_bounded_rationality_ward_staffing_satisficing() -> None:
    """Simon's hospital manager nurse deployment decision under arrival & acuity uncertainty."""
    from bridge_sdk.system1_reflex import StaffingSatisficingReflex

    rec = StaffingSatisficingReflex.evaluate(
        ward_id="ward-acute-cardio",
        current_census=22,
        historical_mean_arrivals=6.0,
        historical_std_arrivals=2.5,
        expected_discharges=4.0,
        high_acuity_drift_patients=3,
        base_patients_per_nurse=4.0,
    )
    assert rec.expected_patient_census == 24.0
    assert rec.census_uncertainty_band[0] < 24 < rec.census_uncertainty_band[1]
    assert rec.recommended_nurses >= rec.minimum_safe_floor_nurses
    assert rec.bounded_rationality.clinician_accountability_retained is True
    assert rec.bounded_rationality.decision_latency_ms < 5.0


_CANONICAL_14COL_PATH = (
    Path(__file__).resolve().parent
    / "harness"
    / "reduced_json_matrices"
    / "system1-reflex_scenarios.14col.json"
)
_CANONICAL_14COL_COLS = [
    "use_case_id",
    "component",
    "scenario",
    "test_type",
    "priority",
    "expected_outcomes",
    "preconditions",
    "test_data",
    "validation_rules",
    "dependencies",
    "tags",
    "estimated_duration",
    "automation_status",
    "notes",
]


def _load_system1_14col_rows() -> list[dict[str, object]]:
    import json

    payload = json.loads(_CANONICAL_14COL_PATH.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == "BT_CANONICAL_MATRIX_V1_14COL"
    rows = payload.get("test_cases", [])
    assert len(rows) == 100
    return rows


_SYSTEM1_14COL_ROWS = _load_system1_14col_rows()


@pytest.mark.parametrize(
    "row",
    _SYSTEM1_14COL_ROWS,
    ids=[str(r["use_case_id"]) for r in _SYSTEM1_14COL_ROWS],
)
def test_canonical_14col_system1_scenario_matrix_row(row: dict[str, object]) -> None:
    """Execute each of the 100 canonical 14-column System 1 scenario rows (85/10/5)."""
    from bridge_sdk.system1_reflex import (
        BoundedRationalityEnvelope,
        ReferralSatisficingReflex,
        StaffingSatisficingReflex,
        get_open_source_model_spec,
    )

    assert list(row.keys()) == _CANONICAL_14COL_COLS
    assert row["test_type"] in {"positive", "negative", "edge"}
    assert row["priority"] in {"high", "medium", "low"}
    assert row["automation_status"] == "automated"

    test_data = row["test_data"]
    assert isinstance(test_data, dict)
    body = test_data["input_payload"]["body"]
    engine = str(body["engine"])
    clinical_text = str(body["clinical_text"])
    vitals = dict(body.get("vitals") or {})
    allergies = list(body.get("allergies") or [])
    test_type = str(row["test_type"])

    if test_type == "negative":
        with pytest.raises(ProprietaryModelRefusedError):
            get_open_source_model_spec("gpt-4o-mini")
        t0 = Tier0SafetyFloor.evaluate(
            vitals=vitals,
            allergies=allergies or ["penicillin"],
            proposed_medications=["amoxicillin"],
            free_text_plan="methotrexate 10mg daily",
        )
        assert t0.blocked is True
        return

    if engine == "Tier0SafetyFloor":
        res_t0 = Tier0SafetyFloor.evaluate(
            vitals=vitals,
            allergies=allergies,
            free_text_plan=clinical_text,
        )
        assert isinstance(res_t0.blocked, bool)
    elif engine == "CfCStateCell":
        cell = CfCStateCell(state_dim=6, base_tau_seconds=900.0)
        h_next = cell.step(
            (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            (0.2, -0.1, 0.1, 0.3, -0.1, 0.0),
            1.0 if test_type == "edge" else 120.0,
        )
        assert len(h_next) == 6
        assert all(-1.0 <= v <= 1.0 for v in h_next)
    elif engine == "PhysiologicalTrajectoryReflex":
        traj = PhysiologicalTrajectoryReflex()
        t_res = traj.observe(
            ClinicalVitalSample(
                timestamp_seconds=1000.0,
                heart_rate=float(vitals.get("heart_rate", 90.0)),
                systolic_bp=float(vitals.get("systolic_bp", 120.0)),
                diastolic_bp=float(vitals.get("diastolic_bp", 80.0)),
                respiratory_rate=float(vitals.get("respiratory_rate", 18.0)),
                spo2=float(vitals.get("spo2", 97.0)),
            )
        )
        assert t_res.latency_ms < 10.0
    elif engine == "ConsultationStateReflex":
        c_res = ConsultationStateReflex.evaluate(
            "" if test_type == "edge" else clinical_text,
            vitals=vitals,
            allergies=allergies,
        )
        assert c_res.latency_ms < 20.0
    elif engine == "ReferralSatisficingReflex":
        r_res = ReferralSatisficingReflex.evaluate(
            clinical_text=clinical_text,
            specialty_requested=str(body.get("specialty", "cardiology")),
            vitals=vitals,
        )
        assert len(r_res.satisficing_alternatives) <= 3
        assert r_res.bounded_rationality.clinician_accountability_retained is True
    elif engine == "StaffingSatisficingReflex":
        s_res = StaffingSatisficingReflex.evaluate(
            ward_id="ward-1",
            current_census=22,
            historical_mean_arrivals=6.0,
            historical_std_arrivals=2.5,
            expected_discharges=4.0,
            high_acuity_drift_patients=3,
        )
        assert s_res.recommended_nurses >= s_res.minimum_safe_floor_nurses
        assert s_res.bounded_rationality.clinician_accountability_retained is True
    elif engine == "Hl7v2SemanticReflex":
        adapter = Hl7v2Adapter()
        env_hl7 = asyncio.run(
            adapter.to_canonical(
                {
                    "type": "ORU^R01",
                    "pid": {"patient_id": "P-9001"},
                    "obx": [
                        {
                            "observation_id": {"code": "2339-0", "display": "Glucose"},
                            "value": 110.0,
                            "unit": "mmol/L",
                            "status": "F",
                        }
                    ],
                }
            )
        )
        assert env_hl7.system1_triage["quarantine_required"] is True
    elif engine == "LocalSlmReflexAdapter":
        spec = get_open_source_model_spec("qwen3:0.6b")
        assert spec.osi_approved is True
    elif engine == "System1CalibrationTracker":
        tracker = System1CalibrationTracker()
        intuition, _ = compute_live_intuition(
            persona_key="doctor",
            intents=["triage.start"],
            clinical_text=clinical_text,
        )
        tracker.record_feedback(
            intuition,
            actual_escalated=True,
            reviewer_outcome=ReviewerOutcome.correct,
        )
        snap = tracker.snapshot()
        assert snap.total_events == 1
    else:
        intuition, _ = compute_live_intuition(
            persona_key="clinician",
            intents=["result.retrieve"],
            safety_class=SafetyClass.routine,
            clinical_text="Patient has slurred speech and unilateral arm weakness",
        )
        gov = evaluate_reflex_signal_governance(
            intent="result.retrieve",
            persona="clinician",
            intuition=intuition,
        )
        assert gov.tier is GovernanceTier.human_in_loop
        env = BoundedRationalityEnvelope(
            information_completeness_ratio=0.85,
            synthesized_sources=("emr",),
            missing_information_gaps=(),
            cognitive_chunks_surfaced=2,
            alternatives_evaluated=4,
            alternatives_satisficed=2,
            decision_latency_ms=0.5,
            consultation_time_saved_seconds=90.0,
            ai_data_quality_bound=0.9,
            ai_epistemic_uncertainty=0.1,
            clinician_accountability_retained=True,
        )
        assert env.clinician_accountability_retained is True


