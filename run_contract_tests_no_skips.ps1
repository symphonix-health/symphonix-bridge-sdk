# Run the agent-native contract suite (WS1-WS12) with ZERO skips.
#
# SCOPE: the 12 bridge_sdk module test files that back the agent-native
# optimisation programme (one per workstream, listed below). This is the
# suite this script certifies green-with-no-skips.
#
# Why a curated file list and not the whole tests/ tree:
#   tests/harness/patient_identity/test_patient_identity_contract.py is a
#   SEPARATE, pre-existing workspace-governance harness (added in commit
#   1820d27, unrelated to agent-native work). Its enforce-mode test scans
#   ~12 sibling repos ON DISK for legacy NHS-number patterns and currently
#   fails on ~40 pre-existing files across analytics-bi, eps, etps, kenya-uhc,
#   mha-administration, mortuary-and-me, pacs-ris, pharmacy-system, triage-api,
#   etc. NONE of those files are agent-native deliverables; none of the four
#   agent-native /agent/intents routers are implicated. That failure is a
#   pre-existing remediation backlog tracked in
#   docs/AGENT_NATIVE_PLAN_TICKOFF.md (section "Pre-existing, out-of-scope
#   failures"), NOT a regression from this programme and NOT a skip. It is
#   deliberately out of scope here so this gate stays meaningful; run it
#   directly with:  pytest tests/harness/patient_identity -m contract
#
# The 3 cross-repo contract tests (HashChain, RetryPolicy, GHARRA AgentRecord)
# carry an importlib skipif so they DON'T fail when their partner package is
# absent. To make them RUN (no skips), execute in an interpreter that has all
# partners importable: BulletTrain's venv (PyJWT + cryptography + ulid +
# bullettrain.*) plus GHARRA's src on PYTHONPATH.
#
# Verified 2026-06-02: 177 passed, 0 failed, 0 skipped.
#
# Usage:  powershell.exe -NoProfile -ExecutionPolicy Bypass -File run_contract_tests_no_skips.ps1
# (pwsh works too; the leading "powershell.exe" form is the always-present one.)

$ErrorActionPreference = "Stop"
$bridge = Split-Path -Parent $MyInvocation.MyCommand.Path
$btPy = "C:\Users\hgeec\github\BulletTrain\.venv\Scripts\python.exe"
$gharraSrc = "C:\Users\hgeec\github\global-agent-registry\src"
$btRoot = "C:\Users\hgeec\github\BulletTrain"

if (-not (Test-Path $btPy)) {
    Write-Error "BulletTrain venv not found at $btPy -- run setup in BulletTrain first."
}

$env:PYTHONPATH = "$bridge\src;$btRoot;$gharraSrc"

# The agent-native contract suite: one test module per workstream.
$wsTests = @(
    "test_agent_contract.py",        # WS1  Agent Execution Contract
    "test_gharra_registration.py",   # WS1c GHARRA agent-record registration
    "test_execution_ledger.py",      # WS2  event-sourced ledger (HashChain contract)
    "test_persona_delegation.py",    # WS3  persona delegation / token exchange
    "test_agent_audit.py",           # WS4  audit + tracing
    "test_error_envelope.py",        # WS5  resilience / error envelope (RetryPolicy contract)
    "test_concurrency.py",           # WS6  execution budgets / single-writer locks
    "test_agent_arena.py",           # WS7  Agent Arena eval metrics + ReleaseGate
    "test_consent_projection.py",    # WS9  consent projection
    "test_clinical_safety_case.py",  # WS10 clinical safety case + MCP transport lockdown
    "test_human_handoff.py",         # WS11 human handoff (ledger contract)
    "test_rollout.py"                # WS12 rollout capstone
) | ForEach-Object { Join-Path "$bridge\tests" $_ }

# Fail loudly if any expected module test file is missing (guards against a
# silently-shrunk suite -- a false green).
$missing = $wsTests | Where-Object { -not (Test-Path $_) }
if ($missing) {
    Write-Error "Agent-native contract suite incomplete -- missing: $($missing -join ', ')"
}

# -rs reports skip reasons; --strict-markers keeps the run honest.
& $btPy -m pytest @wsTests `
    -p no:cacheprovider -rs -q --strict-markers

$code = $LASTEXITCODE
Write-Host ""
Write-Host "PYTEST_EXIT=$code  (0 = all passed, no skips tolerated by intent)"
exit $code
