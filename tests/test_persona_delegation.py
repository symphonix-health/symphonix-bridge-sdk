"""Tests for Persona Delegation (Workstream 3, FR-ID-*/NFR-ID-*).

Uses a REAL RSA keypair (cryptography lib) + REAL PyJWT sign/verify -- no mocks.
Skips honestly if PyJWT or cryptography are absent in the interpreter.
"""
from __future__ import annotations

import importlib.util

import pytest

from bridge_sdk.persona_delegation import (
    ALLOWED_ALGORITHMS,
    DelegationError,
    PersonaScope,
    PersonaTokenClaims,
    TokenBindingType,
    mint_persona_token,
    unify_scope,
    verify_persona_token,
)

_HAVE_JWT = importlib.util.find_spec("jwt") is not None
_HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
pytestmark = pytest.mark.skipif(
    not (_HAVE_JWT and _HAVE_CRYPTO),
    reason="PyJWT + cryptography required for real-key delegation tests",
)

NOW = 1_900_000_000  # fixed clock for deterministic exp checks


@pytest.fixture(scope="module")
def rsa_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub


def _claims(**over) -> PersonaTokenClaims:
    base = dict(
        persona="triage-intake-agent",
        patient_context="Patient/123",
        purpose_of_use="treatment",
        allowed_systems=("triage-api", "appointment-system"),
        max_concurrency=3,
        emergency=False,
        scopes=(PersonaScope.api_read, PersonaScope.task_execute),
        subject="agent",
        actor="user-clinician-1",
    )
    base.update(over)
    return PersonaTokenClaims(**base)


# ---- FR-ID-002: scope unification --------------------------------------

def test_unify_scope_maps_legacy_gharra_scopes() -> None:
    assert unify_scope("gharra:read") is PersonaScope.api_read
    assert unify_scope("gharra:*") is PersonaScope.api_write
    assert unify_scope("api:read") is PersonaScope.api_read


def test_unify_scope_rejects_unknown_scope() -> None:
    with pytest.raises(DelegationError):
        unify_scope("totally:unknown")


# ---- FR-ID-001: mint carries all six bindings + TTL --------------------

def test_minted_token_carries_all_six_bindings(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
    )
    payload = verify_persona_token(tok.jwt, public_key=pub, now=NOW + 10)
    assert payload["persona"] == "triage-intake-agent"
    assert payload["patient_context"] == "Patient/123"           # 1
    assert payload["purpose_of_use"] == "treatment"              # 2
    assert payload["allowed_systems"] == ["triage-api", "appointment-system"]  # 3
    assert payload["max_concurrency"] == 3                       # 4
    assert payload["emergency"] is False                         # 5
    assert payload["scope"] == "api:read task:execute"           # 6
    assert payload["act"] == {"sub": "user-clinician-1"}         # RFC 8693 delegation
    assert payload["exp"] == NOW + 300                           # short-lived TTL


def test_zero_ttl_rejected(rsa_keys) -> None:
    priv, _ = rsa_keys
    with pytest.raises(DelegationError):
        mint_persona_token(
            _claims(), private_key=priv, algorithm="RS256",
            issued_at=NOW, ttl_seconds=0,
        )


# ---- FR-ID + NFR-ID-002: asymmetric-only (HS256 refused) ---------------

def test_mint_refuses_hs256() -> None:
    with pytest.raises(DelegationError):
        mint_persona_token(
            _claims(), private_key=b"symmetric-secret", algorithm="HS256",
            issued_at=NOW, ttl_seconds=300,
        )


def test_allowed_algorithms_exclude_symmetric_and_none() -> None:
    assert "HS256" not in ALLOWED_ALGORITHMS
    assert "none" not in ALLOWED_ALGORITHMS
    assert ALLOWED_ALGORITHMS == {"RS256", "RS384", "RS512", "ES256", "ES384", "EdDSA"}


def test_verify_refuses_to_accept_symmetric_algorithm(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
    )
    with pytest.raises(DelegationError):
        verify_persona_token(tok.jwt, public_key=pub, algorithms=["HS256"], now=NOW + 1)


# ---- FR-ID-003: high-risk requires DPoP/mTLS ---------------------------

def test_high_risk_requires_binding(rsa_keys) -> None:
    priv, _ = rsa_keys
    with pytest.raises(DelegationError):
        mint_persona_token(
            _claims(), private_key=priv, algorithm="RS256",
            issued_at=NOW, ttl_seconds=300,
            binding=TokenBindingType.none, high_risk=True,
        )


def test_mtls_binding_roundtrip_matches_cnf(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
        binding=TokenBindingType.mtls_cnf_x5t_s256,
        cert_thumbprint="THUMB-abc", high_risk=True,
    )
    assert tok.cnf == {"x5t#S256": "THUMB-abc"}
    payload = verify_persona_token(
        tok.jwt, public_key=pub, now=NOW + 5, cert_thumbprint="THUMB-abc",
        require_binding=True,
    )
    assert payload["cnf"]["x5t#S256"] == "THUMB-abc"


def test_mtls_binding_rejects_wrong_thumbprint(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
        binding=TokenBindingType.mtls_cnf_x5t_s256,
        cert_thumbprint="THUMB-abc", high_risk=True,
    )
    with pytest.raises(DelegationError):  # confused-deputy / stolen-token
        verify_persona_token(
            tok.jwt, public_key=pub, now=NOW + 5, cert_thumbprint="THUMB-WRONG",
        )


def test_mtls_binding_requires_material_at_mint(rsa_keys) -> None:
    priv, _ = rsa_keys
    with pytest.raises(DelegationError):
        mint_persona_token(
            _claims(), private_key=priv, algorithm="RS256",
            issued_at=NOW, ttl_seconds=300,
            binding=TokenBindingType.mtls_cnf_x5t_s256,  # no cert_thumbprint
        )


def test_dpop_binding_roundtrip(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
        binding=TokenBindingType.dpop, dpop_jkt="JKT-xyz", high_risk=True,
    )
    assert tok.cnf == {"jkt": "JKT-xyz"}
    payload = verify_persona_token(
        tok.jwt, public_key=pub, now=NOW + 5, dpop_jkt="JKT-xyz", require_binding=True,
    )
    assert payload["cnf"]["jkt"] == "JKT-xyz"


# ---- NFR-ID-001: fail-closed (expiry, replay, missing binding) ---------

def test_expired_token_rejected(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
    )
    with pytest.raises(DelegationError):
        verify_persona_token(tok.jwt, public_key=pub, now=NOW + 301)  # past exp


def test_require_binding_rejects_unbound_token(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300, binding=TokenBindingType.none,
    )
    with pytest.raises(DelegationError):
        verify_persona_token(tok.jwt, public_key=pub, now=NOW + 5, require_binding=True)


def test_tampered_token_rejected(rsa_keys) -> None:
    priv, pub = rsa_keys
    tok = mint_persona_token(
        _claims(), private_key=priv, algorithm="RS256",
        issued_at=NOW, ttl_seconds=300,
    )
    # Flip a character in the signature segment.
    head, payload_seg, sig = tok.jwt.split(".")
    tampered = f"{head}.{payload_seg}.{sig[:-2]}XY"
    with pytest.raises(DelegationError):
        verify_persona_token(tampered, public_key=pub, now=NOW + 5)


def test_token_binding_values_match_gharra() -> None:
    # Must equal gharra.core.models.TokenBinding string values (models.py:75).
    assert {b.value for b in TokenBindingType} == {
        "none", "mtls_cnf_x5t_s256", "dpop",
    }
