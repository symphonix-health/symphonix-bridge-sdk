"""Tests for bridge_sdk.evidence -- rank B evidence resolution.

The headline test proves rank B unblocks the previously-latent ``auto_on_loop``
path: the same routine action escalates while unattested, then auto-proceeds once
real (verified, untampered) evidence is resolved -- and stays escalated if the
evidence is tampered (fail-closed).
"""

from __future__ import annotations

from bridge_sdk import (
    ActionIntent,
    AgentActionManifest,
    AutonomyLevel,
    GovernanceTier,
    IOContract,
    NullEvidenceResolver,
    PerceivedSignal,
    ResolvedEvidence,
    SafetyClass,
    StaticEvidenceResolver,
    evaluate_signal_action,
    is_seeded_simulation_grounded,
    seeded_simulation_grounding_failures,
    signal_from_evidence,
)

_ROUTINE = {
    "ops": AgentActionManifest(
        component="ops",
        intents=[
            ActionIntent(
                intent="dashboard.filter",
                title="Filter the dashboard",
                component="ops",
                safety_class=SafetyClass.routine,
                autonomy_default=AutonomyLevel.auto_with_threshold_hitl,
                input=IOContract(fields=[]),
                output=IOContract(fields=[]),
                preconditions=[],
                postconditions=[],
                fhir_task_code="filter",
            )
        ],
    )
}


def _grounded_evidence(**overrides) -> ResolvedEvidence:
    fields = dict(
        evidence_ref="urn:x",
        attested=True,
        confidence=0.99,
        origin="device",
        reversible=True,
        tamper="ok",
        source_span_ref="paper:self-harness:page-5:offset-1520-1830",
        target_evidence_ref="tests/test_evidence.py::test_rank_b_unblocks_auto_on_loop",
        seeded_dataset_id="seeded-symphonix-bridge-evidence-v1",
        persona_id="persona:clinician-routing-agent",
        scenario_id="scenario:evidence-grounding-routine-dashboard-filter",
        service_route="bridge_sdk.evidence.signal_from_evidence",
        permission_scope="dashboard.filter:read",
        telemetry_ref="telemetry:seeded:evidence-grounding:auto-on-loop",
    )
    fields.update(overrides)
    return ResolvedEvidence(**fields)


def test_null_resolver_is_fail_closed() -> None:
    base = PerceivedSignal(evidence_ref="urn:x")
    assert NullEvidenceResolver().resolve("urn:x") is None
    assert signal_from_evidence(base, None) == base


def test_static_resolver_enriches_signal() -> None:
    ev = _grounded_evidence()
    resolver = StaticEvidenceResolver({"urn:x": ev})
    enriched = signal_from_evidence(
        PerceivedSignal(evidence_ref="urn:x"), resolver.resolve("urn:x")
    )
    assert enriched.attested is True
    assert enriched.confidence == 0.99
    assert enriched.origin == "device"
    assert enriched.reversible is True


def test_tampered_evidence_not_trusted() -> None:
    ev = _grounded_evidence(tamper="altered")
    base = PerceivedSignal(evidence_ref="urn:x")
    assert signal_from_evidence(base, ev) == base  # fail-closed: altered -> untrusted


def test_missing_seeded_simulation_grounding_is_not_trusted() -> None:
    ev = ResolvedEvidence(
        evidence_ref="urn:x",
        attested=True,
        confidence=0.99,
        reversible=True,
        tamper="ok",
    )
    base = PerceivedSignal(evidence_ref="urn:x")

    assert is_seeded_simulation_grounded(ev) is False
    assert "missing_source_span_ref" in seeded_simulation_grounding_failures(ev)
    assert signal_from_evidence(base, ev) == base


def test_synthetic_or_live_only_telemetry_is_not_trusted() -> None:
    synthetic = _grounded_evidence(synthetic_telemetry=True)
    live_only = _grounded_evidence(live_production_evidence=True)
    base = PerceivedSignal(evidence_ref="urn:x")

    assert "synthetic_telemetry" in seeded_simulation_grounding_failures(synthetic)
    assert "live_production_evidence" in seeded_simulation_grounding_failures(live_only)
    assert signal_from_evidence(base, synthetic) == base
    assert signal_from_evidence(base, live_only) == base


def test_rank_b_unblocks_auto_on_loop() -> None:
    """Evidence resolution flips a routine action from escalate -> auto."""
    base = PerceivedSignal(description="filter to active", evidence_ref="urn:x")
    before = evaluate_signal_action(
        intent="dashboard.filter", persona="p", signal=base, manifests=_ROUTINE
    )
    assert before.tier is GovernanceTier.human_in_loop  # latent: unattested -> escalate

    ev = _grounded_evidence()
    resolved = signal_from_evidence(
        base, StaticEvidenceResolver({"urn:x": ev}).resolve("urn:x")
    )
    after = evaluate_signal_action(
        intent="dashboard.filter", persona="p", signal=resolved, manifests=_ROUTINE
    )
    assert after.tier is GovernanceTier.auto_on_loop  # rank B unblocks the path
    assert after.permitted is True


def test_tampered_evidence_keeps_escalation() -> None:
    base = PerceivedSignal(description="filter", evidence_ref="urn:x")
    ev = _grounded_evidence(tamper="altered")
    resolved = signal_from_evidence(base, ev)
    decision = evaluate_signal_action(
        intent="dashboard.filter", persona="p", signal=resolved, manifests=_ROUTINE
    )
    assert decision.tier is GovernanceTier.human_in_loop  # tamper -> still escalates
