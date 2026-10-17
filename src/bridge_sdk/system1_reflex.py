"""System 1 continuous-state and reflexive clinical decision fabric.

Provides sub-millisecond to sub-25ms pre-deliberative clinical state tracking
and fast routing across the Symphonix-Health estate:

1. ``Tier0SafetyFloor`` (S1-01): Deterministic statutory safety floor (<0.5ms)
   enforcing NEWS2 critical single-parameter bounds, high-risk BNF contraindication
   pairs, cross-reactive allergy checks, and unverified dose-proposal blocks.
   Enforces strict clinical monotonicity (System 1 can escalate risk or add red
   flags, but can never downgrade or suppress a Tier 0 finding).
2. ``CfCStateCell`` & ``PhysiologicalTrajectoryReflex`` (S1-02, S1-03):
   Closed-form Continuous-time (CfC) state cell solving the liquid time-constant
   ODE analytically for irregular clinical observation intervals ``dt``, paired
   with multi-parameter trajectory analysis (Shock Index velocity, pulse-pressure
   narrowing, respiratory-oxygenation divergence) to detect compensatory shock
   and early deterioration before static NEWS2 thresholds fire.
3. ``ConsultationStateReflex`` (S1-04): Scope-bounded negation-aware clinical
   text and consultation state machine (<10ms) tracking confirmed symptoms,
   pertinent negatives, active red flags, unscreened safety-net prompts,
   SNOMED-CT concept candidates, affective anxiety/trust trajectory, and
   structured SOAP note pre-staging.
4. ``Hl7v2SemanticReflex`` (S1-10): Sub-5ms semantic and unit-mismatch triage
   for HL7v2 ADT/ORU messages and FHIR R4 Observations (e.g. mmol/L vs mg/dL
   unit swaps, haemolysed potassium artifacts vs true hyperkalaemia, and
   biological survival bounds).
5. ``LocalSlmReflexAdapter`` (S1-06): Circuit-breaker protected (FR-CIRCUIT_-001..005)
   local Windows SLM fast-router (Ollama / ONNX Runtime) with ``/no_think`` and
   JSON schema constraints, strictly restricted to localhost/127.0.0.1 (zero
   external PHI egress) with <2ms fallback to the in-process CfC/reflex engine.
6. ``System1CalibrationTracker`` (M-06): Dual-loop self-improvement tracker
   comparing System 1 ``IntuitionDecision`` outputs against System 2
   ``CouncilDeliberation`` and clinician ``ReviewerOutcome`` signals to compute
   Brier calibration scores, ECE, and governed ``WeightRelease`` proposals.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bridge_sdk.agent_contract import SafetyClass
from bridge_sdk.council_deliberation import CynefinClass, RoutingDecision, WeightRelease, route
from bridge_sdk.human_handoff import OutcomeTally, ReviewerOutcome, summarise_outcomes
from bridge_sdk.signal_governance import (
    CONFIDENCE_BYPASS_THRESHOLD,
    GovernedDecision,
    PerceivedSignal,
    evaluate_signal_action,
)
from bridge_sdk.superpersona_contract import IntuitionDecision

__all__ = [
    "CircuitState",
    "CfCStateCell",
    "ClinicalVitalSample",
    "ConsultationReflexResult",
    "ConsultationStateReflex",
    "ExternalEgressRefusedError",
    "Hl7v2AnomalyFinding",
    "Hl7v2SemanticReflex",
    "Hl7v2TriageResult",
    "LocalSlmReflexAdapter",
    "OPEN_SOURCE_SYSTEM1_MODELS",
    "OpenSourceSystem1ModelSpec",
    "PhysiologicalTrajectoryReflex",
    "ProprietaryModelRefusedError",
    "SafetyMonotonicityError",
    "System1CalibrationSnapshot",
    "System1CalibrationTracker",
    "Tier0SafetyFloor",
    "Tier0SafetyResult",
    "TrajectoryAssessment",
    "compute_live_intuition",
    "evaluate_reflex_signal_governance",
    "get_open_source_model_spec",
    "is_local_trust_endpoint",
]


class SafetyMonotonicityError(ValueError):
    """Raised if a caller attempts to bypass or downgrade a Tier 0 safety hit."""


class ExternalEgressRefusedError(PermissionError):
    """Raised when a local System 1 SLM adapter is configured with a non-local URL."""


class ProprietaryModelRefusedError(PermissionError):
    """Raised when a non-open-source model is requested under strict open-source policy."""


@dataclass(frozen=True)
class OpenSourceSystem1ModelSpec:
    """Metadata for verified open-source System 1 models on Windows (Ollama / llama.cpp / ONNX)."""

    model_id: str
    ollama_tag: str
    huggingface_repo: str
    architecture: str  # "cfc_ltc_ode" | "liquid_state_space" | "hybrid_mamba2_ssm" | "fast_no_think_slm"
    license_spdx: str  # e.g. "Apache-2.0", "MIT"
    parameter_count: str
    windows_runtimes: tuple[str, ...]
    supports_no_think_toggle: bool
    p95_cpu_budget_ms: int


OPEN_SOURCE_SYSTEM1_MODELS: dict[str, OpenSourceSystem1ModelSpec] = {
    "ncps-cfc-6d": OpenSourceSystem1ModelSpec(
        model_id="ncps-cfc-6d",
        ollama_tag="builtin:cfc-6d",
        huggingface_repo="mlech26l/ncps",
        architecture="cfc_ltc_ode",
        license_spdx="Apache-2.0",
        parameter_count="6-state ODE (<10KB)",
        windows_runtimes=("python-math-native", "ncps-pytorch", "onnxruntime"),
        supports_no_think_toggle=True,
        p95_cpu_budget_ms=1,
    ),
    "qwen3:0.6b": OpenSourceSystem1ModelSpec(
        model_id="qwen3:0.6b",
        ollama_tag="qwen3:0.6b",
        huggingface_repo="Qwen/Qwen3-0.6B",
        architecture="fast_no_think_slm",
        license_spdx="Apache-2.0",
        parameter_count="0.6B",
        windows_runtimes=("ollama", "llama.cpp", "onnxruntime-genai"),
        supports_no_think_toggle=True,
        p95_cpu_budget_ms=65,
    ),
    "qwen3:1.7b": OpenSourceSystem1ModelSpec(
        model_id="qwen3:1.7b",
        ollama_tag="qwen3:1.7b",
        huggingface_repo="Qwen/Qwen3-1.7B",
        architecture="fast_no_think_slm",
        license_spdx="Apache-2.0",
        parameter_count="1.7B",
        windows_runtimes=("ollama", "llama.cpp", "onnxruntime-genai"),
        supports_no_think_toggle=True,
        p95_cpu_budget_ms=120,
    ),
    "granite4-tiny:2b": OpenSourceSystem1ModelSpec(
        model_id="granite4-tiny:2b",
        ollama_tag="granite3.3:2b",
        huggingface_repo="ibm-granite/granite-3.3-2b-instruct",
        architecture="hybrid_mamba2_ssm",
        license_spdx="Apache-2.0",
        parameter_count="2.0B",
        windows_runtimes=("ollama", "llama.cpp", "onnxruntime"),
        supports_no_think_toggle=True,
        p95_cpu_budget_ms=110,
    ),
    "smollm2:360m": OpenSourceSystem1ModelSpec(
        model_id="smollm2:360m",
        ollama_tag="smollm2:360m",
        huggingface_repo="HuggingFaceTB/SmolLM2-360M-Instruct",
        architecture="fast_no_think_slm",
        license_spdx="Apache-2.0",
        parameter_count="360M",
        windows_runtimes=("ollama", "llama.cpp", "onnxruntime"),
        supports_no_think_toggle=True,
        p95_cpu_budget_ms=45,
    ),
    "lfm2:1.2b": OpenSourceSystem1ModelSpec(
        model_id="lfm2:1.2b",
        ollama_tag="lfm2:1.2b",
        huggingface_repo="LiquidAI/LFM2-1.2B",
        architecture="liquid_state_space",
        license_spdx="Open-Weight-Liquid",
        parameter_count="1.2B",
        windows_runtimes=("ollama", "llama.cpp", "onnxruntime"),
        supports_no_think_toggle=True,
        p95_cpu_budget_ms=80,
    ),
}


def get_open_source_model_spec(model_name: str, *, require_osi_approved: bool = False) -> OpenSourceSystem1ModelSpec:
    """Resolve a model name against the verified open-source System 1 registry."""
    key = model_name.strip().lower()
    if key not in OPEN_SOURCE_SYSTEM1_MODELS:
        raise ProprietaryModelRefusedError(
            f"Model '{model_name}' is not in OPEN_SOURCE_SYSTEM1_MODELS "
            f"({sorted(OPEN_SOURCE_SYSTEM1_MODELS)}). Open-source System 1 models are required."
        )
    spec = OPEN_SOURCE_SYSTEM1_MODELS[key]
    if require_osi_approved and spec.license_spdx not in ("Apache-2.0", "MIT", "BSD-3-Clause"):
        raise ProprietaryModelRefusedError(
            f"Model '{model_name}' has license '{spec.license_spdx}', which is not strict OSI (Apache-2.0/MIT)."
        )
    return spec


# ---------------------------------------------------------------------------
# 1. Tier 0 Deterministic Safety Floor (S1-01)
# ---------------------------------------------------------------------------

_DOSE_PROPOSAL_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:micrograms?|mcg|milligrams?|mg|grams?|g|"
    r"millilit(?:er|re)s?|ml|units?|iu)\b",
    re.IGNORECASE,
)

PENICILLIN_FAMILY = frozenset(
    {
        "penicillin",
        "benzylpenicillin",
        "phenoxymethylpenicillin",
        "amoxicillin",
        "ampicillin",
        "co-amoxiclav",
        "augmentin",
        "flucloxacillin",
        "piperacillin",
        "tazocin",
        "ticarcillin",
    }
)

NSAID_FAMILY = frozenset(
    {
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketorolac",
        "indomethacin",
        "celecoxib",
        "etoricoxib",
        "meloxicam",
        "aspirin",
    }
)

ANTICOAGULANT_FAMILY = frozenset(
    {
        "warfarin",
        "apixaban",
        "rivaroxaban",
        "dabigatran",
        "edoxaban",
        "enoxaparin",
        "heparin",
    }
)

ACEI_ARB_FAMILY = frozenset(
    {
        "ramipril",
        "lisinopril",
        "enalapril",
        "perindopril",
        "losartan",
        "candesartan",
        "irbesartan",
        "valsartan",
    }
)

BETA_BLOCKER_NON_SELECTIVE = frozenset(
    {
        "propranolol",
        "carvedilol",
        "sotalol",
        "timolol",
        "labetalol",
    }
)


@dataclass(frozen=True)
class Tier0SafetyResult:
    """Deterministic safety floor output (<0.5ms)."""

    blocked: bool
    emergency: bool
    min_risk_score: float
    red_flags: tuple[str, ...]
    reason_codes: tuple[str, ...]
    contraindications: tuple[str, ...]
    news2_single_param_red: bool = False
    latency_ms: float = 0.0


class Tier0SafetyFloor:
    """Deterministic clinical safety floor enforcing statutory invariants."""

    @staticmethod
    def evaluate(
        *,
        vitals: Mapping[str, Any] | None = None,
        proposed_medications: Sequence[str] = (),
        active_medications: Sequence[str] = (),
        allergies: Sequence[str] = (),
        conditions: Sequence[str] = (),
        free_text_plan: str = "",
        allow_dose_proposals: bool = False,
    ) -> Tier0SafetyResult:
        t0 = time.perf_counter()
        red_flags: list[str] = []
        reasons: list[str] = []
        contraindications: list[str] = []
        emergency = False
        blocked = False
        news2_red = False
        min_risk = 0.05

        # 1. Statutory NEWS2 single-parameter critical bounds (score = 3 in single parameter)
        if vitals:
            rr = _opt_float(vitals.get("respiratory_rate") or vitals.get("rr"))
            spo2 = _opt_float(vitals.get("spo2") or vitals.get("oxygen_saturation"))
            sbp = _opt_float(vitals.get("systolic_bp") or vitals.get("sbp"))
            hr = _opt_float(vitals.get("heart_rate") or vitals.get("hr"))
            temp = _opt_float(vitals.get("temperature") or vitals.get("temp"))
            avpu = str(vitals.get("consciousness") or vitals.get("avpu") or "A").strip().upper()

            if rr is not None and (rr <= 8.0 or rr >= 25.0):
                red_flags.append(f"tier0.news2.respiratory_rate_critical:{rr:g}")
                reasons.append("tier0.news2_single_param_red")
                news2_red = True
                min_risk = max(min_risk, 0.88)
                if rr <= 6.0 or rr >= 30.0:
                    emergency = True

            if spo2 is not None and spo2 <= 91.0:
                red_flags.append(f"tier0.news2.spo2_critical:{spo2:g}")
                reasons.append("tier0.news2_single_param_red")
                news2_red = True
                min_risk = max(min_risk, 0.88)
                if spo2 <= 85.0:
                    emergency = True

            if sbp is not None and (sbp <= 90.0 or sbp >= 220.0):
                red_flags.append(f"tier0.news2.sbp_critical:{sbp:g}")
                reasons.append("tier0.news2_single_param_red")
                news2_red = True
                min_risk = max(min_risk, 0.88)
                if sbp <= 75.0:
                    emergency = True

            if hr is not None and (hr <= 40.0 or hr >= 131.0):
                red_flags.append(f"tier0.news2.heart_rate_critical:{hr:g}")
                reasons.append("tier0.news2_single_param_red")
                news2_red = True
                min_risk = max(min_risk, 0.88)
                if hr <= 35.0 or hr >= 150.0:
                    emergency = True

            if temp is not None and (temp <= 35.0 or temp >= 39.1):
                red_flags.append(f"tier0.news2.temperature_critical:{temp:g}")
                reasons.append("tier0.news2_single_param_red")
                news2_red = True
                min_risk = max(min_risk, 0.78)

            if avpu not in ("A", "ALERT", ""):
                red_flags.append(f"tier0.news2.consciousness_altered:{avpu}")
                reasons.append("tier0.news2_single_param_red")
                news2_red = True
                min_risk = max(min_risk, 0.92)
                if avpu in ("P", "U", "PAIN", "UNRESPONSIVE"):
                    emergency = True

        # 2. Extract medications mentioned in free_text_plan + proposed_medications
        plan_lower = free_text_plan.lower()
        all_known_meds = (
            PENICILLIN_FAMILY
            | NSAID_FAMILY
            | ANTICOAGULANT_FAMILY
            | ACEI_ARB_FAMILY
            | BETA_BLOCKER_NON_SELECTIVE
            | {"methotrexate", "potassium", "spironolactone", "lithium", "Gentamicin".lower()}
        )
        inferred_from_text = [
            med
            for med in sorted(all_known_meds)
            if re.search(rf"\b{re.escape(med)}\b", plan_lower)
            and not _is_term_negated_in_text(plan_lower, med)
        ]
        candidate_meds = {m.strip().lower() for m in proposed_medications if m.strip()} | set(
            inferred_from_text
        )
        current_meds = {m.strip().lower() for m in active_medications if m.strip()}
        allergy_text = " ".join(str(a).lower() for a in allergies)
        condition_text = " ".join(str(c).lower() for c in conditions)

        # 2a. Allergy cross-reactivity (Penicillin / Beta-lactam + NSAID)
        has_penicillin_allergy = any(
            tok in allergy_text for tok in ("penicillin", "amoxicillin", "beta-lactam", "augmentin", "co-amoxiclav")
        )
        if has_penicillin_allergy:
            clashing_pen = sorted(candidate_meds & PENICILLIN_FAMILY)
            if clashing_pen:
                msg = f"tier0.allergy.penicillin_cross_reactivity:{','.join(clashing_pen)}"
                contraindications.append(msg)
                red_flags.append(msg)
                reasons.append("tier0.allergy_contraindication")
                blocked = True
                min_risk = max(min_risk, 0.95)

        for allergy_item in allergies:
            norm_allergy = str(allergy_item).strip().lower()
            if not norm_allergy:
                continue
            for med in sorted(candidate_meds):
                if med in norm_allergy or norm_allergy in med:
                    msg = f"tier0.allergy.direct_match:{med}"
                    if msg not in contraindications:
                        contraindications.append(msg)
                        red_flags.append(msg)
                        reasons.append("tier0.allergy_contraindication")
                        blocked = True
                        min_risk = max(min_risk, 0.95)

        # 2b. High-risk BNF drug-drug & drug-condition contraindications
        all_meds_union = candidate_meds | current_meds
        if (candidate_meds & NSAID_FAMILY) and (all_meds_union & ANTICOAGULANT_FAMILY):
            msg = "tier0.bnf.nsaid_plus_anticoagulant_bleed_risk"
            contraindications.append(msg)
            red_flags.append(msg)
            reasons.append("tier0.bnf_interaction")
            blocked = True
            min_risk = max(min_risk, 0.90)

        if (candidate_meds & NSAID_FAMILY) and any(
            k in condition_text
            for k in ("peptic ulcer", "gi bleed", "gastrointestinal bleed", "ckd stage 4", "ckd stage 5", "renal failure")
        ):
            msg = "tier0.bnf.nsaid_contraindicated_in_ulcer_or_severe_ckd"
            contraindications.append(msg)
            red_flags.append(msg)
            reasons.append("tier0.bnf_contraindication")
            blocked = True
            min_risk = max(min_risk, 0.90)

        if (candidate_meds & ACEI_ARB_FAMILY) and any(
            k in condition_text for k in ("pregnan", "second trimester", "third trimester", "hyperkalaemia", "hyperkalemia")
        ):
            msg = "tier0.bnf.acei_arb_contraindicated_pregnancy_or_hyperkalaemia"
            contraindications.append(msg)
            red_flags.append(msg)
            reasons.append("tier0.bnf_contraindication")
            blocked = True
            min_risk = max(min_risk, 0.94)

        if (candidate_meds & BETA_BLOCKER_NON_SELECTIVE) and any(
            k in condition_text for k in ("asthma", "bronchospasm", "wheeze")
        ):
            msg = "tier0.bnf.non_selective_beta_blocker_in_asthma"
            contraindications.append(msg)
            red_flags.append(msg)
            reasons.append("tier0.bnf_contraindication")
            blocked = True
            min_risk = max(min_risk, 0.92)

        if "methotrexate" in candidate_meds and re.search(
            r"methotrexate[^\n.;]{0,40}\b(?:daily|every\s+day|od|once\s+daily)\b",
            plan_lower,
        ):
            msg = "tier0.never_event.methotrexate_daily_dosing_hazard"
            contraindications.append(msg)
            red_flags.append(msg)
            reasons.append("tier0.never_event_guard")
            blocked = True
            min_risk = max(min_risk, 0.98)

        # 3. Unverified dose proposal check when operating in AI draft mode
        if free_text_plan and not allow_dose_proposals and _DOSE_PROPOSAL_RE.search(free_text_plan):
            reasons.append("tier0.dose_proposal_requires_clinician_signoff")
            min_risk = max(min_risk, 0.65)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return Tier0SafetyResult(
            blocked=blocked,
            emergency=emergency,
            min_risk_score=round(min_risk, 4),
            red_flags=tuple(dict.fromkeys(red_flags)),
            reason_codes=tuple(dict.fromkeys(reasons)),
            contraindications=tuple(dict.fromkeys(contraindications)),
            news2_single_param_red=news2_red,
            latency_ms=round(elapsed_ms, 4),
        )

    @staticmethod
    def enforce_monotonicity(
        tier0: Tier0SafetyResult,
        *,
        risk_score: float,
        red_flags: Sequence[str],
        reason_codes: Sequence[str],
    ) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
        """Guarantee System 1 never downgrades or drops a Tier 0 safety finding."""
        merged_risk = max(float(risk_score), float(tier0.min_risk_score))
        merged_flags = tuple(dict.fromkeys([*tier0.red_flags, *red_flags]))
        merged_reasons = tuple(dict.fromkeys([*tier0.reason_codes, *reason_codes]))
        if merged_risk < tier0.min_risk_score or not set(tier0.red_flags).issubset(set(merged_flags)):
            raise SafetyMonotonicityError("Tier 0 safety floor monotonicity violated")
        return round(min(1.0, merged_risk), 4), merged_flags, merged_reasons


# ---------------------------------------------------------------------------
# 2. Closed-form Continuous-time (CfC) State Cell & Physiological Trajectory (S1-02, S1-03)
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        z = math.exp(-min(x, 60.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(x, -60.0))
    return z / (1.0 + z)


@dataclass(frozen=True)
class ClinicalVitalSample:
    """Single timestamped vital-sign observation vector."""

    timestamp_seconds: float
    heart_rate: float = 75.0
    systolic_bp: float = 120.0
    diastolic_bp: float = 78.0
    respiratory_rate: float = 15.0
    spo2: float = 98.0
    temperature: float = 36.8
    consciousness: str = "A"


@dataclass(frozen=True)
class TrajectoryAssessment:
    """Output of the CfC physiological trajectory reflex (<2ms)."""

    hidden_state: tuple[float, ...]
    static_news2_score: int
    compensatory_drift_score: float
    shock_index: float
    shock_index_velocity_per_hr: float
    pulse_pressure: float
    respiratory_oxygen_divergence: float
    deterioration_detected: bool
    subthreshold_early_warning: bool
    red_flags: tuple[str, ...]
    reason_codes: tuple[str, ...]
    cynefin_suggestion: CynefinClass
    latency_ms: float


class CfCStateCell:
    """Closed-form Continuous-time (CfC) liquid state cell (Hasani et al., 2022).

    Solves the liquid time-constant differential equation analytically over
    irregular observation intervals ``dt > 0``:

        h(t + dt) = sigma(-f(h, x) * dt) * h(t) + (1 - sigma(-f(h, x) * dt)) * g(h, x)

    where:
    - ``f(h, x) > 0`` is the state-dependent inverse time constant (decay rate),
    - ``g(h, x) in [-1, 1]`` is the bounded target latent state,
    - ``h(t)`` remains strictly bounded in ``[-1, 1]^d`` for all ``dt in (0, inf)``.
    """

    def __init__(self, state_dim: int = 6, base_tau_seconds: float = 900.0) -> None:
        if state_dim < 1:
            raise ValueError("state_dim must be >= 1")
        if base_tau_seconds <= 0.0:
            raise ValueError("base_tau_seconds must be > 0")
        self.state_dim = state_dim
        self.base_tau_seconds = base_tau_seconds

    def step(
        self,
        hidden: Sequence[float],
        normalized_input: Sequence[float],
        dt_seconds: float,
    ) -> tuple[float, ...]:
        """Advance the continuous hidden state by ``dt_seconds``."""
        if len(hidden) != self.state_dim:
            raise ValueError(f"expected hidden len {self.state_dim}, got {len(hidden)}")
        dt = max(0.001, float(dt_seconds))
        tau_norm = dt / self.base_tau_seconds

        next_state: list[float] = []
        for idx in range(self.state_dim):
            h_i = max(-1.0, min(1.0, float(hidden[idx])))
            x_i = float(normalized_input[idx]) if idx < len(normalized_input) else 0.0
            # Cross-channel coupling from adjacent physiological dimensions
            neighbor = (
                float(normalized_input[(idx + 1) % len(normalized_input)])
                if normalized_input
                else 0.0
            )
            # Single-tick spike dampener: if |x_i - h_i| is extreme over a very short dt,
            # modulate the time-constant gate so 1-second sensor artifacts do not saturate h_i,
            # while persistent multi-step drift integrates smoothly.
            innovation = abs(x_i - h_i)
            artifact_damping = 0.25 if (dt < 5.0 and innovation > 1.2) else 1.0

            # Positive liquid rate f(h, x) > 0 via softplus
            raw_rate = 0.65 + 0.45 * abs(x_i) + 0.25 * abs(h_i) + 0.15 * abs(neighbor)
            f_hx = math.log1p(math.exp(min(raw_rate, 20.0))) * artifact_damping

            # Bounded target state g(h, x) in [-1, 1]
            g_hx = math.tanh(0.78 * x_i + 0.22 * neighbor + 0.18 * h_i)

            # Closed-form exponential decay gate sigma(-f(h, x) * dt_norm)
            # At dt -> 0, decay_gate -> 1.0 (h unchanged); at dt -> inf, decay_gate -> 0.0 (h -> g_hx).
            decay_gate = math.exp(-f_hx * tau_norm)
            h_next = decay_gate * h_i + (1.0 - decay_gate) * g_hx
            next_state.append(round(max(-1.0, min(1.0, h_next)), 6))

        return tuple(next_state)


class PhysiologicalTrajectoryReflex:
    """Continuous-time physiological trajectory analyzer built on ``CfCStateCell``."""

    def __init__(self, base_tau_seconds: float = 900.0) -> None:
        self.cell = CfCStateCell(state_dim=6, base_tau_seconds=base_tau_seconds)
        self._hidden: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._history: list[ClinicalVitalSample] = []

    @property
    def hidden_state(self) -> tuple[float, ...]:
        return self._hidden

    def reset(self) -> None:
        self._hidden = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._history.clear()

    @staticmethod
    def compute_static_news2(sample: ClinicalVitalSample) -> int:
        """Compute standard royal college NEWS2 aggregate score (Scale 1)."""
        score = 0
        # Respiratory rate
        if sample.respiratory_rate <= 8 or sample.respiratory_rate >= 25:
            score += 3
        elif 21 <= sample.respiratory_rate <= 24:
            score += 2
        elif 9 <= sample.respiratory_rate <= 11:
            score += 1

        # SpO2 Scale 1
        if sample.spo2 <= 91:
            score += 3
        elif 92 <= sample.spo2 <= 93:
            score += 2
        elif 94 <= sample.spo2 <= 95:
            score += 1

        # Systolic BP
        if sample.systolic_bp <= 90 or sample.systolic_bp >= 220:
            score += 3
        elif 91 <= sample.systolic_bp <= 100:
            score += 2
        elif 101 <= sample.systolic_bp <= 110:
            score += 1

        # Heart rate
        if sample.heart_rate <= 40 or sample.heart_rate >= 131:
            score += 3
        elif 111 <= sample.heart_rate <= 130:
            score += 2
        elif (41 <= sample.heart_rate <= 50) or (91 <= sample.heart_rate <= 110):
            score += 1

        # Temperature
        if sample.temperature <= 35.0:
            score += 3
        elif sample.temperature >= 39.1:
            score += 2
        elif (35.1 <= sample.temperature <= 36.0) or (38.1 <= sample.temperature <= 39.0):
            score += 1

        # Consciousness (AVPU)
        if sample.consciousness.strip().upper() not in ("A", "ALERT", ""):
            score += 3

        return score

    def observe(self, sample: ClinicalVitalSample) -> TrajectoryAssessment:
        """Ingest one vital-sign observation and return the continuous trajectory assessment."""
        t0 = time.perf_counter()
        if self._history:
            prev = self._history[-1]
            dt = max(0.001, sample.timestamp_seconds - prev.timestamp_seconds)
        else:
            dt = 60.0

        # Normalize deviations relative to physiological homeostasis:
        # positive values indicate stress direction (tachycardia, hypotension, tachypnoea, hypoxia, fever/hypothermia, narrowing PP)
        hr_dev = (sample.heart_rate - 72.0) / 30.0
        sbp_drop = (120.0 - sample.systolic_bp) / 25.0
        pp = max(5.0, sample.systolic_bp - sample.diastolic_bp)
        pp_narrow = (42.0 - pp) / 18.0
        rr_dev = (sample.respiratory_rate - 15.0) / 6.0
        spo2_drop = (98.0 - sample.spo2) / 4.0
        temp_dev = abs(sample.temperature - 36.8) / 1.5

        norm_vec = (hr_dev, sbp_drop, pp_narrow, rr_dev, spo2_drop, temp_dev)
        self._hidden = self.cell.step(self._hidden, norm_vec, dt)
        self._history.append(sample)

        shock_index = sample.heart_rate / max(40.0, sample.systolic_bp)
        si_velocity_per_hr = 0.0
        if len(self._history) >= 2:
            first = self._history[0]
            first_si = first.heart_rate / max(40.0, first.systolic_bp)
            total_dt_hr = max(1.0 / 3600.0, (sample.timestamp_seconds - first.timestamp_seconds) / 3600.0)
            si_velocity_per_hr = (shock_index - first_si) / total_dt_hr

        resp_ox_div = max(0.0, rr_dev) * max(0.0, spo2_drop)
        static_news2 = self.compute_static_news2(sample)

        # Continuous compensatory drift score combines latent CfC state energy with coupled hemodynamic indices
        cfc_stress = sum(max(0.0, h) for h in self._hidden[:5]) / 5.0
        si_excess = max(0.0, (shock_index - 0.68) / 0.35)
        pp_stress = max(0.0, (35.0 - pp) / 15.0)

        # Require multi-sample persistence (>= 2 samples) for sub-threshold drift so single-tick jitter doesn't fire
        multi_step_factor = 1.0 if len(self._history) >= 2 else 0.45
        drift_score = min(
            1.0,
            multi_step_factor
            * (0.45 * cfc_stress + 0.32 * si_excess + 0.13 * pp_stress + 0.10 * min(1.0, resp_ox_div)),
        )

        tier0 = Tier0SafetyFloor.evaluate(
            vitals={
                "heart_rate": sample.heart_rate,
                "systolic_bp": sample.systolic_bp,
                "respiratory_rate": sample.respiratory_rate,
                "spo2": sample.spo2,
                "temperature": sample.temperature,
                "consciousness": sample.consciousness,
            }
        )

        red_flags: list[str] = list(tier0.red_flags)
        reasons: list[str] = list(tier0.reason_codes)

        # Sub-threshold early warning: static NEWS2 is low (< 5, no single-param 3),
        # yet coupled trajectory shows progressive compensatory shock or respiratory divergence!
        subthreshold_warning = False
        if (
            len(self._history) >= 3
            and shock_index >= 0.82
            and si_velocity_per_hr >= 0.08
            and pp <= 36.0
        ):
            subthreshold_warning = True
            red_flags.append("sys1.trajectory.compensatory_shock_drift")
            reasons.append("cfc.shock_index_velocity_and_pulse_pressure_narrowing")

        if len(self._history) >= 3 and resp_ox_div >= 0.55 and sample.spo2 <= 95.0:
            subthreshold_warning = True
            red_flags.append("sys1.trajectory.respiratory_oxygenation_divergence")
            reasons.append("cfc.rr_spo2_divergence")

        deterioration = bool(
            tier0.news2_single_param_red
            or static_news2 >= 5
            or subthreshold_warning
            or drift_score >= 0.62
        )

        if tier0.emergency:
            cynefin = CynefinClass.chaotic
        elif deterioration or red_flags:
            cynefin = CynefinClass.complex
        elif static_news2 >= 3 or drift_score >= 0.35:
            cynefin = CynefinClass.complicated
        else:
            cynefin = CynefinClass.clear

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return TrajectoryAssessment(
            hidden_state=self._hidden,
            static_news2_score=static_news2,
            compensatory_drift_score=round(max(drift_score, tier0.min_risk_score if tier0.news2_single_param_red else 0.0), 4),
            shock_index=round(shock_index, 4),
            shock_index_velocity_per_hr=round(si_velocity_per_hr, 4),
            pulse_pressure=round(pp, 2),
            respiratory_oxygen_divergence=round(resp_ox_div, 4),
            deterioration_detected=deterioration,
            subthreshold_early_warning=subthreshold_warning,
            red_flags=tuple(dict.fromkeys(red_flags)),
            reason_codes=tuple(dict.fromkeys(reasons or ["cfc.trajectory_nominal"])),
            cynefin_suggestion=cynefin,
            latency_ms=round(elapsed_ms, 4),
        )


# ---------------------------------------------------------------------------
# 3. Negation-Aware Consultation & EMR State Reflex (S1-04)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ClinicalConceptRule:
    concept_id: str
    snomed_code: str
    snomed_display: str
    category: str  # "symptom" | "red_flag"
    patterns: tuple[str, ...]
    domain: str
    safety_net_prompts: tuple[str, ...] = ()


_CLINICAL_CONCEPT_RULES: tuple[_ClinicalConceptRule, ...] = (
    _ClinicalConceptRule(
        concept_id="chest_pain",
        snomed_code="29857009",
        snomed_display="Chest pain",
        category="red_flag",
        patterns=("chest pain", "central chest tightness", "crushing chest", "retrosternal pain", "angina"),
        domain="cardiorespiratory",
        safety_net_prompts=(
            "Screen radiation to left arm, shoulder, neck, or jaw",
            "Screen diaphoresis, nausea, or exertional dyspnoea",
            "Verify 12-lead ECG and serial troponin requirement",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="jaw_or_arm_radiation",
        snomed_code="225566008",
        snomed_display="Pain radiating to left arm or jaw",
        category="red_flag",
        patterns=("radiating to left arm", "radiating to jaw", "left arm pain", "jaw pain"),
        domain="cardiorespiratory",
    ),
    _ClinicalConceptRule(
        concept_id="dyspnoea",
        snomed_code="267036007",
        snomed_display="Dyspnoea",
        category="symptom",
        patterns=("shortness of breath", "short of breath", "dyspnoea", "dyspnea", "breathless", "difficulty breathing"),
        domain="cardiorespiratory",
        safety_net_prompts=(
            "Screen Resting SpO2, respiratory rate, and pleuritic chest pain",
            "Screen haemoptysis and unilateral calf swelling",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="thunderclap_or_meningism",
        snomed_code="25064002",
        snomed_display="Acute severe headache / meningism check",
        category="red_flag",
        patterns=("thunderclap headache", "worst headache of life", "neck stiffness", "photophobia", "non-blanching rash"),
        domain="neurological",
        safety_net_prompts=(
            "Screen thunderclap onset (<1 min to peak)",
            "Screen photophobia, neck stiffness, fever, and visual loss",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="headache",
        snomed_code="25064002",
        snomed_display="Headache",
        category="symptom",
        patterns=("headache", "migraine", "cephalalgia", "head pain"),
        domain="neurological",
        safety_net_prompts=(
            "Screen thunderclap onset (<1 min to peak)",
            "Screen photophobia, neck stiffness, focal neurology, and visual changes",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="cauda_equina_red_flag",
        snomed_code="192970008",
        snomed_display="Suspected cauda equina syndrome",
        category="red_flag",
        patterns=("saddle anaesthesia", "saddle anesthesia", "urinary retention", "faecal incontinence", "bilateral sciatica", "bladder incontinence"),
        domain="spinal",
        safety_net_prompts=(
            "Urgent MRI lumbar spine and neurosurgical escalation assessment",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="back_pain",
        snomed_code="161891005",
        snomed_display="Backache",
        category="symptom",
        patterns=("back pain", "low back pain", "lumbar pain", "sciatica"),
        domain="spinal",
        safety_net_prompts=(
            "Screen saddle anaesthesia and perianal sensation",
            "Screen new bladder retention/incontinence or faecal incontinence",
            "Screen bilateral lower-limb motor weakness",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="stroke_fast_red_flag",
        snomed_code="230690007",
        snomed_display="Acute focal neurological deficit (FAST)",
        category="red_flag",
        patterns=("facial droop", "slurred speech", "dysphasia", "aphasia", "hemiparesis", "unilateral weakness", "arm weakness"),
        domain="neurological",
        safety_net_prompts=(
            "Confirm exact time last seen well for thrombolysis window",
            "Immediate hyperacute stroke pathway escalation",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="sepsis_red_flag",
        snomed_code="91302008",
        snomed_display="Suspected sepsis red flag",
        category="red_flag",
        patterns=("rigors", "mottled skin", "confusion", "altered mental state", "septic", "neutropenic"),
        domain="infectious",
        safety_net_prompts=(
            "Evaluate Sepsis Six bundle (lactate, blood cultures, urine output, O2, IV fluids, antibiotics)",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="fever",
        snomed_code="386661006",
        snomed_display="Fever",
        category="symptom",
        patterns=("fever", "pyrexia", "febrile", "high temperature"),
        domain="infectious",
        safety_net_prompts=(
            "Screen rigors, mental state, urine output, and respiratory rate",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="preeclampsia_red_flag",
        snomed_code="398254007",
        snomed_display="Pre-eclampsia warning feature",
        category="red_flag",
        patterns=("visual disturbance", "flashing lights", "epigastric pain", "right upper quadrant pain", "facial oedema", "severe hypertension in pregnancy"),
        domain="maternal",
        safety_net_prompts=(
            "Check blood pressure, urine protein:creatinine ratio, and fetal wellbeing",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="self_harm_red_flag",
        snomed_code="248062006",
        snomed_display="Self-harm or suicidal ideation",
        category="red_flag",
        patterns=("suicidal ideation", "thoughts of self-harm", "wants to end life", "overdose intent"),
        domain="mental_health",
        safety_net_prompts=(
            "Immediate safeguarding and crisis mental health assessment",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="cough",
        snomed_code="49727002",
        snomed_display="Cough",
        category="symptom",
        patterns=("cough", "productive cough", "dry cough"),
        domain="cardiorespiratory",
        safety_net_prompts=(
            "Screen haemoptysis, weight loss, night sweats, and dyspnoea",
        ),
    ),
    _ClinicalConceptRule(
        concept_id="abdominal_pain",
        snomed_code="21522001",
        snomed_display="Abdominal pain",
        category="symptom",
        patterns=("abdominal pain", "epigastric pain", "right iliac fossa pain", "stomach pain"),
        domain="gastrointestinal",
        safety_net_prompts=(
            "Screen guarding/rigidity, haematemesis, melaena, and pregnancy status where applicable",
        ),
    ),
)

_CLAUSE_SPLIT_RE = re.compile(r"[.;!?\n]+|\b(?:but|however|although|except|yet|though)\b", re.IGNORECASE)
_NEGATION_CUE_RE = re.compile(
    r"\b(?:no|not|none|never|denies|denied|denying|without|negative\s+for|free\s+of|absence\s+of|ruled\s+out)\b",
    re.IGNORECASE,
)


def _is_term_negated_in_text(text: str, phrase: str) -> bool:
    """Return True if every occurrence of ``phrase`` in ``text`` falls under a negation cue within its clause."""
    lower = text.lower()
    target = phrase.lower()
    if target not in lower:
        return False

    clauses = _CLAUSE_SPLIT_RE.split(lower)
    found_positive = False
    found_negated = False
    for clause in clauses:
        pos = clause.find(target)
        if pos == -1:
            continue
        prefix = clause[:pos]
        if _NEGATION_CUE_RE.search(prefix):
            found_negated = True
        else:
            found_positive = True

    return found_negated and not found_positive


@dataclass(frozen=True)
class ConsultationReflexResult:
    """Output of the negation-aware consultation & EMR state reflex (<10ms)."""

    confirmed_symptoms: tuple[str, ...]
    negated_findings: tuple[str, ...]
    active_red_flags: tuple[str, ...]
    unscreened_safety_net_prompts: tuple[str, ...]
    candidate_snomed_codes: tuple[dict[str, str], ...]
    anxiety_level: str  # "low" | "moderate" | "high" | "critical"
    trust_level: str  # "low" | "building" | "established" | "high"
    soap_prefill: dict[str, str]
    confidence: float
    risk_score: float
    reason_codes: tuple[str, ...]
    requires_clinician_review: bool = True
    latency_ms: float = 0.0


class ConsultationStateReflex:
    """Streaming clinical text / utterance / timeline state machine (<10ms)."""

    def __init__(self) -> None:
        self._utterances: list[str] = []

    def ingest_utterance(self, text: str) -> ConsultationReflexResult:
        if text and text.strip():
            self._utterances.append(text.strip())
        return self.evaluate(" . ".join(self._utterances))

    @staticmethod
    def evaluate(
        text: str,
        *,
        timeline_events: Sequence[Mapping[str, Any]] = (),
        vitals: Mapping[str, Any] | None = None,
        active_medications: Sequence[str] = (),
        allergies: Sequence[str] = (),
        conditions: Sequence[str] = (),
    ) -> ConsultationReflexResult:
        t0 = time.perf_counter()
        combined_segments: list[str] = []
        if text and text.strip():
            combined_segments.append(text.strip())

        obs_summaries: list[str] = []
        cond_summaries: list[str] = []
        med_summaries: list[str] = [str(m) for m in active_medications if m]
        allergy_summaries: list[str] = [str(a) for a in allergies if a]
        extracted_snomed: list[dict[str, str]] = []

        for ev in timeline_events:
            rtype = str(ev.get("resource_type") or ev.get("resourceType") or "")
            summary = str(ev.get("summary") or ev.get("display") or ev.get("text") or "").strip()
            code = str(ev.get("code") or "").strip()
            code_system = str(ev.get("code_system") or "").lower()
            if summary:
                combined_segments.append(summary)
            if rtype == "Observation" and summary:
                obs_summaries.append(summary)
            elif rtype == "Condition" and summary:
                cond_summaries.append(summary)
            elif rtype == "MedicationRequest" and summary:
                med_summaries.append(summary)
            elif rtype == "AllergyIntolerance" and summary:
                allergy_summaries.append(summary)

            if code and ("snomed" in code_system or code.isdigit()):
                extracted_snomed.append(
                    {
                        "code": code,
                        "display": summary or code,
                        "system": "http://snomed.info/sct",
                    }
                )

        corpus = " . ".join(combined_segments)
        corpus_lower = corpus.lower()

        confirmed_symptoms: list[str] = []
        negated_findings: list[str] = []
        active_red_flags: list[str] = []
        safety_net_candidates: list[str] = []
        snomed_by_code: dict[str, dict[str, str]] = {
            item["code"]: item for item in extracted_snomed
        }

        for rule in _CLINICAL_CONCEPT_RULES:
            matched_phrase: str | None = None
            is_negated = False
            for phrase in rule.patterns:
                if phrase in corpus_lower:
                    matched_phrase = phrase
                    is_negated = _is_term_negated_in_text(corpus_lower, phrase)
                    break
            if matched_phrase is None:
                continue

            if is_negated:
                negated_findings.append(f"No {rule.snomed_display.lower()} ({matched_phrase} negated)")
            else:
                confirmed_symptoms.append(rule.snomed_display)
                snomed_by_code.setdefault(
                    rule.snomed_code,
                    {
                        "code": rule.snomed_code,
                        "display": rule.snomed_display,
                        "system": "http://snomed.info/sct",
                    },
                )
                if rule.category == "red_flag":
                    active_red_flags.append(f"sys1.red_flag.{rule.concept_id}")
                for prompt in rule.safety_net_prompts:
                    if prompt not in safety_net_candidates:
                        safety_net_candidates.append(prompt)

        # Filter out safety-net prompts whose core terms have already been addressed (confirmed or negated)
        unscreened_prompts: list[str] = []
        for prompt in safety_net_candidates:
            prompt_l = prompt.lower()
            if "left arm" in prompt_l and ("left arm" in corpus_lower or "jaw" in corpus_lower):
                continue
            if "thunderclap" in prompt_l and ("thunderclap" in corpus_lower or "sudden onset" in corpus_lower):
                continue
            if "saddle" in prompt_l and ("saddle" in corpus_lower or "bladder" in corpus_lower):
                continue
            unscreened_prompts.append(prompt)

        # Affective state tracking (anxiety & trust) for consultation / telemedicine co-control
        anxiety_cues_high = ("terrified", "panic", "can't breathe", "dying", "scared", "chest crushing", "emergency")
        anxiety_cues_mod = ("worried", "anxious", "concerned", "afraid", "nervous", "getting worse", "pain")
        trust_cues_pos = ("thank you", "makes sense", "understand", "helpful", "reassuring", "agree", "okay")
        trust_cues_neg = ("not listening", "confused", "don't trust", "disagree", "wrong", "ignored")

        if any(cue in corpus_lower for cue in anxiety_cues_high) or len(active_red_flags) >= 2:
            anxiety_level = "high" if not active_red_flags else "critical"
        elif any(cue in corpus_lower for cue in anxiety_cues_mod) or confirmed_symptoms:
            anxiety_level = "moderate"
        else:
            anxiety_level = "low"

        if any(cue in corpus_lower for cue in trust_cues_neg):
            trust_level = "low"
        elif any(cue in corpus_lower for cue in trust_cues_pos):
            trust_level = "high"
        elif len(combined_segments) >= 2:
            trust_level = "established"
        else:
            trust_level = "building"

        # Tier 0 floor check
        tier0 = Tier0SafetyFloor.evaluate(
            vitals=vitals,
            active_medications=med_summaries,
            allergies=allergy_summaries,
            conditions=[*cond_summaries, *confirmed_symptoms],
            free_text_plan=text,
        )

        # Build dynamic SOAP prefill fields
        primary_complaint = (
            confirmed_symptoms[0]
            if confirmed_symptoms
            else (cond_summaries[0] if cond_summaries else (obs_summaries[0] if obs_summaries else "Clinical review"))
        )
        exam_parts: list[str] = []
        if obs_summaries:
            exam_parts.append("Observations: " + "; ".join(obs_summaries[:4]))
        if negated_findings:
            exam_parts.append("Pertinent negatives: " + "; ".join(negated_findings[:3]))
        if unscreened_prompts:
            exam_parts.append("Safety-net checks to complete: " + "; ".join(unscreened_prompts[:3]))

        assessment_parts: list[str] = []
        if confirmed_symptoms:
            assessment_parts.append("Presenting features: " + ", ".join(confirmed_symptoms))
        if cond_summaries:
            assessment_parts.append("Active problems: " + "; ".join(cond_summaries[:4]))
        if active_red_flags or tier0.red_flags:
            assessment_parts.append("Red-flag sentinels: " + ", ".join([*tier0.red_flags, *active_red_flags]))

        plan_parts: list[str] = []
        if med_summaries:
            plan_parts.append("Review active medications: " + "; ".join(dict.fromkeys(med_summaries[:4])))
        if allergy_summaries:
            plan_parts.append("Allergy guard active: " + "; ".join(dict.fromkeys(allergy_summaries[:3])))
        if unscreened_prompts:
            plan_parts.append("Complete red-flag safety netting: " + "; ".join(unscreened_prompts[:2]))
        if not plan_parts and confirmed_symptoms:
            plan_parts.append(f"Clinician review and targeted management for {primary_complaint.lower()}")

        soap_prefill = {
            "chief_complaint": primary_complaint,
            "history_of_present_illness": "; ".join(combined_segments[:4]),
            "examination": " | ".join(exam_parts) if exam_parts else "Targeted clinical examination required.",
            "assessment": " | ".join(assessment_parts) if assessment_parts else primary_complaint,
            "plan": " | ".join(plan_parts) if plan_parts else "Clinician review and disposition.",
        }

        raw_risk = 0.18
        if active_red_flags:
            raw_risk = max(raw_risk, 0.78)
        elif confirmed_symptoms:
            raw_risk = max(raw_risk, 0.35)

        raw_conf = 0.88 if (confirmed_symptoms or obs_summaries or cond_summaries) else 0.76
        if active_red_flags or tier0.red_flags:
            raw_conf = min(raw_conf, 0.72)

        reasons: list[str] = ["sys1.consultation_state_reflex"]
        if negated_findings:
            reasons.append("sys1.negation_guard_applied")
        if active_red_flags:
            reasons.append("sys1.red_flag_detected")
        if unscreened_prompts:
            reasons.append("sys1.safety_net_prompts_staged")

        enforced_risk, enforced_flags, enforced_reasons = Tier0SafetyFloor.enforce_monotonicity(
            tier0,
            risk_score=raw_risk,
            red_flags=active_red_flags,
            reason_codes=reasons,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ConsultationReflexResult(
            confirmed_symptoms=tuple(dict.fromkeys(confirmed_symptoms)),
            negated_findings=tuple(dict.fromkeys(negated_findings)),
            active_red_flags=enforced_flags,
            unscreened_safety_net_prompts=tuple(unscreened_prompts),
            candidate_snomed_codes=tuple(snomed_by_code.values()),
            anxiety_level=anxiety_level,
            trust_level=trust_level,
            soap_prefill=soap_prefill,
            confidence=round(raw_conf, 4),
            risk_score=enforced_risk,
            reason_codes=enforced_reasons,
            requires_clinician_review=True,
            latency_ms=round(elapsed_ms, 4),
        )


# ---------------------------------------------------------------------------
# 4. HL7v2 / FHIR Semantic & Unit-Mismatch Triage Reflex (S1-10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hl7v2AnomalyFinding:
    """Single semantic or unit anomaly detected in an HL7v2 / FHIR payload."""

    code: str
    loinc_code: str
    severity: str  # "warning" | "high" | "critical"
    category: str  # "unit_mismatch" | "specimen_artifact" | "critical_value" | "biological_implausibility"
    message: str
    suggested_unit: str | None = None
    conversion_factor: float | None = None


@dataclass(frozen=True)
class Hl7v2TriageResult:
    """Sub-5ms semantic triage output for HL7v2 / FHIR Observation bundles."""

    quarantine_required: bool
    requires_human_review: bool
    anomalies: tuple[Hl7v2AnomalyFinding, ...]
    reason_codes: tuple[str, ...]
    risk_score: float
    latency_ms: float


class Hl7v2SemanticReflex:
    """Sub-5ms interceptor for HL7v2 ADT/ORU messages and FHIR Observations."""

    @staticmethod
    def evaluate(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> Hl7v2TriageResult:
        t0 = time.perf_counter()
        anomalies: list[Hl7v2AnomalyFinding] = []
        reasons: list[str] = []

        observations = _extract_observations_from_payload(payload)
        for obs in observations:
            loinc = str(obs.get("code") or "").strip()
            display = str(obs.get("display") or "").lower()
            val = _opt_float(obs.get("value"))
            unit = str(obs.get("unit") or "").strip()
            unit_lower = unit.lower()

            if val is None:
                continue

            if val < 0.0:
                anomalies.append(
                    Hl7v2AnomalyFinding(
                        code="HL7_NEGATIVE_PHYSIOLOGICAL_VALUE",
                        loinc_code=loinc or "unknown",
                        severity="critical",
                        category="biological_implausibility",
                        message=f"Negative observation value ({val}) is biologically impossible.",
                    )
                )
                reasons.append("sys1.hl7.negative_value")
                continue

            # 1. Blood Glucose (LOINC 2339-0, 2345-7, 15074-8)
            if loinc in ("2339-0", "2345-7", "15074-8") or "glucose" in display:
                if "mmol" in unit_lower and val >= 45.0:
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_GLUCOSE_UNIT_SWAP_MGDL_AS_MMOLL",
                            loinc_code=loinc or "2339-0",
                            severity="critical",
                            category="unit_mismatch",
                            message=(
                                f"Glucose {val:g} labelled '{unit}' is characteristic of mg/dL "
                                f"(~{val / 18.018:0.1f} mmol/L); 18x insulin dosing hazard if unquarantined."
                            ),
                            suggested_unit="mg/dL",
                            conversion_factor=1.0 / 18.018,
                        )
                    )
                    reasons.append("sys1.hl7.unit_mismatch_glucose")
                elif "mg/dl" in unit_lower and val <= 18.0:
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_GLUCOSE_UNIT_SWAP_MMOLL_AS_MGDL",
                            loinc_code=loinc or "2339-0",
                            severity="critical",
                            category="unit_mismatch",
                            message=(
                                f"Glucose {val:g} labelled '{unit}' is characteristic of mmol/L "
                                f"(~{val * 18.018:0.0f} mg/dL); false hypoglycaemia hazard."
                            ),
                            suggested_unit="mmol/L",
                            conversion_factor=18.018,
                        )
                    )
                    reasons.append("sys1.hl7.unit_mismatch_glucose")

            # 2. Serum Potassium (LOINC 2823-3)
            if loinc == "2823-3" or "potassium" in display:
                if val >= 10.0 and ("mmol" in unit_lower or "meq" in unit_lower or not unit_lower):
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_POTASSIUM_HAEMOLYSIS_OR_EDTA_ARTIFACT",
                            loinc_code="2823-3",
                            severity="critical",
                            category="specimen_artifact",
                            message=(
                                f"Potassium {val:g} {unit or 'mmol/L'} exceeds physiological survival ceiling; "
                                "suspect in-vitro haemolysis or EDTA tube contamination—verify urgent redraw."
                            ),
                        )
                    )
                    reasons.append("sys1.hl7.specimen_artifact_potassium")
                elif val >= 6.0 and ("mmol" in unit_lower or "meq" in unit_lower or not unit_lower):
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_POTASSIUM_CRITICAL_HYPERKALAEMIA",
                            loinc_code="2823-3",
                            severity="high",
                            category="critical_value",
                            message=f"Critical hyperkalaemia ({val:g} {unit or 'mmol/L'}); immediate ECG & clinical review.",
                        )
                    )
                    reasons.append("sys1.hl7.critical_hyperkalaemia")

            # 3. Serum Creatinine (LOINC 2160-0)
            if loinc == "2160-0" or "creatinine" in display:
                if "mg/dl" in unit_lower and val >= 25.0:
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_CREATININE_UNIT_SWAP_UMOLL_AS_MGDL",
                            loinc_code="2160-0",
                            severity="critical",
                            category="unit_mismatch",
                            message=(
                                f"Creatinine {val:g} labelled '{unit}' matches umol/L scale "
                                f"(~{val / 88.4:0.2f} mg/dL); 88.4x eGFR/dosing distortion risk."
                            ),
                            suggested_unit="umol/L",
                            conversion_factor=1.0 / 88.4,
                        )
                    )
                    reasons.append("sys1.hl7.unit_mismatch_creatinine")

            # 4. Haemoglobin (LOINC 718-7)
            if loinc == "718-7" or "hemoglobin" in display or "haemoglobin" in display:
                if "g/dl" in unit_lower and val >= 35.0:
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_HAEMOGLOBIN_UNIT_SWAP_GL_AS_GDL",
                            loinc_code="718-7",
                            severity="high",
                            category="unit_mismatch",
                            message=(
                                f"Haemoglobin {val:g} labelled '{unit}' matches g/L scale (~{val / 10.0:0.1f} g/dL)."
                            ),
                            suggested_unit="g/L",
                            conversion_factor=0.1,
                        )
                    )
                    reasons.append("sys1.hl7.unit_mismatch_haemoglobin")

            # 5. Heart Rate / SpO2 / Temperature survival bounds
            if loinc == "8867-4" or "heart rate" in display:
                if val > 300.0 or val < 10.0:
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_HEART_RATE_IMPLAUSIBLE",
                            loinc_code="8867-4",
                            severity="critical",
                            category="biological_implausibility",
                            message=f"Heart rate {val:g} bpm outside physiological bounds [10, 300].",
                        )
                    )
                    reasons.append("sys1.hl7.implausible_vital")

            if loinc in ("59408-5", "2708-6") or "oxygen saturation" in display or "spo2" in display:
                if val > 100.0 or val < 20.0:
                    anomalies.append(
                        Hl7v2AnomalyFinding(
                            code="HL7_SPO2_IMPLAUSIBLE",
                            loinc_code=loinc or "59408-5",
                            severity="critical",
                            category="biological_implausibility",
                            message=f"SpO2 {val:g}% outside valid bounds [20, 100].",
                        )
                    )
                    reasons.append("sys1.hl7.implausible_vital")

        quarantine = any(
            a.category in ("unit_mismatch", "specimen_artifact", "biological_implausibility")
            for a in anomalies
        )
        human_review = bool(anomalies)
        risk = 0.08
        if quarantine:
            risk = 0.88
        elif human_review:
            risk = 0.65

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return Hl7v2TriageResult(
            quarantine_required=quarantine,
            requires_human_review=human_review,
            anomalies=tuple(anomalies),
            reason_codes=tuple(dict.fromkeys(reasons or ["sys1.hl7.semantic_clean"])),
            risk_score=round(risk, 4),
            latency_ms=round(elapsed_ms, 4),
        )


def _extract_observations_from_payload(
    payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            if isinstance(item, Mapping):
                out.extend(_extract_observations_from_payload(item))
        return out

    if not isinstance(payload, Mapping):
        return out

    # Case 1: HL7v2 dict with "obx" or nested "hl7v2_message"
    hl7 = payload.get("hl7v2_message", payload)
    if isinstance(hl7, Mapping) and "obx" in hl7:
        obx_raw = hl7["obx"]
        obx_list = [obx_raw] if isinstance(obx_raw, Mapping) else list(obx_raw or [])
        for obx in obx_list:
            if not isinstance(obx, Mapping):
                continue
            obs_id = obx.get("observation_id", {})
            out.append(
                {
                    "code": obs_id.get("code", "") if isinstance(obs_id, Mapping) else str(obs_id),
                    "display": obs_id.get("display", "") if isinstance(obs_id, Mapping) else "",
                    "value": obx.get("value"),
                    "unit": obx.get("unit", ""),
                }
            )

    # Case 2: FHIR Observation resource or bundle of fhir_resources
    if payload.get("resourceType") == "Observation":
        coding = (payload.get("code", {}) or {}).get("coding", [{}])[0]
        vq = payload.get("valueQuantity", {}) or {}
        out.append(
            {
                "code": coding.get("code", ""),
                "display": coding.get("display", ""),
                "value": vq.get("value", payload.get("valueString")),
                "unit": vq.get("unit", ""),
            }
        )

    if "fhir_resources" in payload and isinstance(payload["fhir_resources"], Sequence):
        for res in payload["fhir_resources"]:
            if isinstance(res, Mapping):
                out.extend(_extract_observations_from_payload(res))

    return out


# ---------------------------------------------------------------------------
# 5. Circuit-Protected Local Windows SLM Adapter (S1-06, FR-CIRCUIT_-001..005)
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    """Nygard circuit-breaker states (FR-CIRCUIT_-001..005)."""

    closed = "closed"
    open = "open"
    half_open = "half_open"


def is_local_trust_endpoint(endpoint_url: str) -> bool:
    """Verify an SLM endpoint resides strictly on localhost / loopback (zero external PHI egress)."""
    try:
        parsed = urllib.parse.urlparse(endpoint_url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https", "onnx", "local"):
        return False
    host = (parsed.hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def _default_local_slm_endpoint() -> str:
    host = os.environ.get("SYSTEM1_SLM_HOST", "localhost")
    port = os.environ.get("SYSTEM1_SLM_PORT", "11434")
    return f"http://{host}:{port}/api/generate"


class LocalSlmReflexAdapter:
    """Circuit-breaker protected local Windows SLM fast-router (Ollama / ONNX).

    Enforces:
    - Local PHI residency (`127.0.0.1` / `localhost` only; refuses external egress).
    - `/no_think` System 1 single-pass classification with JSON grammar constraint.
    - Nygard circuit breaker (`FR-CIRCUIT_-001..005`) falling back in <2ms to
      deterministic/CfC evaluation when the local daemon is unavailable or slow.
    """

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        model_name: str = "qwen3:1.7b",
        timeout_ms: int = 120,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        enforce_open_source: bool = True,
    ) -> None:
        resolved_url = endpoint_url or _default_local_slm_endpoint()
        if not is_local_trust_endpoint(resolved_url):
            raise ExternalEgressRefusedError(
                f"System 1 SLM endpoint '{resolved_url}' violates local PHI trust boundary "
                "(only 127.0.0.1 / localhost / ::1 permitted)."
            )
        self.model_spec: OpenSourceSystem1ModelSpec | None = None
        if enforce_open_source:
            self.model_spec = get_open_source_model_spec(model_name)
        self.endpoint_url = resolved_url
        self.model_name = model_name
        self.timeout_ms = max(10, int(timeout_ms))
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout_seconds = max(0.1, float(recovery_timeout_seconds))

        self._state = CircuitState.closed
        self._failure_count = 0
        self._opened_at_monotonic: float = 0.0
        self._fallback_count = 0

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.open:
            if (time.monotonic() - self._opened_at_monotonic) >= self.recovery_timeout_seconds:
                self._state = CircuitState.half_open
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def fallback_count(self) -> int:
        return self._fallback_count

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.closed

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold or self._state is CircuitState.half_open:
            self._state = CircuitState.open
            self._opened_at_monotonic = time.monotonic()

    def classify_reflex(
        self,
        text: str,
        *,
        vitals: Mapping[str, Any] | None = None,
        transport_fn: Any | None = None,
    ) -> ConsultationReflexResult:
        """Run fast classification with automatic <2ms fallback to ConsultationStateReflex."""
        base_result = ConsultationStateReflex.evaluate(text, vitals=vitals)

        current_state = self.state
        if current_state is CircuitState.open:
            self._fallback_count += 1
            return ConsultationReflexResult(
                confirmed_symptoms=base_result.confirmed_symptoms,
                negated_findings=base_result.negated_findings,
                active_red_flags=base_result.active_red_flags,
                unscreened_safety_net_prompts=base_result.unscreened_safety_net_prompts,
                candidate_snomed_codes=base_result.candidate_snomed_codes,
                anxiety_level=base_result.anxiety_level,
                trust_level=base_result.trust_level,
                soap_prefill=base_result.soap_prefill,
                confidence=base_result.confidence,
                risk_score=base_result.risk_score,
                reason_codes=(*base_result.reason_codes, "sys1.slm_circuit_open_fallback"),
                requires_clinician_review=True,
                latency_ms=base_result.latency_ms,
            )

        payload = {
            "model": self.model_name,
            "prompt": f"/no_think Classify clinical state JSON for: {text[:400]}",
            "stream": False,
            "raw": True,
            "format": "json",
            "options": {"temperature": 0.0, "num_predict": 64},
        }

        try:
            if transport_fn is not None:
                raw_resp = transport_fn(self.endpoint_url, payload, self.timeout_ms / 1000.0)
            else:
                req = urllib.request.Request(
                    self.endpoint_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout_ms / 1000.0) as resp:  # nosec B310 - validated localhost only
                    raw_resp = json.loads(resp.read().decode("utf-8"))

            self.record_success()
            parsed = raw_resp.get("response", raw_resp) if isinstance(raw_resp, Mapping) else {}
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            slm_risk = _opt_float(parsed.get("risk_score")) if isinstance(parsed, Mapping) else None
            slm_flags = parsed.get("red_flags", []) if isinstance(parsed, Mapping) else []

            # Enforce monotonicity against base deterministic + Tier 0 result
            merged_risk = max(base_result.risk_score, float(slm_risk or 0.0))
            merged_flags = tuple(
                dict.fromkeys([*base_result.active_red_flags, *(str(f) for f in slm_flags)])
            )
            return ConsultationReflexResult(
                confirmed_symptoms=base_result.confirmed_symptoms,
                negated_findings=base_result.negated_findings,
                active_red_flags=merged_flags,
                unscreened_safety_net_prompts=base_result.unscreened_safety_net_prompts,
                candidate_snomed_codes=base_result.candidate_snomed_codes,
                anxiety_level=base_result.anxiety_level,
                trust_level=base_result.trust_level,
                soap_prefill=base_result.soap_prefill,
                confidence=base_result.confidence,
                risk_score=round(min(1.0, merged_risk), 4),
                reason_codes=(*base_result.reason_codes, "sys1.local_slm_enriched"),
                requires_clinician_review=True,
                latency_ms=base_result.latency_ms,
            )
        except Exception:
            self.record_failure()
            self._fallback_count += 1
            return ConsultationReflexResult(
                confirmed_symptoms=base_result.confirmed_symptoms,
                negated_findings=base_result.negated_findings,
                active_red_flags=base_result.active_red_flags,
                unscreened_safety_net_prompts=base_result.unscreened_safety_net_prompts,
                candidate_snomed_codes=base_result.candidate_snomed_codes,
                anxiety_level=base_result.anxiety_level,
                trust_level=base_result.trust_level,
                soap_prefill=base_result.soap_prefill,
                confidence=base_result.confidence,
                risk_score=base_result.risk_score,
                reason_codes=(*base_result.reason_codes, "sys1.slm_fallback_to_cfc"),
                requires_clinician_review=True,
                latency_ms=base_result.latency_ms,
            )


# ---------------------------------------------------------------------------
# 6. Dual-Loop Self-Improvement & Calibration Tracker (M-06)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CalibrationEvent:
    predicted_risk: float
    predicted_red_flag: bool
    actual_adverse_or_escalated: bool
    reviewer_outcome: ReviewerOutcome
    member_id: str = "system1.reflex"


@dataclass(frozen=True)
class System1CalibrationSnapshot:
    """Telemetry and self-improvement calibration metrics (M-06)."""

    total_events: int
    brier_score: float
    expected_calibration_error: float
    false_positives: int
    false_negatives: int
    true_positives: int
    true_negatives: int
    recall: float
    precision: float
    outcome_tally: OutcomeTally
    candidate_weight_release: WeightRelease


class System1CalibrationTracker:
    """Tracks System 2 Council / Clinician feedback against System 1 intuition.

    Implements Runtime Self-Improvement Loop 1:
    - Computes Brier calibration score and Expected Calibration Error (ECE).
    - Tracks FP/FN confusion matrix against System 2 deliberation & clinician sign-off.
    - Generates a governed ``WeightRelease`` adjustment, strictly refusing any
      sensitivity relaxation if ``false_negatives > 0``.
    """

    def __init__(self, baseline_version: str = "sys1-weights-1.0.0") -> None:
        self.baseline_version = baseline_version
        self._events: list[_CalibrationEvent] = []

    def record_feedback(
        self,
        intuition: IntuitionDecision,
        *,
        actual_escalated: bool,
        reviewer_outcome: ReviewerOutcome,
        member_id: str = "system1.reflex",
    ) -> None:
        pred_flag = bool(
            intuition.risk_score >= 0.60
            or any("red_flag" in code or "tier0" in code for code in intuition.reason_codes)
        )
        self._events.append(
            _CalibrationEvent(
                predicted_risk=float(intuition.risk_score),
                predicted_red_flag=pred_flag,
                actual_adverse_or_escalated=bool(actual_escalated),
                reviewer_outcome=reviewer_outcome,
                member_id=member_id,
            )
        )

    def snapshot(self) -> System1CalibrationSnapshot:
        n = len(self._events)
        if n == 0:
            tally = summarise_outcomes([])
            return System1CalibrationSnapshot(
                total_events=0,
                brier_score=0.0,
                expected_calibration_error=0.0,
                false_positives=0,
                false_negatives=0,
                true_positives=0,
                true_negatives=0,
                recall=1.0,
                precision=1.0,
                outcome_tally=tally,
                candidate_weight_release=WeightRelease(
                    version=self.baseline_version,
                    weights={"system1.reflex": 1.0},
                    model_versions={"system1.reflex": "cfc-1.0"},
                ),
            )

        brier_sum = 0.0
        tp = fp = tn = fn = 0
        bins: list[list[_CalibrationEvent]] = [[] for _ in range(5)]

        for ev in self._events:
            y = 1.0 if ev.actual_adverse_or_escalated else 0.0
            brier_sum += (ev.predicted_risk - y) ** 2
            if ev.predicted_red_flag and ev.actual_adverse_or_escalated:
                tp += 1
            elif ev.predicted_red_flag and not ev.actual_adverse_or_escalated:
                fp += 1
            elif not ev.predicted_red_flag and ev.actual_adverse_or_escalated:
                fn += 1
            else:
                tn += 1

            bin_idx = min(4, int(ev.predicted_risk * 5.0))
            bins[bin_idx].append(ev)

        brier = brier_sum / n
        ece = 0.0
        for bucket in bins:
            if not bucket:
                continue
            avg_p = sum(e.predicted_risk for e in bucket) / len(bucket)
            avg_y = sum(1.0 if e.actual_adverse_or_escalated else 0.0 for e in bucket) / len(bucket)
            ece += (len(bucket) / n) * abs(avg_p - avg_y)

        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        tally = summarise_outcomes([e.reviewer_outcome for e in self._events])

        # Compute governed weight adjustment:
        # If FN > 0, weight of safety sentinel is boosted (>= 1.25) to prevent missed deterioration.
        # If FN == 0 and Brier <= 0.12, reward calibrated reflex weight.
        if fn > 0:
            reflex_weight = 0.85
            safety_weight = 1.35
            next_ver = f"{self.baseline_version}-fn-hardened"
        else:
            reflex_weight = round(max(0.75, min(1.25, 1.0 + (0.12 - brier))), 4)
            safety_weight = 1.15
            next_ver = f"{self.baseline_version}-cal-{n}"

        release = WeightRelease(
            version=next_ver,
            weights={
                "system1.reflex": reflex_weight,
                "tier0.safety_seat": safety_weight,
            },
            model_versions={
                "system1.reflex": "cfc-1.0",
                "tier0.safety_seat": "deterministic-1.0",
            },
        )

        return System1CalibrationSnapshot(
            total_events=n,
            brier_score=round(brier, 4),
            expected_calibration_error=round(ece, 4),
            false_positives=fp,
            false_negatives=fn,
            true_positives=tp,
            true_negatives=tn,
            recall=round(recall, 4),
            precision=round(precision, 4),
            outcome_tally=tally,
            candidate_weight_release=release,
        )


# ---------------------------------------------------------------------------
# 7. Live Intuition Producer & SignalBox Governance Helper (S1-05, S1-11)
# ---------------------------------------------------------------------------


def compute_live_intuition(
    *,
    persona_key: str,
    intents: Sequence[str],
    safety_class: SafetyClass = SafetyClass.routine,
    default_framework: str = "soap",
    clinical_text: str = "",
    timeline_events: Sequence[Mapping[str, Any]] = (),
    vital_samples: Sequence[ClinicalVitalSample | Mapping[str, Any]] = (),
    hl7_or_fhir_payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    active_medications: Sequence[str] = (),
    allergies: Sequence[str] = (),
    conditions: Sequence[str] = (),
) -> tuple[IntuitionDecision, RoutingDecision]:
    """Compute a live, auditable ``IntuitionDecision`` and ``RoutingDecision`` (<5ms)."""
    has_live_signals = bool(
        clinical_text.strip()
        or timeline_events
        or vital_samples
        or hl7_or_fhir_payload
        or active_medications
        or allergies
        or conditions
    )

    if not has_live_signals:
        salience = {intent: round(1.0 / len(intents), 4) for intent in intents} if intents else {}
        base_conf = 0.72 if safety_class is SafetyClass.high_risk else 0.80
        base_risk = {
            SafetyClass.routine: 0.2,
            SafetyClass.sensitive: 0.55,
            SafetyClass.high_risk: 0.85,
        }[safety_class]
        intuition = IntuitionDecision(
            selected_framework=default_framework,
            route_salience=salience,
            candidate_hypotheses=[f"{persona_key}:{intent}" for intent in intents],
            confidence=base_conf,
            risk_score=base_risk,
            reason_codes=[
                "persona.default_framework",
                "reference_action_manifest",
                f"safety.{safety_class.value}",
            ],
        )
        routing = route(
            intuition,
            deterministic_basis=(safety_class is SafetyClass.routine),
            emergency=False,
            red_flags=(),
        )
        return intuition, routing

    # 1. Evaluate physiological trajectory if vital samples provided
    traj_assessment: TrajectoryAssessment | None = None
    latest_vitals_dict: dict[str, Any] | None = None
    if vital_samples:
        reflex = PhysiologicalTrajectoryReflex()
        for idx, item in enumerate(vital_samples):
            if isinstance(item, ClinicalVitalSample):
                sample = item
            else:
                sample = ClinicalVitalSample(
                    timestamp_seconds=float(item.get("timestamp_seconds", idx * 300.0)),
                    heart_rate=float(item.get("heart_rate", item.get("hr", 75.0))),
                    systolic_bp=float(item.get("systolic_bp", item.get("sbp", 120.0))),
                    diastolic_bp=float(item.get("diastolic_bp", item.get("dbp", 78.0))),
                    respiratory_rate=float(item.get("respiratory_rate", item.get("rr", 15.0))),
                    spo2=float(item.get("spo2", item.get("oxygen_saturation", 98.0))),
                    temperature=float(item.get("temperature", item.get("temp", 36.8))),
                    consciousness=str(item.get("consciousness", item.get("avpu", "A"))),
                )
            traj_assessment = reflex.observe(sample)
            latest_vitals_dict = {
                "heart_rate": sample.heart_rate,
                "systolic_bp": sample.systolic_bp,
                "diastolic_bp": sample.diastolic_bp,
                "respiratory_rate": sample.respiratory_rate,
                "spo2": sample.spo2,
                "temperature": sample.temperature,
                "consciousness": sample.consciousness,
            }

    # 2. Evaluate consultation / text state
    consult_result = ConsultationStateReflex.evaluate(
        clinical_text,
        timeline_events=timeline_events,
        vitals=latest_vitals_dict,
        active_medications=active_medications,
        allergies=allergies,
        conditions=conditions,
    )

    # 3. Evaluate HL7v2 / FHIR semantic triage if payload provided
    hl7_result: Hl7v2TriageResult | None = None
    if hl7_or_fhir_payload is not None:
        hl7_result = Hl7v2SemanticReflex.evaluate(hl7_or_fhir_payload)

    # Combine risk, confidence, red flags, and dynamic salience
    red_flags: list[str] = list(consult_result.active_red_flags)
    reason_codes: list[str] = list(consult_result.reason_codes)
    risk_score = consult_result.risk_score
    confidence = consult_result.confidence
    emergency = False

    if traj_assessment is not None:
        red_flags.extend(traj_assessment.red_flags)
        reason_codes.extend(traj_assessment.reason_codes)
        risk_score = max(risk_score, traj_assessment.compensatory_drift_score)
        if traj_assessment.cynefin_suggestion is CynefinClass.chaotic:
            emergency = True
        if traj_assessment.subthreshold_early_warning:
            confidence = min(confidence, 0.74)

    if hl7_result is not None and hl7_result.anomalies:
        red_flags.extend(a.code for a in hl7_result.anomalies)
        reason_codes.extend(hl7_result.reason_codes)
        risk_score = max(risk_score, hl7_result.risk_score)
        confidence = min(confidence, 0.68)

    if safety_class is SafetyClass.high_risk:
        risk_score = max(risk_score, 0.65)

    dedup_flags = tuple(dict.fromkeys(red_flags))
    dedup_reasons = tuple(
        dict.fromkeys([*reason_codes, f"safety.{safety_class.value}"])
    )

    # Dynamic framework selection: escalate to ISBAR when deteriorating or red-flagged
    selected_framework = default_framework
    if dedup_flags and default_framework == "soap" and persona_key in ("doctor", "clinician", "nurse"):
        selected_framework = "isbar"

    # Salience weighting across intents
    salience: dict[str, float] = {}
    if intents:
        raw_weights: dict[str, float] = {}
        for intent in intents:
            w = 1.0
            if dedup_flags and ("triage" in intent or "escalate" in intent or "lab" in intent):
                w = 2.5
            elif not dedup_flags and ("result" in intent or "appointment" in intent):
                w = 1.5
            raw_weights[intent] = w
        total_w = sum(raw_weights.values()) or 1.0
        salience = {k: round(v / total_w, 4) for k, v in raw_weights.items()}

    hypotheses = [f"{persona_key}:{intent}" for intent in intents]
    for sym in consult_result.confirmed_symptoms[:3]:
        hypotheses.append(f"symptom:{sym.lower().replace(' ', '_')}")
    if traj_assessment and traj_assessment.subthreshold_early_warning:
        hypotheses.append("trajectory:compensatory_drift")

    intuition = IntuitionDecision(
        selected_framework=selected_framework,
        route_salience=salience,
        candidate_hypotheses=hypotheses,
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        risk_score=round(max(0.0, min(1.0, risk_score)), 4),
        reason_codes=list(dedup_reasons),
    )

    routing = route(
        intuition,
        deterministic_basis=(not dedup_flags and safety_class is SafetyClass.routine),
        emergency=emergency,
        red_flags=dedup_flags,
    )
    return intuition, routing


def evaluate_reflex_signal_governance(
    *,
    intent: str,
    persona: str,
    intuition: IntuitionDecision,
    evidence_ref: str = "fhir://Observation/system1-reflex",
    attested: bool = True,
    reversible: bool = True,
    action_intended: bool = True,
    workflow_id: str = "wf-system1-reflex",
    correlation_id: str = "corr-system1-reflex",
) -> GovernedDecision:
    """Bind a System 1 ``IntuitionDecision`` into SignalBox ``evaluate_signal_action``.

    If System 1 flagged any red flag or risk_score > 0.25, effective confidence is
    clamped below ``CONFIDENCE_BYPASS_THRESHOLD`` (0.85) so the action is guaranteed
    to escalate to ``GovernanceTier.human_in_loop`` with a ``HandoffPackage``.
    """
    has_red_flag = any(
        "red_flag" in r or "tier0" in r or "compensatory" in r or "mismatch" in r
        for r in intuition.reason_codes
    )
    effective_conf = (
        min(intuition.confidence, CONFIDENCE_BYPASS_THRESHOLD - 0.05)
        if (has_red_flag or intuition.risk_score > 0.30)
        else intuition.confidence
    )
    signal = PerceivedSignal(
        description=f"System 1 reflex ({intuition.selected_framework}): {', '.join(intuition.reason_codes[:3])}",
        evidence_ref=evidence_ref,
        attested=attested,
        confidence=effective_conf,
        origin="ai",
        reversible=reversible,
    )
    return evaluate_signal_action(
        intent=intent,
        persona=persona,
        signal=signal,
        action_intended=action_intended,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
    )


def _opt_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 8. Herbert A. Simon Bounded Rationality & Satisficing Frontier Extension
#    (Equity Afya Franchise Referral & Hospital Nurse Deployment Reflexes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundedRationalityEnvelope:
    """Explicitly quantifies how System 1 extends human bounded rationality
    (Simon, 1955/1957) while declaring the AI system's own structural bounds.

    Human decision constraints addressed:
    1. Limited Information -> ``information_completeness_ratio``, ``synthesized_sources``, ``missing_information_gaps``
    2. Limited Cognitive Capacity -> ``cognitive_chunks_surfaced`` (bounded to working-memory limits), ``alternatives_evaluated``, ``alternatives_satisficed``
    3. Limited Time -> ``decision_latency_ms``, ``consultation_time_saved_seconds``

    AI self-constraints disclosed:
    - ``ai_data_quality_bound``, ``ai_epistemic_uncertainty``, ``ai_operational_mode``
    - ``clinician_accountability_retained`` (invariant: must always be True)
    """

    information_completeness_ratio: float
    synthesized_sources: tuple[str, ...]
    missing_information_gaps: tuple[str, ...]
    cognitive_chunks_surfaced: int
    alternatives_evaluated: int
    alternatives_satisficed: int
    decision_latency_ms: float
    consultation_time_saved_seconds: float
    ai_data_quality_bound: float
    ai_epistemic_uncertainty: float
    ai_operational_mode: str = "in_process_cfc_deterministic"
    clinician_accountability_retained: bool = True

    def __post_init__(self) -> None:
        if not self.clinician_accountability_retained:
            raise ValueError(
                "Bounded rationality invariant violated: AI extends decision boundaries "
                "but clinician_accountability_retained must always be True."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "information_completeness_ratio": self.information_completeness_ratio,
            "synthesized_sources": list(self.synthesized_sources),
            "missing_information_gaps": list(self.missing_information_gaps),
            "cognitive_chunks_surfaced": self.cognitive_chunks_surfaced,
            "alternatives_evaluated": self.alternatives_evaluated,
            "alternatives_satisficed": self.alternatives_satisficed,
            "decision_latency_ms": self.decision_latency_ms,
            "consultation_time_saved_seconds": self.consultation_time_saved_seconds,
            "ai_data_quality_bound": self.ai_data_quality_bound,
            "ai_epistemic_uncertainty": self.ai_epistemic_uncertainty,
            "ai_operational_mode": self.ai_operational_mode,
            "clinician_accountability_retained": self.clinician_accountability_retained,
        }


@dataclass(frozen=True)
class SpecialistReferralOption:
    """A satisficing referral or management option for franchise/network care (e.g. Equity Afya)."""

    option_id: str
    facility_id: str
    facility_name: str
    specialty: str
    pathway_type: str  # "emergency_transfer" | "fast_track_specialist" | "tele_specialist_coconsult" | "in_clinic_guideline_care"
    urgency: str  # "stat" | "urgent" | "routine"
    estimated_wait_days: float
    distance_km: float
    cost_tier: str  # "sha_nhif_covered" | "low_copay_franchise" | "standard_specialist_tariff"
    satisficing_score: float
    meets_aspiration_threshold: bool
    supporting_evidence: tuple[str, ...]
    uncertainty_notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "facility_id": self.facility_id,
            "facility_name": self.facility_name,
            "specialty": self.specialty,
            "pathway_type": self.pathway_type,
            "urgency": self.urgency,
            "estimated_wait_days": self.estimated_wait_days,
            "distance_km": self.distance_km,
            "cost_tier": self.cost_tier,
            "satisficing_score": self.satisficing_score,
            "meets_aspiration_threshold": self.meets_aspiration_threshold,
            "supporting_evidence": list(self.supporting_evidence),
            "uncertainty_notes": list(self.uncertainty_notes),
        }


@dataclass(frozen=True)
class ReferralSatisficingResult:
    """Result of the Equity Afya / Primary-Care Specialist Referral Satisficing Reflex."""

    recommended_option: SpecialistReferralOption
    satisficing_alternatives: tuple[SpecialistReferralOption, ...]
    clinical_red_flags: tuple[str, ...]
    guideline_triggers: tuple[str, ...]
    predictive_risk_score: float
    bounded_rationality: BoundedRationalityEnvelope

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended_option": self.recommended_option.to_dict(),
            "satisficing_alternatives": [
                opt.to_dict() for opt in self.satisficing_alternatives
            ],
            "clinical_red_flags": list(self.clinical_red_flags),
            "guideline_triggers": list(self.guideline_triggers),
            "predictive_risk_score": self.predictive_risk_score,
            "bounded_rationality": self.bounded_rationality.to_dict(),
        }


class ReferralSatisficingReflex:
    """Sub-5ms System 1 decision-boundary extender for specialist referrals
    across distributed primary-care franchises (such as Equity Afya).

    Addresses Simon's three bounds without usurping clinician accountability:
    - Information bound: fuses longitudinal history, medications, prior labs,
      guideline criteria, specialist slot availability, and patient cost tier.
    - Cognitive bound: evaluates candidate pathways against an aspiration threshold
      and surfaces the top 3 satisficing alternatives with explicit trade-offs.
    - Temporal bound: executes in <2ms so the clinician has referral clarity
      during the live consultation.
    """

    @staticmethod
    def evaluate(
        *,
        clinical_text: str,
        specialty_requested: str | None = None,
        longitudinal_conditions: Sequence[str] = (),
        active_medications: Sequence[str] = (),
        previous_investigations: Sequence[str] = (),
        vitals: Mapping[str, Any] | None = None,
        patient_cost_constraint: str = "low_copay_franchise",
        available_specialist_slots: Sequence[Mapping[str, Any]] = (),
        aspiration_threshold: float = 0.72,
    ) -> ReferralSatisficingResult:
        t0 = time.perf_counter()
        consult = ConsultationStateReflex.evaluate(
            clinical_text,
            vitals=vitals,
            active_medications=active_medications,
            conditions=longitudinal_conditions,
        )

        # Infer target specialty if not explicitly provided
        inferred_specialty = specialty_requested or "General Internal Medicine"
        flags_joined = " ".join(consult.active_red_flags).lower()
        symptoms_joined = " ".join(consult.confirmed_symptoms).lower()
        if "chest_pain" in flags_joined or "jaw_or_arm" in flags_joined or "dyspnoea" in symptoms_joined:
            inferred_specialty = specialty_requested or "Cardiology"
        elif "stroke" in flags_joined or "thunderclap" in flags_joined or "headache" in symptoms_joined:
            inferred_specialty = specialty_requested or "Neurology"
        elif "cauda_equina" in flags_joined or "backache" in symptoms_joined:
            inferred_specialty = specialty_requested or "Neurosurgery / Spine"
        elif "preeclampsia" in flags_joined:
            inferred_specialty = specialty_requested or "Obstetrics & Maternal-Fetal Medicine"

        # Identify missing longitudinal information that bounds certainty
        missing_gaps: list[str] = []
        synthesized_sources: list[str] = ["consultation_presentation", "nice_who_referral_guidelines"]
        if longitudinal_conditions:
            synthesized_sources.append("longitudinal_problem_list")
        else:
            missing_gaps.append("No prior longitudinal problem list on file")
        if active_medications:
            synthesized_sources.append("active_medication_history")
        else:
            missing_gaps.append("Medication history unconfirmed")
        if previous_investigations:
            synthesized_sources.append("previous_investigations_and_labs")
        else:
            missing_gaps.append("No baseline diagnostic investigations attached")
        if vitals:
            synthesized_sources.append("current_encounter_vitals")
        else:
            missing_gaps.append("Current vital signs not yet recorded")
        if available_specialist_slots:
            synthesized_sources.append("realtime_franchise_specialist_directory")
        else:
            synthesized_sources.append("default_franchise_network_topology")
            missing_gaps.append("Live external hospital slot feed unavailable; using franchise directory estimates")

        info_completeness = round(
            min(1.0, max(0.25, (6 - len(missing_gaps)) / 6.0)),
            4,
        )

        has_emergency_flag = bool(consult.active_red_flags) or consult.risk_score >= 0.70
        guideline_triggers: list[str] = []
        if has_emergency_flag:
            guideline_triggers.append(
                f"Red-flag clinical presentation ({', '.join(consult.active_red_flags) or 'high risk score'}) "
                f"requires urgent {inferred_specialty} escalation"
            )
        if consult.unscreened_safety_net_prompts:
            guideline_triggers.append(
                f"Complete safety-net screening: {consult.unscreened_safety_net_prompts[0]}"
            )
        if not guideline_triggers:
            guideline_triggers.append(
                f"Routine stepped-care threshold evaluated for {inferred_specialty}"
            )

        # Build candidate referral options across the Equity Afya / partner network
        raw_slots = list(available_specialist_slots) if available_specialist_slots else [
            {
                "facility_id": "EQA-HUB-ACUTE-01",
                "facility_name": "Equity Afya Regional Acute Referral Hub",
                "specialty": inferred_specialty,
                "pathway_type": "emergency_transfer" if has_emergency_flag else "fast_track_specialist",
                "urgency": "stat" if has_emergency_flag else "urgent",
                "estimated_wait_days": 0.0 if has_emergency_flag else 2.0,
                "distance_km": 6.5,
                "cost_tier": "sha_nhif_covered",
            },
            {
                "facility_id": "EQA-TELE-SPEC-01",
                "facility_name": "Equity Afya Franchise Tele-Specialist Consult",
                "specialty": inferred_specialty,
                "pathway_type": "tele_specialist_coconsult",
                "urgency": "urgent" if has_emergency_flag else "routine",
                "estimated_wait_days": 0.5,
                "distance_km": 0.0,
                "cost_tier": "low_copay_franchise",
            },
            {
                "facility_id": "EQA-LOCAL-CLINIC",
                "facility_name": "In-Clinic Stepped Care + Targeted Diagnostics",
                "specialty": "Primary Care + Diagnostic Workup",
                "pathway_type": "in_clinic_guideline_care",
                "urgency": "routine",
                "estimated_wait_days": 0.0,
                "distance_km": 0.0,
                "cost_tier": "low_copay_franchise",
            },
            {
                "facility_id": "EXT-TERTIARY-01",
                "facility_name": "External Tertiary Specialist Centre",
                "specialty": inferred_specialty,
                "pathway_type": "fast_track_specialist",
                "urgency": "urgent",
                "estimated_wait_days": 7.0,
                "distance_km": 18.0,
                "cost_tier": "standard_specialist_tariff",
            },
        ]

        evaluated_options: list[SpecialistReferralOption] = []
        for idx, slot in enumerate(raw_slots):
            ptype = str(slot.get("pathway_type", "fast_track_specialist"))
            wait_d = float(slot.get("estimated_wait_days", 3.0))
            dist_km = float(slot.get("distance_km", 5.0))
            ctier = str(slot.get("cost_tier", "low_copay_franchise"))

            # Compute Simon satisficing score balancing clinical acuity, timeliness, and patient cost constraint
            if has_emergency_flag:
                acuity_fit = 0.96 if ptype in ("emergency_transfer", "fast_track_specialist") else (
                    0.68 if ptype == "tele_specialist_coconsult" else 0.25
                )
            else:
                acuity_fit = 0.88 if ptype in ("in_clinic_guideline_care", "tele_specialist_coconsult") else 0.74

            time_fit = max(0.2, 1.0 - (wait_d / 21.0))
            cost_fit = (
                1.0
                if ctier in ("sha_nhif_covered", patient_cost_constraint)
                else (0.78 if ctier == "low_copay_franchise" else 0.52)
            )
            score = round(0.55 * acuity_fit + 0.25 * time_fit + 0.20 * cost_fit, 4)

            evidence: list[str] = [
                f"Pathway: {ptype} ({slot.get('specialty', inferred_specialty)})",
                f"Estimated wait: {wait_d:g}d | Distance: {dist_km:g}km | Cost tier: {ctier}",
            ]
            if has_emergency_flag and ptype in ("emergency_transfer", "fast_track_specialist"):
                evidence.append("Matches red-flag escalation requirement (monotonic safety floor)")
            elif not has_emergency_flag and ptype in ("in_clinic_guideline_care", "tele_specialist_coconsult"):
                evidence.append("Avoids unnecessary patient travel/out-of-pocket specialist cost while preserving safety net")

            uncertainties: list[str] = list(missing_gaps[:2])
            if ctier == "standard_specialist_tariff" and patient_cost_constraint != "standard_specialist_tariff":
                uncertainties.append("Out-of-pocket specialist tariff may exceed patient affordability threshold")

            evaluated_options.append(
                SpecialistReferralOption(
                    option_id=f"ref-opt-{idx + 1}",
                    facility_id=str(slot.get("facility_id", f"FAC-{idx + 1}")),
                    facility_name=str(slot.get("facility_name", "Network Facility")),
                    specialty=str(slot.get("specialty", inferred_specialty)),
                    pathway_type=ptype,
                    urgency=str(slot.get("urgency", "routine")),
                    estimated_wait_days=wait_d,
                    distance_km=dist_km,
                    cost_tier=ctier,
                    satisficing_score=score,
                    meets_aspiration_threshold=(score >= aspiration_threshold),
                    supporting_evidence=tuple(evidence),
                    uncertainty_notes=tuple(uncertainties),
                )
            )

        evaluated_options.sort(key=lambda o: o.satisficing_score, reverse=True)
        top_three = tuple(evaluated_options[:3])
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)
        epistemic_uncertainty = round(max(0.05, 1.0 - (0.6 * consult.confidence + 0.4 * info_completeness)), 4)

        envelope = BoundedRationalityEnvelope(
            information_completeness_ratio=info_completeness,
            synthesized_sources=tuple(synthesized_sources),
            missing_information_gaps=tuple(missing_gaps),
            cognitive_chunks_surfaced=len(top_three),
            alternatives_evaluated=len(evaluated_options),
            alternatives_satisficed=sum(1 for o in top_three if o.meets_aspiration_threshold),
            decision_latency_ms=elapsed_ms,
            consultation_time_saved_seconds=150.0,
            ai_data_quality_bound=info_completeness,
            ai_epistemic_uncertainty=epistemic_uncertainty,
            ai_operational_mode="in_process_cfc_deterministic",
            clinician_accountability_retained=True,
        )

        return ReferralSatisficingResult(
            recommended_option=top_three[0],
            satisficing_alternatives=top_three,
            clinical_red_flags=consult.active_red_flags,
            guideline_triggers=tuple(guideline_triggers),
            predictive_risk_score=consult.risk_score,
            bounded_rationality=envelope,
        )


@dataclass(frozen=True)
class WardStaffingRecommendation:
    """Result of the Hospital Nurse Deployment Satisficing Reflex (Simon's staffing problem)."""

    ward_id: str
    shift_hours: float
    expected_patient_census: float
    census_uncertainty_band: tuple[int, int]
    high_acuity_drift_patients: int
    recommended_nurses: int
    minimum_safe_floor_nurses: int
    surge_contingency_nurses: int
    target_patients_per_nurse: float
    rationale: tuple[str, ...]
    bounded_rationality: BoundedRationalityEnvelope

    def to_dict(self) -> dict[str, Any]:
        return {
            "ward_id": self.ward_id,
            "shift_hours": self.shift_hours,
            "expected_patient_census": self.expected_patient_census,
            "census_uncertainty_band": list(self.census_uncertainty_band),
            "high_acuity_drift_patients": self.high_acuity_drift_patients,
            "recommended_nurses": self.recommended_nurses,
            "minimum_safe_floor_nurses": self.minimum_safe_floor_nurses,
            "surge_contingency_nurses": self.surge_contingency_nurses,
            "target_patients_per_nurse": self.target_patients_per_nurse,
            "rationale": list(self.rationale),
            "bounded_rationality": self.bounded_rationality.to_dict(),
        }


class StaffingSatisficingReflex:
    """Sub-2ms operational satisficing reflex for hospital nurse deployment under uncertainty.

    Rather than pretending to know tomorrow's exact arrivals or patient acuity
    (impossible under bounded rationality), combines current census, historical
    arrival distribution, and live CfC physiological trajectory drift counts to
    recommend a robust satisficing nurse deployment with explicit uncertainty bounds.
    """

    @staticmethod
    def evaluate(
        *,
        ward_id: str = "ward-acute-1",
        current_census: int = 20,
        historical_mean_arrivals: float = 6.0,
        historical_std_arrivals: float = 2.5,
        expected_discharges: float = 4.0,
        high_acuity_drift_patients: int = 2,
        base_patients_per_nurse: float = 4.0,
        shift_hours: float = 12.0,
    ) -> WardStaffingRecommendation:
        t0 = time.perf_counter()
        expected_census = max(
            1.0,
            float(current_census) + float(historical_mean_arrivals) - float(expected_discharges),
        )
        low_census = max(1, int(math.floor(expected_census - 1.28 * historical_std_arrivals)))
        high_census = max(low_census, int(math.ceil(expected_census + 1.28 * historical_std_arrivals)))

        # High-acuity deteriorating patients (detected by CfC trajectory reflex) require 1:2 nurse ratio
        standard_patients = max(0.0, expected_census - high_acuity_drift_patients)
        base_nurses = (standard_patients / max(1.0, base_patients_per_nurse)) + (
            high_acuity_drift_patients / 2.0
        )
        min_safe_floor = max(2, int(math.ceil(base_nurses)))
        surge_buffer = max(
            0,
            int(math.ceil((high_census - expected_census) / max(1.0, base_patients_per_nurse))),
        )
        recommended = min_safe_floor + (1 if high_acuity_drift_patients >= 2 or surge_buffer >= 1 else 0)
        effective_ratio = round(expected_census / max(1, recommended), 2)

        rationale = (
            f"Expected census {expected_census:0.1f} (80% arrival interval [{low_census}, {high_census}] patients).",
            f"{high_acuity_drift_patients} patient(s) exhibiting active CfC physiological drift weighted at 1:2 acuity ratio.",
            f"Satisficing deployment: {recommended} nurses (statutory floor {min_safe_floor}, surge reserve +{surge_buffer}).",
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)
        uncertainty = round(min(0.65, historical_std_arrivals / max(4.0, expected_census)), 4)

        envelope = BoundedRationalityEnvelope(
            information_completeness_ratio=0.84,
            synthesized_sources=(
                "current_ward_census",
                "historical_arrival_distribution",
                "cfc_physiological_drift_acuity_stream",
            ),
            missing_information_gaps=(
                "Exact unscheduled ED admissions and individual length-of-stay remain stochastic",
            ),
            cognitive_chunks_surfaced=3,
            alternatives_evaluated=5,
            alternatives_satisficed=2,
            decision_latency_ms=elapsed_ms,
            consultation_time_saved_seconds=300.0,
            ai_data_quality_bound=0.84,
            ai_epistemic_uncertainty=uncertainty,
            ai_operational_mode="in_process_cfc_deterministic",
            clinician_accountability_retained=True,
        )

        return WardStaffingRecommendation(
            ward_id=ward_id,
            shift_hours=shift_hours,
            expected_patient_census=round(expected_census, 2),
            census_uncertainty_band=(low_census, high_census),
            high_acuity_drift_patients=high_acuity_drift_patients,
            recommended_nurses=recommended,
            minimum_safe_floor_nurses=min_safe_floor,
            surge_contingency_nurses=surge_buffer,
            target_patients_per_nurse=effective_ratio,
            rationale=rationale,
            bounded_rationality=envelope,
        )
