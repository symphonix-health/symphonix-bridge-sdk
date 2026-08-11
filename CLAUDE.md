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

## Two source packages: `bridge_sdk` (canonical SDK) + `symphonix_bridge_sdk` (observability migration target)

`pyproject.toml`'s `[tool.hatch.build.targets.wheel]` ships two top-level
packages from `src/`: `bridge_sdk` (everything documented above -- adapters,
signal governance, council deliberation, human handoff, superpersona
contract, GRA) and `symphonix_bridge_sdk`, a newer package matching the repo
name that currently holds only `observability/`. `src/bridge_sdk/observability/__init__.py`
is now a thin backward-compatible shim (`from symphonix_bridge_sdk.observability
import *`) -- the real implementation lives under `symphonix_bridge_sdk`, so
both `from bridge_sdk.observability import ...` and
`from symphonix_bridge_sdk.observability import ...` resolve to the same
code and pick up the same deprecation/guard behaviour described below. This
looks like the start of a package rename (`bridge_sdk` -> `symphonix_bridge_sdk`)
scoped to `observability/` so far; no other submodule has moved yet.

## `[observability]` optional extra + deprecation guard (2026-08-03, phase 1+2 of OTEL dep migration)

Commit `6031d1f` (PR #9, closing issue #4 -- "move observability to an
optional extra so lean consumers can drop OTEL entirely", the follow-up
tracked from `signalbox-mcp`'s own `CLAUDE.md`) adds a new
`[observability]` optional-dependencies group to `pyproject.toml`
(`opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-{fastapi,httpx,requests}`,
`opentelemetry-sdk`, `prometheus-client`, `sentry-sdk[fastapi]`), plus two
guards in `src/symphonix_bridge_sdk/observability/__init__.py` (and,
via the shim above, `src/bridge_sdk/observability/__init__.py` too):

- **Deprecation warning on import** -- any `import ...observability` emits a
  `DeprecationWarning` stating that the OpenTelemetry/Sentry/Prometheus stack
  will be removed from this package's CORE `dependencies` in the next major
  release, and that consumers should add `symphonix-bridge-sdk[observability]`
  to their own requirements to keep the import working after that happens.
  `pyproject.toml`'s pytest `filterwarnings` silences this specific warning
  for this repo's own test suite.
- **Fail-loud `ImportError` guard** -- if any of
  `opentelemetry.sdk.trace` / `opentelemetry.exporter.otlp` / `sentry_sdk` /
  `prometheus_client` is genuinely missing, importing `observability` raises
  an `ImportError` naming the missing module(s) and the install command,
  instead of a cryptic failure deep inside a submodule.

**This is phase 1+2 only.** As of this commit, `opentelemetry-*` /
`sentry-sdk` / `prometheus-client` are STILL listed in `pyproject.toml`'s
core `dependencies` (unchanged) -- a plain `pip install symphonix-bridge-sdk`
still pulls the full OTEL/Sentry/Prometheus stack in. Phase 1+2 only adds the
opt-in extra, the deprecation warning, and the fail-loud guard; removing the
observability stack from core `dependencies` (the actual "lean consumer"
win) is deferred to "the next major release" and has not landed yet -- do
not assume `signalbox-mcp`'s bootstrap script (which still installs the
observability deps directly, per its own `CLAUDE.md`) can be simplified
until that later phase ships.

## Fix: the fail-loud missing-stack `ImportError` guard never actually fired (2026-08-05)

Commit `4156085` fixes the "Fail-loud `ImportError` guard" described above.
`importlib.util.find_spec()` only returns `None` for an ABSENT top-level
module; for a dotted name it imports the parent package first, so with the
observability stack genuinely absent, `find_spec("opentelemetry.sdk.trace")`
raised `ModuleNotFoundError` instead of returning `None`. The friendly
`ImportError` the guard is supposed to raise never fired -- a caller with the
stack missing got exactly the cryptic `ModuleNotFoundError: No module named
'opentelemetry'` the guard exists to prevent.

`src/symphonix_bridge_sdk/observability/__init__.py` now probes via a new
`_is_missing()` helper that also treats `ImportError`/`ValueError` raised by
`find_spec` as "missing"; `src/bridge_sdk/observability` inherits the fix
through the re-export shim described above, with no further change needed
there. The commit also removed a `unittest.mock.patch` from
`tests/test_observability.py` (posture rule 18 / L-259 -- no internal mocks)
that had been faking `find_spec` to return `None` directly for the missing
case -- a behaviour the real function never exhibits for a dotted name, so
the mocked test was asserting a branch production could never reach. The
replacement test runs the probe for real in a child interpreter started with
`-I -S` so site-packages is genuinely off `sys.path`, with a known-true
control that fails loudly if the child turns out not to be stack-free.
