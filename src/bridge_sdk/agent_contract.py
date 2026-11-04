"""Agent Execution Contract: typed action manifests for agent personas.

Workstream 1 of the agent-native optimisation programme. An ``AgentActionManifest``
declares the typed intents a component exposes to agent personas, so an agent
resolves a deterministic action (a typed domain API or a Nexus task) BEFORE it
falls back to semantic-UI or raw browser control. Each intent carries an
input/output contract, pre/post-conditions, a safety class, and a FHIR R4 Task
projection.

This is the keystone vocabulary every later workstream builds on:

- Workstream 2 (execution ledger) records the FHIR Task produced here.
- Workstream 3 (persona delegation) scopes tokens to intent capabilities.
- Workstream 4 (audit) links Provenance/AuditEvent to the resolved intent.

Requirements: FR-AEC-001..005, NFR-AEC-001..002
(see ``BulletTrain/docs/AGENT_EXECUTION_CONTRACT_REQUIREMENTS.md``).

Reconciliation note. The source plan ("Optimising Symphonix Health for
Agent-Native Computer Use", Workstream 1) referred to these requirements as
``FR-AO-*`` and named the host repo ``tool-library``; both were inferred
placeholders, corrected here (not silently):

- Component code is ``AEC`` (Agent Execution Contract). ``AO`` already names the
  existing Agent Orchestrator in BulletTrain
  (``agent_orchestrator_lifecycle_matrix.14col.json`` owns ``FR-AO-001..010``).
- The shared type lives in this SDK, the supported cross-repo client surface.
  ``tool-library`` is a civic tool-lending app used to stress-test the CAID
  pipeline, not a shared library.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

__all__ = [
    "ActionIntent",
    "AgentActionManifest",
    "AutonomyLevel",
    "Condition",
    "EXECUTION_MODE_BY_PATH",
    "ExecutionMode",
    "FieldSpec",
    "FieldType",
    "IOContract",
    "ManifestError",
    "CONDUCTOR_SIBLING_MANIFESTS",
    "REFERENCE_MANIFESTS",
    "all_conductor_manifests",
    "ResolverDecision",
    "ResolverPath",
    "SafetyClass",
    "reference_manifest",
    "resolve_intent",
]

_AUTONOMY_EXT = "https://symphonix.health/fhir/StructureDefinition/autonomy-level"
_EVIDENCE_EXT = "https://symphonix.health/fhir/StructureDefinition/evidence-bundle"


class ManifestError(ValueError):
    """An action manifest is malformed, or a requested intent is unknown."""


class SafetyClass(str, Enum):
    """Clinical-safety classification governing autonomy and auth requirements."""

    routine = "routine"  # low-risk, deterministic, no patient data
    sensitive = "sensitive"  # patient-data touching; consent + scope gated
    high_risk = "high_risk"  # clinically influential; DPoP/mTLS + safety case


class AutonomyLevel(str, Enum):
    """Governance-ladder rung an intent may run at (earned, not launched)."""

    shadow = "shadow"
    advisory = "advisory"
    auto_with_threshold_hitl = "auto_with_threshold_hitl"


class ResolverPath(str, Enum):
    """Execution path chosen by the action resolver, in preference order."""

    api = "api"  # typed domain API
    nexus = "nexus"  # Nexus A2A task
    ui_fallback = "ui_fallback"  # semantic-UI action (no typed manifest entry)
    browser = "browser"  # raw browser control (last resort)


class ExecutionMode(str, Enum):
    """Normalised 3-valued execution mode for telemetry (FR-AEC-001).

    The canonical mode the measurement framework joins on (the API-first and
    browser-fallback KPIs). Derived once from the 4-valued ``ResolverPath`` via
    ``EXECUTION_MODE_BY_PATH`` so every emitter agrees on one normalisation
    rather than re-deriving it differently. ``typed_api`` covers both the typed
    domain API and the Nexus task; ``semantic_ui`` is a semantic-UI action;
    ``browser`` is raw browser control.
    """

    typed_api = "typed_api"
    semantic_ui = "semantic_ui"
    browser = "browser"


# The single source of truth for path -> mode normalisation. Every face
# (SignalBox executor, audit composer, dashboards) must use this map, not its
# own copy, so the API-first rate is computed identically everywhere.
EXECUTION_MODE_BY_PATH: dict[ResolverPath, ExecutionMode] = {
    ResolverPath.api: ExecutionMode.typed_api,
    ResolverPath.nexus: ExecutionMode.typed_api,
    ResolverPath.ui_fallback: ExecutionMode.semantic_ui,
    ResolverPath.browser: ExecutionMode.browser,
}


class FieldType(str, Enum):
    """Permitted field types in an input/output contract."""

    string = "string"
    integer = "integer"
    number = "number"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    reference = "reference"  # FHIR reference, e.g. "Patient/123"
    code = "code"
    object = "object"


_PY_TYPES: dict[FieldType, tuple[type, ...]] = {
    FieldType.string: (str,),
    FieldType.integer: (int,),
    FieldType.number: (int, float),
    FieldType.boolean: (bool,),
    FieldType.date: (str,),
    FieldType.datetime: (str,),
    FieldType.reference: (str,),
    FieldType.code: (str,),
    FieldType.object: (dict,),
}


class FieldSpec(BaseModel):
    """One typed field in an input or output contract."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: FieldType
    required: bool = True
    description: str = ""
    fhir_path: str | None = None  # e.g. "Task.for.reference"


class IOContract(BaseModel):
    """A typed input or output contract for an intent."""

    model_config = ConfigDict(extra="forbid")

    fields: list[FieldSpec] = Field(default_factory=list)

    def field_map(self) -> dict[str, FieldSpec]:
        return {f.name: f for f in self.fields}


class Condition(BaseModel):
    """A machine-checkable pre/post-condition assertion."""

    model_config = ConfigDict(extra="forbid")

    expression: str  # e.g. "consent.permits('triage')"
    description: str = ""


class ActionIntent(BaseModel):
    """A single typed intent a component exposes to agent personas."""

    model_config = ConfigDict(extra="forbid")

    intent: str  # dotted name, e.g. "triage.start"
    title: str
    component: str  # owning service, e.g. "triage-api"
    safety_class: SafetyClass
    autonomy_default: AutonomyLevel = AutonomyLevel.advisory
    input: IOContract = Field(default_factory=IOContract)
    output: IOContract = Field(default_factory=IOContract)
    preconditions: list[Condition] = Field(default_factory=list)
    postconditions: list[Condition] = Field(default_factory=list)
    fhir_task_code: str  # Task.code.text for this intent
    fhir_task_intent: str = "order"  # FHIR Task.intent value

    def validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate a payload against the input contract.

        Raises ``ManifestError`` (FR-AEC-001-AC02) on an unknown field, a missing
        required field, or a type mismatch, so a malformed intent payload fails
        with a typed error rather than being handed to a browser.
        """
        if not isinstance(payload, dict):
            raise ManifestError(f"intent '{self.intent}' payload must be an object")
        spec = self.input.field_map()
        unknown = set(payload) - set(spec)
        if unknown:
            raise ManifestError(
                f"intent '{self.intent}' rejects unknown fields: {sorted(unknown)}"
            )
        for name, fs in spec.items():
            if name not in payload:
                if fs.required:
                    raise ManifestError(
                        f"intent '{self.intent}' missing required field '{name}'"
                    )
                continue
            value = payload[name]
            # bool is a subclass of int; reject it where a number is expected.
            numeric = fs.type in (FieldType.integer, FieldType.number)
            if numeric and isinstance(value, bool):
                raise ManifestError(
                    f"intent '{self.intent}' field '{name}' expected {fs.type.value}"
                )
            if not isinstance(value, _PY_TYPES[fs.type]):
                raise ManifestError(
                    f"intent '{self.intent}' field '{name}' expected {fs.type.value}"
                )
        return payload

    def to_fhir_task(
        self,
        payload: dict[str, Any],
        *,
        persona: str,
        patient_reference: str | None = None,
        autonomy: AutonomyLevel | None = None,
        evidence_bundle: str | None = None,
        status: str = "in-progress",
    ) -> dict[str, Any]:
        """Project a validated invocation into a FHIR R4 Task (FR-AEC-003).

        Mirrors the reference Task in the plan: resourceType/status/intent/code,
        ``for.reference``, an ``input[]`` array (including the AgentPersona), and
        Symphonix extensions for autonomy-level and evidence-bundle.
        """
        self.validate_payload(payload)
        level = (autonomy or self.autonomy_default).value
        task_input: list[dict[str, Any]] = [
            {"type": {"text": "AgentPersona"}, "valueString": persona},
        ]
        spec = self.input.field_map()
        for name, value in payload.items():
            if spec[name].type is FieldType.reference and isinstance(value, str):
                task_input.append(
                    {"type": {"text": name}, "valueReference": {"reference": value}}
                )
            else:
                task_input.append({"type": {"text": name}, "valueString": str(value)})
        extension: list[dict[str, Any]] = [{"url": _AUTONOMY_EXT, "valueCode": level}]
        if evidence_bundle:
            extension.append({"url": _EVIDENCE_EXT, "valueUri": evidence_bundle})
        task: dict[str, Any] = {
            "resourceType": "Task",
            "status": status,
            "intent": self.fhir_task_intent,
            "code": {"text": self.fhir_task_code},
            "input": task_input,
            "extension": extension,
        }
        if patient_reference:
            task["for"] = {"reference": patient_reference}
        return task


class AgentActionManifest(BaseModel):
    """The set of typed intents one component publishes for agent personas."""

    model_config = ConfigDict(extra="forbid")

    component: str
    version: str = "1.0.0"
    intents: list[ActionIntent] = Field(default_factory=list)

    def intent_names(self) -> list[str]:
        return [i.intent for i in self.intents]

    def has(self, intent: str) -> bool:
        return any(i.intent == intent for i in self.intents)

    def get(self, intent: str) -> ActionIntent:
        for i in self.intents:
            if i.intent == intent:
                return i
        raise ManifestError(
            f"unknown intent '{intent}' for component '{self.component}'"
        )

    def capabilities(self) -> list[str]:
        """Capability strings for GHARRA agent-card registration (FR-AEC-002)."""
        return self.intent_names()

    def agent_card(self, *, endpoint: str | None = None) -> dict[str, Any]:
        """Minimal ``/.well-known/agent-card.json`` body for this component."""
        return {
            "id": self.component,
            "name": self.component,
            "version": self.version,
            "capabilities": self.capabilities(),
            "endpoint": endpoint,
            "intents": [
                {"intent": i.intent, "safety_class": i.safety_class.value}
                for i in self.intents
            ],
        }


class ResolverDecision(BaseModel):
    """The resolver's chosen execution path for an intent (FR-AEC-001/004)."""

    model_config = ConfigDict(extra="forbid")

    intent: str
    path: ResolverPath
    component: str | None = None
    manifest_backed: bool = False
    reason: str | None = None  # required when path is ui_fallback / browser

    @computed_field  # type: ignore[prop-decorator]
    @property
    def execution_mode(self) -> ExecutionMode:
        """Normalised 3-valued execution mode for telemetry (FR-AEC-001).

        Derived from ``path`` so every emitter records the same mode and
        ``model_dump()`` carries it onto the action record. This is the field
        the API-first / browser-fallback KPIs join on.
        """
        return EXECUTION_MODE_BY_PATH[self.path]


def resolve_intent(
    intent: str,
    manifests: list[AgentActionManifest] | dict[str, AgentActionManifest],
    *,
    prefer_nexus: bool = False,
) -> ResolverDecision:
    """Resolve an intent to a deterministic path before any browser action.

    Returns a typed path (``api`` or ``nexus``) when a manifest exposes the
    intent; otherwise ``ui_fallback`` with a recorded reason (FR-AEC-004-AC01).
    """
    items = manifests.values() if isinstance(manifests, dict) else manifests
    for m in items:
        if m.has(intent):
            return ResolverDecision(
                intent=intent,
                path=ResolverPath.nexus if prefer_nexus else ResolverPath.api,
                component=m.component,
                manifest_backed=True,
            )
    return ResolverDecision(
        intent=intent,
        path=ResolverPath.ui_fallback,
        manifest_backed=False,
        reason=f"no manifest entry for intent '{intent}'",
    )


def _patient_ref() -> FieldSpec:
    return FieldSpec(
        name="patient",
        type=FieldType.reference,
        required=True,
        description="FHIR Patient reference, e.g. Patient/123",
        fhir_path="Task.for.reference",
    )


# Reference manifests: the five top workflows (FR-AEC-003). The plan lists
# triage.start, appointment.book, claim.submit, lab.order, result.retrieve.
REFERENCE_MANIFESTS: dict[str, AgentActionManifest] = {
    "triage-api": AgentActionManifest(
        component="triage-api",
        intents=[
            ActionIntent(
                intent="triage.start",
                title="Start a patient triage assessment",
                component="triage-api",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(
                            name="presenting_complaint",
                            type=FieldType.string,
                            description="Free-text presenting complaint",
                        ),
                        FieldSpec(
                            name="questionnaire",
                            type=FieldType.reference,
                            required=False,
                            fhir_path="Task.input:Questionnaire",
                        ),
                    ]
                ),
                output=IOContract(
                    fields=[
                        FieldSpec(
                            name="urgency",
                            type=FieldType.code,
                            description="Recommended urgency band",
                        ),
                        FieldSpec(
                            name="task",
                            type=FieldType.reference,
                            description="Created FHIR Task reference",
                        ),
                    ]
                ),
                preconditions=[
                    Condition(
                        expression="consent.permits('triage')",
                        description="Active consent permits triage",
                    )
                ],
                postconditions=[
                    Condition(expression="task.status in {'in-progress','completed'}")
                ],
                fhir_task_code="agent-triage-start",
            ),
        ],
    ),
    "appointment-system": AgentActionManifest(
        component="appointment-system",
        intents=[
            ActionIntent(
                intent="appointment.book",
                title="Book an appointment slot",
                component="appointment-system",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(
                            name="slot",
                            type=FieldType.string,
                            description="Bookable slot identifier",
                        ),
                    ]
                ),
                output=IOContract(
                    fields=[FieldSpec(name="booking", type=FieldType.reference)]
                ),
                fhir_task_code="agent-appointment-book",
            ),
        ],
    ),
    "insurance-eclaims": AgentActionManifest(
        component="insurance-eclaims",
        intents=[
            ActionIntent(
                intent="claim.submit",
                title="Submit an insurance claim",
                component="insurance-eclaims",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(
                            name="claim",
                            type=FieldType.object,
                            description="Claim payload",
                        ),
                    ]
                ),
                output=IOContract(
                    fields=[FieldSpec(name="claim_status", type=FieldType.code)]
                ),
                fhir_task_code="agent-claim-submit",
            ),
        ],
    ),
    "lis": AgentActionManifest(
        component="lis",
        intents=[
            ActionIntent(
                intent="lab.order",
                title="Place a laboratory order",
                component="lis",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(
                            name="test_code",
                            type=FieldType.code,
                            description="Lab test code",
                        ),
                    ]
                ),
                output=IOContract(
                    fields=[FieldSpec(name="order", type=FieldType.reference)]
                ),
                fhir_task_code="agent-lab-order",
            ),
            ActionIntent(
                intent="result.retrieve",
                title="Retrieve a laboratory result",
                component="lis",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(
                            name="order",
                            type=FieldType.reference,
                            description="Lab order reference",
                        ),
                    ]
                ),
                output=IOContract(
                    fields=[FieldSpec(name="result", type=FieldType.reference)]
                ),
                fhir_task_code="agent-result-retrieve",
            ),
        ],
    ),
}


def reference_manifest(component: str) -> AgentActionManifest:
    """Return the reference manifest for a component (raises ``ManifestError``)."""
    try:
        return REFERENCE_MANIFESTS[component]
    except KeyError:
        raise ManifestError(
            f"no reference manifest for component '{component}'"
        ) from None


CONDUCTOR_SIBLING_MANIFESTS: dict[str, AgentActionManifest] = {
    "enterprise-epr": AgentActionManifest(
        component="enterprise-epr",
        intents=[
            ActionIntent(
                intent="epr.encounter.read",
                title="Read patient encounter and active problem list",
                component="enterprise-epr",
                safety_class=SafetyClass.sensitive,
                input=IOContract(fields=[_patient_ref()]),
                output=IOContract(fields=[FieldSpec(name="encounter", type=FieldType.reference)]),
                fhir_task_code="agent-epr-encounter-read",
            ),
            ActionIntent(
                intent="epr.discharge.propose",
                title="Draft discharge summary and readiness proposal for clinician sign-off",
                component="enterprise-epr",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="encounter", type=FieldType.reference),
                        FieldSpec(name="summary_text", type=FieldType.string),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="discharge_draft", type=FieldType.reference)]),
                fhir_task_code="agent-epr-discharge-propose",
            ),
        ],
    ),
    "pharmacy-system": AgentActionManifest(
        component="pharmacy-system",
        intents=[
            ActionIntent(
                intent="pharmacy.prescription.verify",
                title="Verify medication safety, allergies, and renal dosing",
                component="pharmacy-system",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="medication_request", type=FieldType.reference),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="verification_status", type=FieldType.code)]),
                fhir_task_code="agent-pharmacy-verify",
            ),
            ActionIntent(
                intent="pharmacy.dispense.release",
                title="Release verified medication dispense (requires pharmacist sign-off)",
                component="pharmacy-system",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="medication_request", type=FieldType.reference),
                        FieldSpec(name="pharmacist_signoff_id", type=FieldType.string),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="medication_dispense", type=FieldType.reference)]),
                fhir_task_code="agent-pharmacy-dispense",
            ),
        ],
    ),
    "nursing-station": AgentActionManifest(
        component="nursing-station",
        intents=[
            ActionIntent(
                intent="nursing.vitals.record",
                title="Record nursing vital signs and NEWS2 observation",
                component="nursing-station",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="news2_score", type=FieldType.integer),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="observation", type=FieldType.reference)]),
                fhir_task_code="agent-nursing-vitals-record",
            ),
            ActionIntent(
                intent="nursing.deterioration.escalate",
                title="Escalate acute NEWS2 clinical deterioration to rapid response team",
                component="nursing-station",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="news2_score", type=FieldType.integer),
                        FieldSpec(name="escalation_reason", type=FieldType.string),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="escalation_task", type=FieldType.reference)]),
                fhir_task_code="agent-nursing-deterioration-escalate",
            ),
        ],
    ),
    "scheduling-gateway": AgentActionManifest(
        component="scheduling-gateway",
        intents=[
            ActionIntent(
                intent="scheduling.slot.reserve",
                title="Reserve a federated outpatient or follow-up slot",
                component="scheduling-gateway",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="slot_id", type=FieldType.string),
                        FieldSpec(name="clinic_code", type=FieldType.code),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="appointment", type=FieldType.reference)]),
                fhir_task_code="agent-scheduling-slot-reserve",
            ),
        ],
    ),
    "patient360-assistant": AgentActionManifest(
        component="patient360-assistant",
        intents=[
            ActionIntent(
                intent="patient360.summary.synthesize",
                title="Synthesize longitudinal Patient360 clinical summary across federated siblings",
                component="patient360-assistant",
                safety_class=SafetyClass.sensitive,
                input=IOContract(fields=[_patient_ref()]),
                output=IOContract(fields=[FieldSpec(name="bundle", type=FieldType.reference)]),
                fhir_task_code="agent-patient360-synthesize",
            ),
        ],
    ),
    "clinical-pathways": AgentActionManifest(
        component="clinical-pathways",
        intents=[
            ActionIntent(
                intent="pathways.sepsis.evaluate",
                title="Evaluate NICE NG51 sepsis and acute deterioration pathway",
                component="clinical-pathways",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="news2_score", type=FieldType.integer),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="care_plan", type=FieldType.reference)]),
                fhir_task_code="agent-pathways-sepsis-evaluate",
            ),
        ],
    ),
    "pacs-ris": AgentActionManifest(
        component="pacs-ris",
        intents=[
            ActionIntent(
                intent="imaging.order.create",
                title="Create a diagnostic imaging order in PACS/RIS",
                component="pacs-ris",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="modality", type=FieldType.code),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="service_request", type=FieldType.reference)]),
                fhir_task_code="agent-imaging-order-create",
            ),
        ],
    ),
    "community-nursing": AgentActionManifest(
        component="community-nursing",
        intents=[
            ActionIntent(
                intent="community.visit.schedule",
                title="Schedule post-discharge community nursing follow-up visit",
                component="community-nursing",
                safety_class=SafetyClass.sensitive,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="visit_window", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="care_visit", type=FieldType.reference)]),
                fhir_task_code="agent-community-visit-schedule",
            ),
        ],
    ),
    "ambulance-ems": AgentActionManifest(
        component="ambulance-ems",
        intents=[
            ActionIntent(
                intent="ambulance.handover.record",
                title="Record pre-hospital ATMIST ambulance handover to ED",
                component="ambulance-ems",
                safety_class=SafetyClass.high_risk,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="atmist_summary", type=FieldType.string),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="handover_composition", type=FieldType.reference)]),
                fhir_task_code="agent-ambulance-handover-record",
            ),
        ],
    ),
    "symphonix-health-research-to-caid-agent": AgentActionManifest(
        component="symphonix-health-research-to-caid-agent",
        intents=[
            ActionIntent(
                intent="research.evidence.appraise",
                title="Execute governed R0-R5 literature retrieval, redaction, and GRADE appraisal",
                component="symphonix-health-research-to-caid-agent",
                safety_class=SafetyClass.routine,
                input=IOContract(
                    fields=[
                        FieldSpec(name="query", type=FieldType.string),
                        FieldSpec(name="tier", type=FieldType.code),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="evidence_pack_id", type=FieldType.string)]),
                fhir_task_code="agent-research-evidence-appraise",
            ),
        ],
    ),
    "second-brain-kb": AgentActionManifest(
        component="second-brain-kb",
        intents=[
            ActionIntent(
                intent="kb.guideline.query",
                title="Query curated internal clinical guidelines and proven knowledge base",
                component="second-brain-kb",
                safety_class=SafetyClass.routine,
                input=IOContract(
                    fields=[FieldSpec(name="topic", type=FieldType.string)]
                ),
                output=IOContract(fields=[FieldSpec(name="knowledge_entry_id", type=FieldType.string)]),
                fhir_task_code="agent-kb-guideline-query",
            ),
        ],
    ),
    "BulletTrain": AgentActionManifest(
        component="BulletTrain",
        intents=[
            ActionIntent(
                intent="bullettrain.hie.federate",
                title="Federate clinical encounter and SHR resource via BulletTrain OpenHIE Hub",
                component="BulletTrain",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-bullettrain-hie-federate",
            ),
        ],
    ),
    "HMIS": AgentActionManifest(
        component="HMIS",
        intents=[
            ActionIntent(
                intent="hmis.adt.admit",
                title="Record hospital ADT admission and bed assignment in HMIS",
                component="HMIS",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-hmis-adt-admit",
            ),
        ],
    ),
    "gp-system": AgentActionManifest(
        component="gp-system",
        intents=[
            ActionIntent(
                intent="gp.consultation.record",
                title="Record primary care GP consultation and referral in gp-system",
                component="gp-system",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-gp-consultation-record",
            ),
        ],
    ),
    "eps": AgentActionManifest(
        component="eps",
        intents=[
            ActionIntent(
                intent="eps.prescription.sign",
                title="Prepare electronic prescription for clinician signature in EPS",
                component="eps",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-eps-prescription-sign",
            ),
        ],
    ),
    "etps": AgentActionManifest(
        component="etps",
        intents=[
            ActionIntent(
                intent="etps.spine.transmit",
                title="Transmit signed electronic prescription via ETPS Spine bridge",
                component="etps",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-etps-spine-transmit",
            ),
        ],
    ),
    "provider-portal": AgentActionManifest(
        component="provider-portal",
        intents=[
            ActionIntent(
                intent="provider.referral.review",
                title="Review cross-specialty clinician referral in Provider Portal",
                component="provider-portal",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-provider-referral-review",
            ),
        ],
    ),
    "citizen-portal": AgentActionManifest(
        component="citizen-portal",
        intents=[
            ActionIntent(
                intent="citizen.record.view",
                title="Project patient-facing summary and consent status in Citizen Portal",
                component="citizen-portal",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-citizen-record-view",
            ),
        ],
    ),
    "maternity-system": AgentActionManifest(
        component="maternity-system",
        intents=[
            ActionIntent(
                intent="maternity.partogram.evaluate",
                title="Evaluate intrapartum partogram and maternal-fetal escalation in Maternity System",
                component="maternity-system",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-maternity-partogram-evaluate",
            ),
        ],
    ),
    "cancer-pathway-tracker": AgentActionManifest(
        component="cancer-pathway-tracker",
        intents=[
            ActionIntent(
                intent="cancer.fds_clock.track",
                title="Track 2WW/62-day Faster Diagnosis Standard oncology pathway clock",
                component="cancer-pathway-tracker",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-cancer-fds-clock-track",
            ),
        ],
    ),
    "genomics-interpretation": AgentActionManifest(
        component="genomics-interpretation",
        intents=[
            ActionIntent(
                intent="genomics.variant.classify",
                title="Classify ACMG genomic variant for molecular MDT review",
                component="genomics-interpretation",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-genomics-variant-classify",
            ),
        ],
    ),
    "blood-transfusion": AgentActionManifest(
        component="blood-transfusion",
        intents=[
            ActionIntent(
                intent="transfusion.crossmatch.verify",
                title="Verify electronic crossmatch and haemovigilance compatibility in Blood Transfusion",
                component="blood-transfusion",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-transfusion-crossmatch-verify",
            ),
        ],
    ),
    "epaccs": AgentActionManifest(
        component="epaccs",
        intents=[
            ActionIntent(
                intent="epaccs.respect.coordinate",
                title="Coordinate EPaCCS ReSPECT palliative care preferences across care settings",
                component="epaccs",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-epaccs-respect-coordinate",
            ),
        ],
    ),
    "mha-administration": AgentActionManifest(
        component="mha-administration",
        intents=[
            ActionIntent(
                intent="mha.detention_clock.verify",
                title="Verify Mental Health Act statutory detention clock and SOAD safeguard",
                component="mha-administration",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-mha-detention-clock-verify",
            ),
        ],
    ),
    "screening-recall": AgentActionManifest(
        component="screening-recall",
        intents=[
            ActionIntent(
                intent="screening.cohort.invite",
                title="Issue population screening recall invitation and failsafe tracking",
                component="screening-recall",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-screening-cohort-invite",
            ),
        ],
    ),
    "rehabilitation": AgentActionManifest(
        component="rehabilitation",
        intents=[
            ActionIntent(
                intent="rehab.care_plan.update",
                title="Update allied health and rehabilitation functional care plan",
                component="rehabilitation",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-rehab-care-plan-update",
            ),
        ],
    ),
    "clinical-trial-system": AgentActionManifest(
        component="clinical-trial-system",
        intents=[
            ActionIntent(
                intent="ctms.subject.screen",
                title="Screen clinical trial candidate against protocol eligibility criteria",
                component="clinical-trial-system",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-ctms-subject-screen",
            ),
        ],
    ),
    "picis-system": AgentActionManifest(
        component="picis-system",
        intents=[
            ActionIntent(
                intent="picis.icu_stepup.evaluate",
                title="Evaluate perioperative/ICU high-acuity step-up capacity and trajectory in PICIS",
                component="picis-system",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-picis-icu-stepup-evaluate",
            ),
        ],
    ),
    "mortuary-and-me": AgentActionManifest(
        component="mortuary-and-me",
        intents=[
            ActionIntent(
                intent="mortuary.me_scrutiny.record",
                title="Record Medical Examiner scrutiny and chain-of-custody verification",
                component="mortuary-and-me",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-mortuary-me-scrutiny-record",
            ),
        ],
    ),
    "outbreak-management": AgentActionManifest(
        component="outbreak-management",
        intents=[
            ActionIntent(
                intent="outbreak.contact_trace.record",
                title="Record communicable disease outbreak contact-tracing episode",
                component="outbreak-management",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-outbreak-contact-trace-record",
            ),
        ],
    ),
    "analytics-bi": AgentActionManifest(
        component="analytics-bi",
        intents=[
            ActionIntent(
                intent="analytics.cohort.aggregate",
                title="Compute de-identified population health KPI aggregate in Analytics BI",
                component="analytics-bi",
                safety_class=SafetyClass.routine,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-analytics-cohort-aggregate",
            ),
        ],
    ),
    "erp": AgentActionManifest(
        component="erp",
        intents=[
            ActionIntent(
                intent="erp.ledger.reconcile",
                title="Reconcile healthcare enterprise resource planning financial ledger entry",
                component="erp",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-erp-ledger-reconcile",
            ),
        ],
    ),
    "supply-chain-erp": AgentActionManifest(
        component="supply-chain-erp",
        intents=[
            ActionIntent(
                intent="supply_chain.stock.replenish",
                title="Trigger medical supply chain lot/cold-chain replenishment order",
                component="supply-chain-erp",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-supply-chain-stock-replenish",
            ),
        ],
    ),
    "ormdet-governance-console": AgentActionManifest(
        component="ormdet-governance-console",
        intents=[
            ActionIntent(
                intent="ormdet.model_risk.audit",
                title="Record ORMDET clinical AI and multi-agent operational risk governance audit",
                component="ormdet-governance-console",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-ormdet-model-risk-audit",
            ),
        ],
    ),
    "vr-therapy": AgentActionManifest(
        component="vr-therapy",
        intents=[
            ActionIntent(
                intent="vr_therapy.session.supervise",
                title="Supervise therapeutic VR digital behavioural health session telemetry",
                component="vr-therapy",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-vr-therapy-session-supervise",
            ),
        ],
    ),
    "hear-the-risk": AgentActionManifest(
        component="hear-the-risk",
        intents=[
            ActionIntent(
                intent="hear_the_risk.biomarker.screen",
                title="Evaluate acoustic vocal biomarker risk stratification screening",
                component="hear-the-risk",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-hear-the-risk-biomarker-screen",
            ),
        ],
    ),
    "helixcare-diagnostic-access-network": AgentActionManifest(
        component="helixcare-diagnostic-access-network",
        intents=[
            ActionIntent(
                intent="hdan.diagnostic_slot.route",
                title="Route federated diagnostic access referral across HelixCare HDAN",
                component="helixcare-diagnostic-access-network",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-hdan-diagnostic-slot-route",
            ),
        ],
    ),
    "kenya-uhc-implementation": AgentActionManifest(
        component="kenya-uhc-implementation",
        intents=[
            ActionIntent(
                intent="kenya_uhc.sha_claim.verify",
                title="Verify Kenya SHA UHC national country-pack eligibility and claim bundle",
                component="kenya-uhc-implementation",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-kenya-uhc-sha-claim-verify",
            ),
        ],
    ),
    "tool-library": AgentActionManifest(
        component="tool-library",
        intents=[
            ActionIntent(
                intent="tool_library.catalog.inspect",
                title="Inspect governed clinical and operational tool library catalogue entry",
                component="tool-library",
                safety_class=SafetyClass.routine,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-tool-library-catalog-inspect",
            ),
        ],
    ),
    "ambient-clinical-scribe": AgentActionManifest(
        component="ambient-clinical-scribe",
        intents=[
            ActionIntent(
                intent="ambient_scribe.soap_note.draft",
                title="Draft structured ambient clinical consultation SOAP note for clinician sign-off",
                component="ambient-clinical-scribe",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-ambient-scribe-soap-note-draft",
            ),
        ],
    ),
    "mdt-board-orchestrator": AgentActionManifest(
        component="mdt-board-orchestrator",
        intents=[
            ActionIntent(
                intent="mdt_board.quorum.coordinate",
                title="Coordinate multi-disciplinary team board case list and specialist quorum",
                component="mdt-board-orchestrator",
                safety_class=SafetyClass.sensitive,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-mdt-board-quorum-coordinate",
            ),
        ],
    ),
    "renal-dialysis-coordination": AgentActionManifest(
        component="renal-dialysis-coordination",
        intents=[
            ActionIntent(
                intent="renal_dialysis.session.schedule",
                title="Coordinate haemodialysis chair schedule and vascular access surveillance",
                component="renal-dialysis-coordination",
                safety_class=SafetyClass.high_risk,
                autonomy_default=AutonomyLevel.advisory,
                input=IOContract(
                    fields=[
                        _patient_ref(),
                        FieldSpec(name="context_note", type=FieldType.string, required=False),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="outcome_ref", type=FieldType.reference)]),
                fhir_task_code="agent-renal-dialysis-session-schedule",
            ),
        ],
    ),
    "global-agent-registry": AgentActionManifest(
        component="global-agent-registry",
        intents=[
            ActionIntent(
                intent="gharra.capability.select",
                title="Broker governed Persona/SuperPersona capability selection with trust and jurisdiction gates",
                component="global-agent-registry",
                safety_class=SafetyClass.routine,
                input=IOContract(
                    fields=[
                        FieldSpec(name="domain", type=FieldType.string),
                        FieldSpec(name="jurisdiction", type=FieldType.code),
                    ]
                ),
                output=IOContract(fields=[FieldSpec(name="selected_agent_id", type=FieldType.string)]),
                fhir_task_code="agent-gharra-capability-select",
            ),
        ],
    ),
}


def all_conductor_manifests() -> dict[str, AgentActionManifest]:
    """Return the combined dictionary of reference and Conductor sibling manifests."""
    combined = dict(REFERENCE_MANIFESTS)
    combined.update(CONDUCTOR_SIBLING_MANIFESTS)
    return combined
