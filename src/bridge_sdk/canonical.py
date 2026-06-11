"""FHIR R4 Canonical Envelope — the pivot representation for all protocol translations."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TranslationDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CanonicalEnvelope(BaseModel):
    """FHIR R4 canonical representation that all protocols translate to/from."""

    envelope_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: f"COR-{uuid.uuid4().hex[:12]}")
    idempotency_key: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Protocol metadata
    source_protocol: str = ""
    target_protocol: str = ""
    direction: TranslationDirection = TranslationDirection.INBOUND

    # FHIR R4 canonical payload
    fhir_resources: list[dict[str, Any]] = Field(default_factory=list)

    # Terminology codes to preserve across hops
    loinc_codes: list[dict[str, str]] = Field(default_factory=list)
    snomed_codes: list[dict[str, str]] = Field(default_factory=list)

    # Raw source payload (for dead-letter / debug)
    raw_source: Any = None
    raw_source_type: str = ""

    # Translation metadata
    translation_ms: float = 0.0
    hop_count: int = 0
    hops: list[dict[str, Any]] = Field(default_factory=list)

    # Audit
    previous_hash: str = ""
    envelope_hash: str = ""

    # Error state
    error: str | None = None
    error_code: str | None = None

    # --- Phase 4 (G4, G16, G17): Consent + PHI + residency ---
    consent_token: str | None = None
    phi_classification: str = (
        "none"  # none | public | internal | restricted | sensitive
    )
    data_residency: list[str] = Field(default_factory=list)  # ISO country codes
    purpose_of_use: str = "treatment"  # treatment | emergency | research | operations

    # --- Phase 1 (G1): Dispatch mode + task tracking ---
    dispatch_mode: str = "sync"  # sync | stream | async
    task_id: str | None = None  # For async callback tracking
    callback_url: str | None = None

    # --- Phase 3 (G7): Trust material from GHARRA ---
    agent_trust: dict[str, Any] = Field(default_factory=dict)

    def compute_hash(self) -> str:
        content = f"{self.envelope_id}:{self.correlation_id}:{self.timestamp}:{self.previous_hash}"
        self.envelope_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.envelope_hash

    def add_hop(self, protocol: str, adapter: str, latency_ms: float) -> None:
        self.hops.append(
            {
                "protocol": protocol,
                "adapter": adapter,
                "latency_ms": latency_ms,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self.hop_count = len(self.hops)

    def extract_loinc_codes(self) -> list[dict[str, str]]:
        """Walk FHIR resources AND raw_source to extract LOINC coding entries."""
        codes: list[dict[str, str]] = []
        # Walk FHIR resources
        for resource in self.fhir_resources:
            self._walk_codings(resource, codes, "http://loinc.org")
        # Phase 2 (G5): Also walk raw_source for codes the adapter missed
        if self.raw_source and not codes:
            self._walk_codings(self.raw_source, codes, "http://loinc.org")
            # Also look for bare code+system pairs without the FHIR structure
            self._walk_bare_codes(self.raw_source, codes, "loinc")
        self.loinc_codes = codes
        return codes

    def extract_snomed_codes(self) -> list[dict[str, str]]:
        codes: list[dict[str, str]] = []
        for resource in self.fhir_resources:
            self._walk_codings(resource, codes, "http://snomed.info/sct")
        self.snomed_codes = codes
        return codes

    def assert_loinc_preserved(self, original_codes: list[dict[str, str]]) -> bool:
        """Phase 2 (G5): Verify LOINC codes are preserved after translation."""
        if not original_codes:
            return True
        current_code_set = {c["code"] for c in self.loinc_codes}
        original_code_set = {c["code"] for c in original_codes}
        return original_code_set.issubset(current_code_set)

    @staticmethod
    def _walk_codings(obj: Any, out: list, system: str) -> None:
        if isinstance(obj, dict):
            if obj.get("system") == system and "code" in obj:
                out.append(
                    {
                        "code": obj["code"],
                        "system": system,
                        "display": obj.get("display", ""),
                    }
                )
            for v in obj.values():
                CanonicalEnvelope._walk_codings(v, out, system)
        elif isinstance(obj, list):
            for item in obj:
                CanonicalEnvelope._walk_codings(item, out, system)

    @staticmethod
    def _walk_bare_codes(obj: Any, out: list, system_hint: str) -> None:
        """Walk looking for {code: "...", system: "http://loinc.org"} or loinc_code fields."""
        if isinstance(obj, dict):
            # Look for loinc_code / loinc_display pattern (Kafka events, REST payloads)
            if system_hint == "loinc" and obj.get("loinc_code"):
                out.append(
                    {
                        "code": str(obj["loinc_code"]),
                        "system": "http://loinc.org",
                        "display": obj.get("loinc_display", ""),
                    }
                )
            for v in obj.values():
                CanonicalEnvelope._walk_bare_codes(v, out, system_hint)
        elif isinstance(obj, list):
            for item in obj:
                CanonicalEnvelope._walk_bare_codes(item, out, system_hint)
