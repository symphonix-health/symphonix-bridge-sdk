"""Contract and negative-control tests for bridge_sdk.clinical_decision_record (W-03)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bridge_sdk import (  # noqa: E402
    CDR_SCHEMA_VERSION,
    CdrAbstention,
    CdrAgent,
    CdrAudit,
    CdrCalculation,
    CdrCalculationInput,
    CdrCalculationThreshold,
    CdrCalibration,
    CdrClinicianAction,
    CdrConflictingFinding,
    CdrDecision,
    CdrDecisionOutput,
    CdrEvidenceItem,
    CdrFactReference,
    CdrFactSource,
    CdrFrameworkBasis,
    CdrMissingInfo,
    CdrModelOrComponent,
    CdrProvenance,
    CdrProvenanceInput,
    CdrSafety,
    CdrSafetyAlert,
    CdrSupportingFact,
    CdrTenantScope,
    CdrUncertainty,
    ClinicalDecisionRecordBuilder,
    ClinicalDecisionRecordError,
    assert_valid_clinical_decision_record,
    build_clinical_decision_record,
    load_cdr_schema,
    mask_clinical_decision_record,
    resolve_repo_code_change,
    validate_clinical_decision_record,
)


def _sample_record() -> dict:
    code_change = resolve_repo_code_change(
        "symphonix-bridge-sdk", Path(__file__).resolve().parents[1]
    )
    return build_clinical_decision_record(
        record_id="cdr_bullettrain-diag-0001",
        recorded_at="2026-10-21T17:00:00Z",
        agent=CdrAgent(
            gharra_agent_id="bullettrain-diagnostic-reasoning",
            display_name="BulletTrain Diagnostic Reasoning Agent",
            version="2.4.0",
            clinical_domain="diagnostics",
            repository="BulletTrain",
            responsible_owner_org_id="symphonix-clinical-ai",
        ),
        supporting_facts=[
            CdrSupportingFact(
                fact_id="F1",
                kind="vital",
                value="Temperature 38.9 degC on ward admission",
                source=CdrFactSource(
                    source_system="FHIR-Observation",
                    source_record_id="OBS-TEMP-9912",
                    resolved=True,
                    observed_at="2026-10-21T16:40:00Z",
                    jurisdiction="GB-ENG",
                ),
            ),
            CdrSupportingFact(
                fact_id="F2",
                kind="symptom",
                value="Productive cough with purulent sputum for 4 days",
                source=CdrFactSource(
                    source_system="FHIR-Condition",
                    source_record_id="COND-COUGH-4401",
                    resolved=True,
                    observed_at="2026-10-21T16:42:00Z",
                    jurisdiction="GB-ENG",
                ),
            ),
            CdrSupportingFact(
                fact_id="F3",
                kind="laboratory",
                value="C-reactive protein 118 mg/L",
                source=CdrFactSource(
                    source_system="FHIR-Observation",
                    source_record_id="OBS-CRP-7781",
                    resolved=True,
                    observed_at="2026-10-21T16:50:00Z",
                    jurisdiction="GB-ENG",
                ),
            ),
            CdrSupportingFact(
                fact_id="F4",
                kind="laboratory",
                value="Plasma D-dimer 210 ng/mL FEU",
                source=CdrFactSource(
                    source_system="FHIR-Observation",
                    source_record_id="OBS-DDIMER-7782",
                    resolved=True,
                    observed_at="2026-10-21T16:51:00Z",
                    jurisdiction="GB-ENG",
                ),
            ),
        ],
        decision=CdrDecision(
            kind="differential_diagnosis",
            summary=(
                "Community-acquired pneumonia is the primary working diagnosis supported by fever 38.9 C, "
                "productive cough, and CRP 118 mg/L; acute pulmonary embolism is excluded given low D-dimer."
            ),
            outputs=[
                CdrDecisionOutput(
                    label="Community-acquired pneumonia",
                    code_system="SNOMED-CT",
                    code="385093006",
                    role="primary",
                    confidence=0.82,
                    calibration=CdrCalibration(
                        raw_confidence=0.86,
                        calibrated_confidence=0.82,
                        method="temperature_scaling",
                        calibration_table_version="bt-diag-temp-v1.2",
                        drift_check="within_ece_0.03",
                    ),
                    facts_relied_upon=[
                        CdrFactReference(
                            fact_id="F1",
                            how_it_contributed=(
                                "Fever of 38.9 degC indicates systemic acute infection consistent with bacterial CAP."
                            ),
                            strength="primary",
                        ),
                        CdrFactReference(
                            fact_id="F2",
                            how_it_contributed=(
                                "Purulent productive cough localises the infectious process to the lower respiratory tract."
                            ),
                            strength="supporting",
                        ),
                        CdrFactReference(
                            fact_id="F3",
                            how_it_contributed=(
                                "CRP > 100 mg/L strongly favours bacterial pneumonia over viral bronchitis per NICE CG191."
                            ),
                            strength="primary",
                        ),
                    ],
                ),
                CdrDecisionOutput(
                    label="Acute pulmonary embolism",
                    code_system="SNOMED-CT",
                    code="59282003",
                    role="excluded",
                    confidence=0.06,
                    facts_relied_upon=[
                        CdrFactReference(
                            fact_id="F4",
                            how_it_contributed=(
                                "D-dimer below 500 ng/mL FEU in a low pre-test probability patient excludes acute PE."
                            ),
                            strength="contradictory",
                        )
                    ],
                ),
            ],
        ),
        evidence=[
            CdrEvidenceItem(
                evidence_id="E1",
                kind="clinical_guideline",
                identifier="https://www.nice.org.uk/guidance/cg191",
                version_or_release="CG191-2023-10",
                jurisdiction="GB-ENG",
                retrieved_at="2026-10-21T16:59:58Z",
                supports=["Community-acquired pneumonia"],
                research_framework_basis=[
                    CdrFrameworkBasis(
                        framework="FUTURE-AI",
                        principle="Explainability and traceability of clinical rationale",
                    ),
                    CdrFrameworkBasis(
                        framework="TRIPOD+AI",
                        principle="Explicit predictor reporting and calibration transparency",
                    ),
                ],
            )
        ],
        uncertainty=CdrUncertainty(
            statement=(
                "Chest radiograph and sputum microbiology culture are pending; empiric classification relies on "
                "inflammatory markers and clinical examination."
            ),
            missing_information=[
                CdrMissingInfo(
                    what="Chest X-ray report",
                    why_it_matters="Required to confirm lobar or patchy consolidation for definitive CAP diagnosis.",
                    requested_from="radiology-order-service",
                )
            ],
            conflicting_findings=[
                CdrConflictingFinding(
                    description="Normal leukocyte count despite elevated CRP 118 mg/L",
                    direction="contradicts",
                    fact_or_evidence_ref="F3",
                )
            ],
            calibrated_confidence=0.82,
            calibration_method="temperature_scaling",
            calculation=CdrCalculation(
                method="scored_rule_set",
                inputs_used=[
                    CdrCalculationInput(
                        name="crp_mg_l",
                        value=118.0,
                        derived_from=["F3"],
                    ),
                    CdrCalculationInput(
                        name="temperature_c",
                        value=38.9,
                        derived_from=["F1"],
                    ),
                ],
                thresholds_applied=[
                    CdrCalculationThreshold(
                        name="minimum_review_confidence",
                        value=0.60,
                        resulting_status="requires_human_review",
                    )
                ],
                reproducible=True,
                verification_command="pytest tests/test_clinical_decision_record.py",
            ),
        ),
        safety=CdrSafety(
            contraindications_checked=True,
            alerts=[
                CdrSafetyAlert(
                    severity="moderate",
                    message="Confirm infiltrate on chest radiograph for patient 9912 within 4 hours.",
                    rule_id="RULE-CAP-CXR-4H",
                )
            ],
            requires_human_review=True,
            review_role="attending_clinician",
            decision_status="requires_human_review",
            abstention=CdrAbstention(
                abstained=False,
                reason_code=None,
                minimum_confidence_threshold=0.60,
            ),
            safety_rule_hits=["RULE-CAP-CXR-4H"],
        ),
        provenance=CdrProvenance(
            model_or_component=CdrModelOrComponent(
                identifier="symphonix-clinical-reasoner-local",
                version="2026.10",
                provider="symphonix-local",
                deployment_fingerprint="fp-local-998877",
            ),
            inputs=[
                CdrProvenanceInput(
                    type="clinical_record",
                    identifier="fhir:Patient/SYNTH-042",
                    version_or_release="v4.0.1",
                    tool="fhir.get_observations",
                ),
                CdrProvenanceInput(
                    type="guideline_store",
                    identifier="nice:cg191",
                    version_or_release="2023-10",
                    tool="nice.lookup_guideline",
                ),
            ],
            prompt_identifier="bullettrain.diagnostic_reasoning",
            prompt_version="2.4.0",
            code_change=code_change,
        ),
        audit=CdrAudit(
            audit_reference="audit:bullettrain:diag:0001",
            persisted=True,
            resolved_in_audit_store=True,
            tenant_scope=CdrTenantScope(
                patient_scope="patient:SYNTH-042",
                facility_scope="facility:NHS-LON-01",
                purpose_of_use="clinical_decision_support",
            ),
            clinician_action=CdrClinicianAction(
                action="not_yet_reviewed",
            ),
        ),
    )


def test_cdr_schema_loads_and_builder_emits_valid_record() -> None:
    schema = load_cdr_schema()
    assert schema["title"] == "Symphonix clinical decision explanation and evidence record"
    record = _sample_record()
    assert record["schema_version"] == CDR_SCHEMA_VERSION
    assert record["provenance"]["code_change"]["revision_verified"] is True
    problems = validate_clinical_decision_record(record)
    assert problems == []


def test_negative_dangling_fact_reference_rejected() -> None:
    record = _sample_record()
    tampered = deepcopy(record)
    tampered["decision"]["outputs"][0]["facts_relied_upon"].append(
        {
            "fact_id": "F999",
            "how_it_contributed": "References a fact_id that does not exist in supporting_facts.",
        }
    )
    problems = validate_clinical_decision_record(tampered)
    assert any("F999" in err and "not present in supporting_facts" in err for err in problems)
    with pytest.raises(ClinicalDecisionRecordError):
        assert_valid_clinical_decision_record(tampered)


def test_negative_circular_fact_explanation_rejected() -> None:
    record = _sample_record()
    tampered = deepcopy(record)
    tampered["decision"]["outputs"][0]["facts_relied_upon"][0]["how_it_contributed"] = (
        tampered["decision"]["outputs"][0]["label"]
    )
    problems = validate_clinical_decision_record(tampered)
    assert any("merely restates output label" in err for err in problems)


def test_negative_unresolvable_evidence_rejected() -> None:
    record = _sample_record()
    tampered = deepcopy(record)
    tampered["evidence"][0]["identifier"] = "NICE guideline with no URI or authority"
    problems = validate_clinical_decision_record(tampered)
    assert any("not a resolvable namespace/URI/DOI identifier" in err for err in problems)


def test_negative_missing_evidence_version_rejected() -> None:
    record = _sample_record()
    tampered = deepcopy(record)
    tampered["evidence"][0]["version_or_release"] = "   "
    problems = validate_clinical_decision_record(tampered)
    assert any("version_or_release must be a non-empty string" in err for err in problems)


def test_role_profile_masking_preserves_schema_validity() -> None:
    record = _sample_record()

    clinician_masked = mask_clinical_decision_record(record, role_profile="clinician")
    assert clinician_masked["audit"]["tenant_scope"]["patient_scope"] == "patient:SYNTH-XXX"
    assert clinician_masked["supporting_facts"][0]["source"]["source_record_id"] == "OBS-TEMP-XXXX"
    assert "38.9" not in clinician_masked["decision"]["summary"]
    assert "XX.X" in clinician_masked["decision"]["summary"]
    assert "deployment_fingerprint" not in clinician_masked["provenance"]["model_or_component"]
    # Structural IDs and citations remain schema-valid
    assert clinician_masked["schema_version"] == CDR_SCHEMA_VERSION
    assert clinician_masked["record_id"] == "cdr_bullettrain-diag-0001"
    assert clinician_masked["evidence"][0]["identifier"] == "https://www.nice.org.uk/guidance/cg191"
    assert validate_clinical_decision_record(clinician_masked) == []

    developer_masked = mask_clinical_decision_record(record, role_profile="developer")
    assert (
        developer_masked["provenance"]["model_or_component"]["deployment_fingerprint"]
        == "fp-local-998877"
    )
    assert validate_clinical_decision_record(developer_masked) == []
