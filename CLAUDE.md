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
