"""Persona Delegation: short-lived, scoped, sender-constrained persona tokens.

Workstream 3. Replaces persona *labels* with delegated, minimum-necessary
authority bound to clinical context. Depends on WS1-2.

Design decision: EXTEND GHARRA, don't reinvent. Verified prior art:

- ``gharra.core.models.TokenBinding`` already enumerates
  ``none`` / ``mtls_cnf_x5t_s256`` / ``dpop`` (models.py:75). We reuse those
  EXACT string values so a token minted here is intelligible to the GHARRA
  gateway's ``cnf.x5t#S256`` check (gateway.py:267).
- ``gharra.core.signing._ALLOWED_ALGORITHMS`` rejects HS256/"none" for registry
  signatures (signing.py:34). We mirror that allowlist: persona tokens are
  asymmetric-only (RS256/ES256/EdDSA). That is precisely the plan's "migrate
  Nexus mesh auth from HS256 to RS256/DPoP-bound" requirement (FR-ID + NFR-ID-002)
  expressed as a hard mint-time guard: ``mint`` REFUSES HS256.
- GHARRA personas (``api/routes/personas.py``) carry ``allowed_purposes`` but
  NO scope/TTL/patient-context binding. Token exchange / delegation (RFC 8693)
  is ABSENT in both repos. Those are the genuine new build here.

The six bindings the plan mandates on every persona token:
patient context, purpose of use, allowed systems, max concurrency, emergency
flag, and UI/API action scopes.

Requirements: FR-ID-001..003, NFR-ID-001..002
(``BulletTrain/docs/PERSONA_DELEGATION_REQUIREMENTS.md``).

This module degrades gracefully without PyJWT: ``mint``/``verify`` raise a clear
``DelegationError`` if ``pyjwt`` is not installed, but the binding model,
scope-unification, and fail-closed checks are pure-python and always available.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "DelegationError",
    "PersonaScope",
    "PersonaToken",
    "PersonaTokenClaims",
    "TokenBindingType",
    "mint_persona_token",
    "unify_scope",
    "verify_persona_token",
]

# Asymmetric-only: mirrors gharra.core.signing._ALLOWED_ALGORITHMS (signing.py:34).
# HS256/"none" are deliberately excluded -- the WS3 anti-goal is symmetric mesh
# secrets. Mint refuses anything not in this set.
ALLOWED_ALGORITHMS: frozenset[str] = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "EdDSA"}
)


class DelegationError(Exception):
    """Raised on an invalid delegation request or a fail-closed auth violation."""


class TokenBindingType(str, Enum):
    """Sender-constraint binding -- value-identical to GHARRA's TokenBinding.

    (``gharra.core.models.TokenBinding``, models.py:75). Kept in lockstep so a
    persona token is intelligible to the GHARRA gateway without translation.
    """

    none = "none"
    mtls_cnf_x5t_s256 = "mtls_cnf_x5t_s256"
    dpop = "dpop"


# Canonical UI/API action scopes (FR-ID-002 unification). GHARRA today carries
# coarse "gharra:read"/"gharra:*" API-key scopes plus persona allowed_purposes;
# SignalBox carries none. This is the single vocabulary all three resolve to.
class PersonaScope(str, Enum):
    """Unified UI/API action scope vocabulary across GHARRA, Nexus, SignalBox."""

    api_read = "api:read"
    api_write = "api:write"
    ui_navigate = "ui:navigate"
    ui_fill = "ui:fill"
    ui_submit = "ui:submit"
    task_execute = "task:execute"
    task_escalate = "task:escalate"


# Map legacy / per-service scope strings onto the unified vocabulary (FR-ID-002).
_LEGACY_SCOPE_MAP: dict[str, PersonaScope] = {
    "gharra:read": PersonaScope.api_read,
    "gharra:*": PersonaScope.api_write,
    "read": PersonaScope.api_read,
    "write": PersonaScope.api_write,
    "navigate": PersonaScope.ui_navigate,
    "fill": PersonaScope.ui_fill,
    "submit": PersonaScope.ui_submit,
    "execute": PersonaScope.task_execute,
    "escalate": PersonaScope.task_escalate,
}


def unify_scope(raw: str) -> PersonaScope:
    """Resolve a legacy/per-service scope string to the unified vocabulary.

    Raises ``DelegationError`` on an unknown scope (fail-closed: never silently
    grant an unrecognised authority).
    """
    if raw in _LEGACY_SCOPE_MAP:
        return _LEGACY_SCOPE_MAP[raw]
    try:
        return PersonaScope(raw)
    except ValueError:
        raise DelegationError(f"unknown scope '{raw}'") from None


@dataclass(frozen=True)
class PersonaTokenClaims:
    """The six mandated bindings carried by every persona token (FR-ID-001)."""

    persona: str  # persona key, e.g. "triage-intake-agent"
    patient_context: str | None  # 1. patient context (FHIR ref) or None
    purpose_of_use: str  # 2. purpose of use (treatment/emergency/...)
    allowed_systems: tuple[str, ...]  # 3. allowed systems (component ids)
    max_concurrency: int  # 4. max concurrent workflows
    emergency: bool  # 5. emergency (break-glass) flag
    scopes: tuple[PersonaScope, ...]  # 6. UI/API action scopes
    subject: str = "agent"  # the delegated principal (the agent)
    actor: str | None = None  # RFC 8693 act: who delegated (the user)
    token_id: str | None = None  # JWT ID for audit without storing the token
    contract_id: str | None = None  # Superpersona contract binding
    contract_version: str | None = None

    def to_jwt_payload(self, *, issued_at: int, ttl_seconds: int) -> dict[str, Any]:
        """Build the JWT claim set, including RFC 8693 ``act`` and ``exp``."""
        if ttl_seconds <= 0:
            raise DelegationError("ttl_seconds must be positive (short-lived)")
        payload: dict[str, Any] = {
            "sub": self.subject,
            "persona": self.persona,
            "patient_context": self.patient_context,
            "purpose_of_use": self.purpose_of_use,
            "allowed_systems": list(self.allowed_systems),
            "max_concurrency": self.max_concurrency,
            "emergency": self.emergency,
            "scope": " ".join(s.value for s in self.scopes),
            "iat": issued_at,
            "exp": issued_at + ttl_seconds,
        }
        if self.token_id is not None:
            payload["jti"] = self.token_id
        if self.contract_id is not None:
            payload["contract_id"] = self.contract_id
        if self.contract_version is not None:
            payload["contract_version"] = self.contract_version
        if self.actor is not None:
            # RFC 8693 delegation: the token acts on behalf of `actor`.
            payload["act"] = {"sub": self.actor}
        return payload


@dataclass(frozen=True)
class PersonaToken:
    """A minted persona token plus the binding metadata needed to verify it."""

    jwt: str
    algorithm: str
    binding: TokenBindingType
    cnf: dict[str, str] = field(default_factory=dict)  # confirmation claim


def _confirmation_claim(
    binding: TokenBindingType,
    *,
    cert_thumbprint: str | None,
    dpop_jkt: str | None,
) -> dict[str, str]:
    """Build the RFC 8705 / RFC 9449 confirmation claim for a binding.

    Fail-closed: a binding that names a constraint MUST supply its material.
    """
    if binding is TokenBindingType.mtls_cnf_x5t_s256:
        if not cert_thumbprint:
            raise DelegationError("mtls binding requires a cert_thumbprint")
        return {"x5t#S256": cert_thumbprint}
    if binding is TokenBindingType.dpop:
        if not dpop_jkt:
            raise DelegationError("dpop binding requires a dpop_jkt")
        return {"jkt": dpop_jkt}
    return {}


def mint_persona_token(
    claims: PersonaTokenClaims,
    *,
    private_key: Any,
    algorithm: str,
    issued_at: int,
    ttl_seconds: int = 300,
    binding: TokenBindingType = TokenBindingType.none,
    cert_thumbprint: str | None = None,
    dpop_jkt: str | None = None,
    high_risk: bool = False,
) -> PersonaToken:
    """Mint a short-lived, scoped, optionally sender-constrained persona token.

    - Refuses HS256/symmetric algorithms (FR-ID + NFR-ID-002): asymmetric only.
    - ``ttl_seconds`` defaults to 300 s (short-lived, FR-ID-001).
    - ``high_risk`` actions REQUIRE a DPoP or mTLS binding (FR-ID-003): minting a
      high-risk token with ``binding=none`` fails closed.
    """
    if algorithm not in ALLOWED_ALGORITHMS:
        raise DelegationError(
            f"algorithm '{algorithm}' not allowed; persona tokens are "
            f"asymmetric-only ({sorted(ALLOWED_ALGORITHMS)}). HS256/none refused."
        )
    if high_risk and binding is TokenBindingType.none:
        raise DelegationError(
            "high-risk action requires a DPoP or mTLS sender-constrained binding"
        )
    cnf = _confirmation_claim(
        binding, cert_thumbprint=cert_thumbprint, dpop_jkt=dpop_jkt
    )
    payload = claims.to_jwt_payload(issued_at=issued_at, ttl_seconds=ttl_seconds)
    if cnf:
        payload["cnf"] = cnf

    try:
        import jwt  # PyJWT
    except ImportError:  # pragma: no cover - exercised only without pyjwt
        raise DelegationError(
            "PyJWT is required to mint persona tokens (pip install pyjwt)"
        ) from None

    token = jwt.encode(payload, private_key, algorithm=algorithm)
    return PersonaToken(jwt=token, algorithm=algorithm, binding=binding, cnf=cnf)


def verify_persona_token(
    token: str,
    *,
    public_key: Any,
    algorithms: list[str] | None = None,
    now: int,
    cert_thumbprint: str | None = None,
    dpop_jkt: str | None = None,
    require_binding: bool = False,
) -> dict[str, Any]:
    """Verify a persona token and its sender-constraint, fail-closed.

    Raises ``DelegationError`` on: a disallowed algorithm, an expired token, a
    binding mismatch (presented thumbprint != ``cnf``), or a missing binding when
    ``require_binding`` is set (high-risk path, FR-ID-003 / NFR-ID-001).
    """
    allowed = algorithms or sorted(ALLOWED_ALGORITHMS)
    bad = set(allowed) - ALLOWED_ALGORITHMS
    if bad:
        raise DelegationError(
            f"verify refuses non-asymmetric algorithms: {sorted(bad)}"
        )

    try:
        import jwt  # PyJWT
    except ImportError:  # pragma: no cover
        raise DelegationError("PyJWT is required to verify persona tokens") from None

    try:
        # Expiry is asserted explicitly below against the injected ``now`` so the
        # check is deterministic and clock-independent; disable PyJWT's own
        # wall-clock iat/nbf/exp validation to avoid double, non-deterministic
        # time checks. Signature + algorithm verification stay fully enforced.
        payload = jwt.decode(
            token,
            public_key,
            algorithms=allowed,
            options={"verify_exp": False, "verify_iat": False, "verify_nbf": False},
        )
    except Exception as exc:  # PyJWT raises many subclasses; normalise to fail-closed
        raise DelegationError(f"token verification failed: {exc}") from None

    # Explicit expiry check against the caller's clock (fail-closed, testable).
    exp = payload.get("exp")
    if exp is None or now >= exp:
        raise DelegationError("token expired")

    cnf = payload.get("cnf") or {}
    if require_binding and not cnf:
        raise DelegationError("binding required but token carries no cnf claim")
    if "x5t#S256" in cnf:
        if cert_thumbprint != cnf["x5t#S256"]:
            raise DelegationError("mTLS cert thumbprint does not match cnf.x5t#S256")
    if "jkt" in cnf:
        if dpop_jkt != cnf["jkt"]:
            raise DelegationError("DPoP key thumbprint does not match cnf.jkt")
    return payload


def jkt_from_jwk(jwk: dict[str, str]) -> str:
    """RFC 7638 JWK SHA-256 thumbprint (base64url), used for DPoP ``jkt``.

    Small, dependency-free helper so tests can construct a real ``jkt`` without
    pulling in a JOSE stack.
    """
    import base64
    import json

    # RFC 7638: lexicographically-ordered required members, no whitespace.
    members = {
        k: jwk[k] for k in sorted(jwk) if k in {"crv", "e", "kty", "n", "x", "y"}
    }
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
