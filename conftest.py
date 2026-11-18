"""Workspace-root conftest.py — hydrates User-scope env vars."""

from __future__ import annotations

import sys
from pathlib import Path


def _hydrate_user_scope_secrets() -> None:
    """Pull persistent User-scope env vars into the current process env.

    Sandboxed bash launchers / restricted CI runners often inherit only
    the parent's process env, dropping the Windows User-scope persistent
    block. Tests gated on real-API keys (Stripe, FHIR, etc.) then skip
    even when the user has those keys persisted. Read once at pytest
    startup so subprocesses (and pytest itself) see them.

    Reads only — never logs values. No-op on non-Windows.
    """
    import os

    if os.name != "nt":
        return
    keys = (
        "STRIPE_SECRET_KEY",
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "BT_FHIR_BASE_URL",
        "BT_FHIR_TOKEN",
        "FHIR_BASE_URL",
        "FHIR_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "MPESA_CONSUMER_KEY",
        "MPESA_CONSUMER_SECRET",
    )
    if all(os.environ.get(k) for k in keys):
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
            for key in keys:
                if os.environ.get(key):
                    continue
                try:
                    val, _ = winreg.QueryValueEx(h, key)
                except FileNotFoundError:
                    continue
                if isinstance(val, str) and val:
                    os.environ[key] = val
    except OSError:
        return


_hydrate_user_scope_secrets()


def _resolve_workspace_root(repo_root: Path) -> Path:
    import os

    for key in ("SYMPHONIX_WORKSPACE_ROOT", "CAID_WORKSPACE"):
        val = os.environ.get(key)
        if val and (Path(val) / "workspace-tooling").is_dir():
            return Path(val).resolve()
    parent = repo_root.parent
    if (parent / "workspace-tooling").is_dir():
        return parent.resolve()
    git_file = repo_root / ".git"
    if git_file.is_file():
        text = git_file.read_text(encoding="utf-8", errors="ignore").strip()
        if text.startswith("gitdir:"):
            gitdir = Path(text.split("gitdir:", 1)[1].strip())
            if len(gitdir.parents) >= 3:
                ws = gitdir.parents[3]
                if (ws / "workspace-tooling").is_dir():
                    return ws.resolve()
    return parent.resolve()


def _add_workspace_sibling_packages() -> None:
    """Make local sibling packages importable for real cross-repo contract tests."""
    import os

    repo_root = Path(__file__).resolve().parent
    workspace = _resolve_workspace_root(repo_root)
    os.environ["SYMPHONIX_WORKSPACE_ROOT"] = str(workspace)
    os.environ["CAID_WORKSPACE"] = str(workspace)
    candidates = (
        repo_root / "src",
        workspace / "BulletTrain",
        workspace / "global-agent-registry" / "src",
    )
    for candidate in candidates:
        if candidate.exists():
            path = str(candidate)
            if path not in sys.path:
                sys.path.insert(0, path)


_add_workspace_sibling_packages()


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    """Fail the pytest session if any test is skipped or xfailed (L-FIX-DO-NOT-SKIP)."""
    import os

    if os.environ.get("SYMPHONIX_ALLOW_TEST_SKIPS") == "1":
        return
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is None:
        return
    skipped = terminal.stats.get("skipped", [])
    xfailed = terminal.stats.get("xfailed", [])
    if skipped or xfailed:
        session.exitstatus = 1
