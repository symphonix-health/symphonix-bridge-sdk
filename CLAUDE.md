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
