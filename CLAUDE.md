<!-- global-workspace-instructions:start -->

## Global workspace instructions

Also read and follow `C:\Users\hgeec\github\CLAUDE.md` and `C:\Users\hgeec\github\AGENTS.md` before working in this repository. These repo-local instructions remain in force. If a repo-local instruction conflicts with global files, prefer the more specific repo-local instruction unless a system, developer, or user instruction says otherwise.

<!-- global-workspace-instructions:end -->

# CLAUDE.md

_(auto-bootstrapped by caid-agent/scripts/bootstrap_bt_repo.py)_

## BulletTrain Integration Constitution

This repo is governed by the BulletTrain Integration Constitution. Workflow /
orchestration / handler / route / service code in this repo MUST NOT call
external systems directly -- all external traffic routes through the
BulletTrain Integration Engine (`bullettrain.connectors.*`) or the
api_gateway hub.

- Constitution: `../caid-agent/docs/architecture/bullettrain-integration-constitution.md`
- Anti-pattern catalogue: `../caid-agent/docs/architecture/integration-anti-patterns.md`
- ADR-004: `../caid-agent/docs/architecture/architecture-decision-records/ADR-004-bullettrain-integration-constitution.md`

Enforcement in this repo:
- **Load-bearing:** user-level Claude Code hook `~/.claude/hooks/bullettrain_integration_guard.py` blocks violations at write time. This is the only enforcement layer that fires automatically.
- **Review-time guidance only** (not CI-enforced): `.semgrep/` rules run on demand via `semgrep --config .semgrep/`; `.github/PULL_REQUEST_TEMPLATE.md` carries the 11-item architecture compliance checklist.
- **GitHub Actions disabled estate-wide since 2026-05-11** -- workflow YAMLs in `.github/workflows/` are preserved in-tree but inert; semgrep and the PR template are not enforced by CI, only by reviewer attention. Per workspace memory `reference_constitution_enforcement_layers.md`.

PRs that violate constitution rules are rejected per rule 7. If a temporary
bypass is genuinely required, link an exception ADR (status: Proposed,
expiry date set, owner named) -- without an ADR, the bypass is invalid.

## Scope override guard: dual-control, audited safety-scope expansion (2026-06-21)

`src/bridge_sdk/scope_override_guard.py` (commit `02f1185`) adds a fail-closed
`ScopeOverrideGuard` for any caller that needs to grant a `PersonaScope`
expansion beyond what a persona was originally issued. `ScopeOverrideGuard.evaluate()`
takes a `ScopeOverrideRequest` (persona, primary/secondary actor, requested vs.
granted scopes, rationale, `safety_case_ref`, correlation id) and returns a
`ScopeOverrideDecision` -- permitted only when every excess scope is in the
caller-configured `permitted_override_scopes` set, the rationale meets
`min_rationale_chars`, a `safety_case_ref` is present, and (depending on
configuration) a named secondary approver's token validates against a
`FileDualControlApprovalStore`. Every decision is hashed and written to a
`FileScopeOverrideAuditSink`, and `ScopeOverrideMetrics` tracks false-positive/
false-negative rates; `make_scope_override_metrics_router()` exposes them as a
FastAPI `APIRouter`. All of `FileDualControlApprovalStore`,
`FileScopeOverrideAuditSink`, `ScopeOverrideDecision`, `ScopeOverrideError`,
`ScopeOverrideGuard`, `ScopeOverrideMetrics`, `ScopeOverrideRequest`,
`make_scope_override_metrics_router`, and `token_sha256` are re-exported from
the package root (`bridge_sdk`).

## Evidence resolution fails closed without seeded-simulation grounding (2026-06-22)

`src/bridge_sdk/evidence.py` (commit `0b44492`) adds nine grounding fields to
`ResolvedEvidence` -- `source_span_ref`, `target_evidence_ref`,
`seeded_dataset_id`, `persona_id`, `scenario_id`, `service_route`,
`permission_scope`, `telemetry_ref`, `synthetic_telemetry`, and
`live_production_evidence` -- plus the new
`seeded_simulation_grounding_failures(resolved)` / `is_seeded_simulation_grounded(resolved)`
helpers (both re-exported from `bridge_sdk`). `signal_from_evidence(...)` now
refuses to promote a signal to `attested` -- returning the conservative `base`
signal instead -- whenever `seeded_simulation_grounding_failures()` reports any
missing or synthetic/live-only component, in addition to the pre-existing
`tamper == "altered"` check. A caller relying on `signal_from_evidence` to
attest a claim now needs `ResolvedEvidence` populated with a full evidence
chain (source span, target-repo evidence, seeded dataset, persona, scenario,
service route, and permission scope), not just a valid signature.

## Human handoff / release gate: receiver evidence is now required (2026-07-02)

`src/bridge_sdk/human_handoff.py::HandoffInbox.resume()` and
`src/bridge_sdk/agent_arena.py::ReleaseGate.evaluate()` both gained a
`receiver_observer_evidence` parameter (commit `66d00a2`). This is a breaking
change to callers written against the pre-2026-07-02 shape:

- `HandoffInbox.resume(workflow_id, outcome=...)` **without**
  `receiver_observer_evidence` now raises `HandoffError("resume requires
  receiver observer evidence")`. Callers must construct and pass a
  `ReceiverObserverEvidence` instance (which is itself `.validate()`-ed before
  the resume is accepted).
- `ReleaseGate.evaluate(...)` **without** `receiver_observer_evidence=True` now
  silently adds `"receiver_observer_evidence"` to `failing_criteria` -- and
  flips `promoted` to `False` -- for any run where `metrics.human_handoff_rate
  > 0`. There is no exception; a caller not passing the flag will simply stop
  being promoted for handoff-containing runs.

Neither `signalbox-mcp`'s `action_resolver.govern_action()` /
`signal_governance.evaluate_signal_action()` nor `clinical-pathways`'
`integration/bridge_client.py` currently call `HandoffInbox.resume()` or
`ReleaseGate.evaluate()`, so no in-workspace caller breaks today -- but any new
integration against the human-handoff or release-gate surface must supply
`receiver_observer_evidence` from the start.

## SignalBox headed computer-use tool binding added (2026-07-11)

Commit `e6876c9` added `signalbox-mcp.computer-use-headed` to
`SIGNALBOX_TOOL_IDS` and the governed tool-binding table in
`src/bridge_sdk/superpersona_contract.py`. The binding carries
`protocol: browser` and is included in `mcp_tool_policy()`'s
`allowed_tools` alongside the existing `signalbox.capture-session`,
`signalbox-mcp.invoke-tool`, and `signalbox-mcp.capture-attestation`
bindings -- so a governed persona contract can now authorise headed
computer-use browser sessions via SignalBox-MCP, not just the prior
invoke-tool/capture-session/capture-attestation set. See
`src/bridge_sdk/superpersona_contract.py` and
`test_contract_policy_includes_signalbox_for_governed_execution` in
`tests/test_superpersona_contract.py`.
