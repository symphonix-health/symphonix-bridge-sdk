# CLAUDE.md

_(auto-bootstrapped by caid-agent/scripts/bootstrap_bt_repo.py)_

## BulletTrain Integration Constitution

This repo is governed by the BulletTrain Integration Constitution. Workflow /
orchestration / handler / route / service code in this repo MUST NOT call
external systems directly -- all external traffic routes through the
BulletTrain Integration Engine (`bullettrain.connectors.*`) or the
api_gateway hub.

- Constitution: `c:/Users/hgeec/github/caid-agent/docs/architecture/bullettrain-integration-constitution.md`
- Anti-pattern catalogue: `c:/Users/hgeec/github/caid-agent/docs/architecture/integration-anti-patterns.md`
- ADR-004: `c:/Users/hgeec/github/caid-agent/docs/architecture/architecture-decision-records/ADR-004-bullettrain-integration-constitution.md`

Enforcement in this repo:
- `.semgrep/` -- run with `semgrep --config .semgrep/`
- `.github/PULL_REQUEST_TEMPLATE.md` -- 11-item architecture compliance checklist
- User-level Claude Code hook (`~/.claude/hooks/bullettrain_integration_guard.py`) blocks violations at write time.

PRs that violate constitution rules are rejected per rule 7. If a temporary
bypass is genuinely required, link an exception ADR (status: Proposed,
expiry date set, owner named) -- without an ADR, the bypass is invalid.
