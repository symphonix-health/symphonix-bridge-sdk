"""Workspace-root conftest.py — hydrates User-scope env vars."""

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
        "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET",
        "BT_FHIR_BASE_URL", "BT_FHIR_TOKEN",
        "FHIR_BASE_URL", "FHIR_AUTH_TOKEN",
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
        "MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET",
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
