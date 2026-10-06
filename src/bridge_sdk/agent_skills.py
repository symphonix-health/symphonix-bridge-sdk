"""Agent-only skills + tooltip facets -- capabilities that REFUSE human constraints.

These are the non-human-agent surface of the SignalBox programme: the "senses
beyond human" (AGENT_TOOLTIPS_DESIGN.md section 2) expressed as named, typed
SKILLS, plus the agent-only tooltip FACETS they read. They are deliberately
unavailable to a human operator -- a human tooltip is a short hover string, while
these consume the agent-evidence channel (provenance, cryptographic attestation,
coded semantics, policy/consent, telemetry, hidden/off-screen structure,
cross-modal fusion) that a human cannot perceive. They occupy the agent's LATENT
capacity (the agent-evidence channel + model context), not the human ARIA channel.

Consumers (one shared source): the superpersona attaches them as skill packs
(:func:`attach_agent_only_skills`); the BulletTrain-embedded Signalbox control
plane and the standalone signalbox-mcp server import the catalogue.

Guard: :func:`assert_non_human` fails closed if a human actor invokes one --
"can only be used by non-human agents".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from bridge_sdk.superpersona_contract import SkillPackRef

__all__ = [
    "AgentSenseFacet",
    "AgentOnlySkill",
    "HumanUseRefused",
    "AGENT_ONLY_SKILLS",
    "agent_only_skills",
    "skill_pack_refs",
    "assert_non_human",
    "attach_agent_only_skills",
]


class AgentSenseFacet(str, Enum):
    """The agent-only tooltip facets -- senses beyond human (design section 2).

    The first eight are *perception* channels: each reads something an agent can
    perceive that a human cannot. ``agent_action`` is the one *action* facet: a
    capability an agent may exercise that a human-usable surface must not, where
    the guarded contract is "the agent may act, the human may not", not "the
    agent may see, the human may not".
    """

    provenance = "provenance"
    attestation = "attestation"
    coded_semantics = "coded_semantics"
    confidence_origin = "confidence_origin"
    policy_consent = "policy_consent"
    telemetry = "telemetry"
    hidden_structural = "hidden_structural"  # off-screen / zero-opacity / behind-layer
    cross_modal = "cross_modal"
    agent_action = "agent_action"  # act, not perceive -- see input intelligence below


class HumanUseRefused(Exception):
    """Raised (fail-closed) when a human actor attempts an agent-only skill."""


@dataclass(frozen=True)
class AgentOnlySkill:
    """A capability available ONLY to non-human agents.

    ``human_usable`` is always False (these refuse human constraints); ``latent``
    marks that the skill draws on the agent's latent / beyond-human capacity
    rather than a human-facing affordance.
    """

    skill_id: str
    title: str
    facet: AgentSenseFacet
    description: str
    required_scope: str = ""
    human_usable: bool = False
    latent: bool = True

    def skill_pack_ref(self) -> SkillPackRef:
        return SkillPackRef(
            id=self.skill_id, title=self.title, owner="symphonix", version="1.0.0"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "title": self.title,
            "facet": self.facet.value,
            "description": self.description,
            "required_scope": self.required_scope,
            "human_usable": self.human_usable,
            "latent": self.latent,
        }


def _skill(
    skill_id: str,
    title: str,
    facet: AgentSenseFacet,
    description: str,
    required_scope: str = "",
) -> AgentOnlySkill:
    return AgentOnlySkill(
        skill_id=skill_id,
        title=title,
        facet=facet,
        description=description,
        required_scope=required_scope,
    )


AGENT_ONLY_SKILLS: dict[str, AgentOnlySkill] = {
    s.skill_id: s
    for s in (
        _skill(
            "sense.provenance.resolve",
            "Resolve provenance",
            AgentSenseFacet.provenance,
            "Trace a rendered value to its source service / connector / fetch "
            "time / correlation id.",
        ),
        _skill(
            "sense.attestation.verify",
            "Verify attestation",
            AgentSenseFacet.attestation,
            "Verify a value's signature + registry/GHARRA anchor and tamper "
            "status -- a human cannot perceive a hash chain.",
        ),
        _skill(
            "sense.semantics.decode",
            "Decode coded semantics",
            AgentSenseFacet.coded_semantics,
            "Read the LOINC/SNOMED/FHIR coding + reference range + flag behind a "
            "display string.",
        ),
        _skill(
            "sense.confidence.read",
            "Read confidence + origin",
            AgentSenseFacet.confidence_origin,
            "Read model confidence, AI-vs-human-vs-device origin, validation "
            "state, and staleness.",
        ),
        _skill(
            "sense.policy.introspect",
            "Introspect policy + consent",
            AgentSenseFacet.policy_consent,
            "Read whether THIS persona may act, purpose-of-use, consent scope, "
            "and deny reason -- before acting.",
        ),
        _skill(
            "sense.telemetry.read",
            "Read telemetry",
            AgentSenseFacet.telemetry,
            "Read latency, the backing API calls, and console errors behind an "
            "element (sub-perceptual to a human).",
        ),
        _skill(
            "sense.hidden.read",
            "Read hidden structure",
            AgentSenseFacet.hidden_structural,
            "Deliberately read off-screen / zero-opacity / behind-layer text and "
            "z-order -- perceive the human-invisible.",
        ),
        _skill(
            "sense.crossmodal.fuse",
            "Fuse cross-modal",
            AgentSenseFacet.cross_modal,
            "Fuse pixels + DOM + network + attestation into one judgement; a "
            "human gets pixels only.",
        ),
        _skill(
            "action.input.intelligence",
            "Request advisory input intelligence before acting",
            AgentSenseFacet.agent_action,
            "Ask the advisory input-validation capability for bounded, "
            "provenance-bearing suggestions on a field BEFORE submitting, then "
            "act on an explicitly accepted suggestion. The capability never "
            "blocks or mutates: deterministic validation stays the sole blocking "
            "authority, and the agent's acceptance is the act. A human uses the "
            "same capability through the product UI, not through this skill.",
            required_scope="input-intelligence:request",
        ),
    )
}


def agent_only_skills() -> list[AgentOnlySkill]:
    """The agent-only skill catalogue (one per sense facet)."""
    return list(AGENT_ONLY_SKILLS.values())


def skill_pack_refs() -> list[SkillPackRef]:
    """Agent-only skill packs to attach to a :class:`SuperpersonaContract`."""
    return [s.skill_pack_ref() for s in AGENT_ONLY_SKILLS.values()]


def assert_non_human(skill_id: str, *, actor_is_human: bool) -> AgentOnlySkill:
    """Return the skill iff the actor is a non-human agent; refuse otherwise.

    Fail-closed: an unknown skill, or a human actor, raises
    :class:`HumanUseRefused`. These skills refuse human constraints -- they are
    not human affordances.
    """
    skill = AGENT_ONLY_SKILLS.get(skill_id)
    if skill is None:
        raise HumanUseRefused(f"unknown agent-only skill '{skill_id}'")
    if actor_is_human or skill.human_usable:
        raise HumanUseRefused(
            f"skill '{skill_id}' is agent-only; human use is refused"
        )
    return skill


def attach_agent_only_skills(contract: Any) -> Any:
    """Return a copy of a SuperpersonaContract with the agent-only skill packs added.

    Idempotent: packs already present (by id) are not duplicated. Works on any
    object exposing a ``skill_packs`` list and pydantic ``model_copy`` (the
    :class:`SuperpersonaContract` shape).
    """
    existing = list(contract.skill_packs)
    have = {p.id for p in existing}
    additions = [r for r in skill_pack_refs() if r.id not in have]
    return contract.model_copy(update={"skill_packs": existing + additions})
