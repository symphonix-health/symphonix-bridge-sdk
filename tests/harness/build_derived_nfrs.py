"""symphonix-bridge-sdk — caid-agent ISO/IEC 25010:2023 NFR derivation harness.
against this repo's requirements_superset.json and emit the result as
``derived_nfrs.json`` next to the superset.

This script is the contract between caid-agent (the orchestrator that
owns the rule library) and consumer repos (which own their FR
catalogues). Re-running it after the superset changes refreshes the
derived NFR set automatically — no per-repo NFR maintenance required.

Usage::

    python tests/harness/build_derived_nfrs.py

The engine is loaded from ``../caid-agent/src`` (workspace-sibling)
or from an installed ``caid`` package, whichever is found first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SUPERSET = ROOT / "tests" / "harness" / "requirements_superset.json"
OUT = ROOT / "tests" / "harness" / "derived_nfrs.json"

# Workspace-sibling caid-agent — preferred so changes to the engine flow
# without re-publishing a package.
_SIBLING_CAID_SRC = ROOT.parent / "caid-agent" / "src"
if _SIBLING_CAID_SRC.exists():
    sys.path.insert(0, str(_SIBLING_CAID_SRC))


def _scale_tier_for_subsystem(subsystem: str) -> str:
    """Heuristic scale-tier per workspace.

    The legacy queue (eps, etps, gharra, etc.) and clinical paths run as
    'sovereign' — patient-data scale + tight RPO/RTO. Everything else
    defaults to 'production'.
    """
    sovereign = {
        "eps", "etps", "global-agent-registry", "kenya-uhc-implementation",
        "clinical-pathways", "signalbox-mcp", "csaa", "triage-api",
    }
    return "sovereign" if subsystem in sovereign else "production"


def _project_type_for_subsystem(subsystem: str) -> str:
    """Heuristic project-type per workspace."""
    if subsystem in {"design-system"}:
        return "design_system"
    if subsystem in {"symphonix-public", "healthcare-pain-points-plan",
                     "symphonix-eps-ig"}:
        return "docs_site"
    if subsystem in {"symphonix-bridge-sdk"}:
        return "sdk"
    return "backend_api"


def _regulatory_regime_for_subsystem(subsystem: str) -> list[str]:
    """Heuristic regulatory regime per workspace."""
    base = ["ISO_27001", "ISO_27701"]
    if subsystem in {"eps", "etps", "clinical-pathways", "signalbox-mcp",
                     "csaa", "triage-api"}:
        base += ["NHS_DCB", "MHRA_SAMD", "GDPR"]
    if subsystem == "kenya-uhc-implementation":
        base += ["KENYA_DPA"]
    if subsystem == "global-agent-registry":
        base += ["EU_AI_ACT", "ISO_42001"]
    if subsystem in {"appointment-system", "scheduling-gateway",
                     "symphonix-bridge-sdk"}:
        base += ["HIPAA", "GDPR"]
    return base


def main() -> None:
    try:
        from caid.nfr_derivation import NFRDerivationEngine
        from caid.task_spec import RequirementLink
    except ImportError as exc:
        raise SystemExit(
            f"caid-agent NFR engine not importable ({exc}). "
            "Ensure ../caid-agent is checked out alongside this repo, "
            "or pip install -e ../caid-agent."
        ) from exc

    if not SUPERSET.exists():
        raise SystemExit(
            f"missing {SUPERSET} — run build_requirements_superset.py first"
        )

    superset = json.loads(SUPERSET.read_text(encoding="utf-8"))
    # Support both shapes: nested {metadata: {subsystem}} (newer repos)
    # and flat {subsystem} (older eps/etps style).
    if "metadata" in superset and "subsystem" in superset["metadata"]:
        subsystem = superset["metadata"]["subsystem"]
    else:
        subsystem = superset.get("subsystem", "unknown")

    # Convert superset entries into RequirementLink objects so the engine
    # can read .statement / .title / .rationale. We treat every superset
    # row as functional unless it explicitly self-categorises non-functional,
    # because some older supersets (eps/etps) don't carry a category field.
    frs = [
        RequirementLink(
            req_id=r["requirement_id"],
            title=r.get("title", r.get("requirement_id", "")),
            statement=r.get("statement", ""),
            rationale=r.get("rationale", ""),
            category="functional",
        )
        for r in superset["requirements"]
        if r.get("category", "functional") not in {"non-functional"}
    ]

    engine = NFRDerivationEngine()
    derived = engine.derive(
        frs=frs,
        project_type=_project_type_for_subsystem(subsystem),
        regulatory_regime=_regulatory_regime_for_subsystem(subsystem),
        scale_tier=_scale_tier_for_subsystem(subsystem),
    )

    payload = {
        "schema_version": "BT_DERIVED_NFRS_V1",
        "iso_model": "ISO/IEC 25010:2023",
        "metadata": {
            "subsystem": subsystem,
            "fr_count": len(frs),
            "derived_nfr_count": len(derived),
            "project_type": _project_type_for_subsystem(subsystem),
            "regulatory_regime": _regulatory_regime_for_subsystem(subsystem),
            "scale_tier": _scale_tier_for_subsystem(subsystem),
            "characteristics_covered": sorted({
                n.nfr_aspects[0] for n in derived if n.nfr_aspects
            }),
        },
        "derived_nfrs": [
            {
                "requirement_id": n.req_id,
                "title": n.title,
                "statement": n.statement,
                "rationale": n.rationale,
                "category": n.category,
                "priority": n.priority,
                "iso_25010_characteristic": (
                    n.nfr_aspects[0] if n.nfr_aspects else ""
                ),
                "iso_25010_subcharacteristic": (
                    n.nfr_aspects[1] if len(n.nfr_aspects) > 1 else ""
                ),
                "regulatory_ref": n.regulatory_ref,
                "trace_links": n.trace_links,
                "acceptance_criteria": [
                    {
                        "ac_id": ac.ac_id,
                        "given": ac.given,
                        "when": ac.when,
                        "then": ac.then,
                        "test_type": ac.test_type,
                    }
                    for ac in n.acceptance_criteria
                ],
            }
            for n in derived
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    chars = ", ".join(payload["metadata"]["characteristics_covered"])
    print(f"[OK] {OUT.name} — {len(derived)} NFRs from {len(frs)} FRs")
    print(f"     characteristics: {chars}")


if __name__ == "__main__":
    main()
