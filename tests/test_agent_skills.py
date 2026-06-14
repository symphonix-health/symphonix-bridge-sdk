"""Tests for bridge_sdk.agent_skills -- agent-only skills + tooltip facets."""

from __future__ import annotations

import pytest

from bridge_sdk import (
    AGENT_ONLY_SKILLS,
    AgentSenseFacet,
    HumanUseRefused,
    agent_only_skills,
    assert_non_human,
    attach_agent_only_skills,
    reference_superpersona_contract,
    skill_pack_refs,
)


def test_catalogue_covers_every_facet_exactly_once() -> None:
    facets = [s.facet for s in agent_only_skills()]
    assert set(facets) == set(AgentSenseFacet)
    assert len(facets) == len(set(facets)) == len(AgentSenseFacet)


def test_all_skills_refuse_human_use_and_are_latent() -> None:
    for skill in agent_only_skills():
        assert skill.human_usable is False
        assert skill.latent is True


def test_assert_non_human_allows_agent() -> None:
    skill = assert_non_human("sense.attestation.verify", actor_is_human=False)
    assert skill.facet is AgentSenseFacet.attestation


def test_assert_non_human_refuses_human() -> None:
    with pytest.raises(HumanUseRefused):
        assert_non_human("sense.attestation.verify", actor_is_human=True)


def test_assert_non_human_refuses_unknown_skill() -> None:
    with pytest.raises(HumanUseRefused):
        assert_non_human("sense.does.not.exist", actor_is_human=False)


def test_skill_pack_refs_match_catalogue() -> None:
    refs = skill_pack_refs()
    assert {r.id for r in refs} == set(AGENT_ONLY_SKILLS)


def test_attach_agent_only_skills_is_additive_and_idempotent() -> None:
    base = reference_superpersona_contract("doctor")
    once = attach_agent_only_skills(base)
    attached_ids = {p.id for p in once.skill_packs}
    assert set(AGENT_ONLY_SKILLS).issubset(attached_ids)
    # original packs are preserved
    assert {p.id for p in base.skill_packs}.issubset(attached_ids)
    # idempotent: attaching again adds nothing
    twice = attach_agent_only_skills(once)
    assert len(twice.skill_packs) == len(once.skill_packs)


def test_to_dict_is_serialisable() -> None:
    d = AGENT_ONLY_SKILLS["sense.hidden.read"].to_dict()
    assert d["facet"] == "hidden_structural"
    assert d["human_usable"] is False
