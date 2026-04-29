"""Sentry initialization with PHI scrubbing."""

from __future__ import annotations

import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

_PHI_KEYS = {"patient_id", "nhs_number", "dob", "address", "name", "email"}


def _scrub_mapping(value: dict[str, Any]) -> None:
    for key in list(value.keys()):
        if key.lower() in _PHI_KEYS:
            del value[key]
        elif isinstance(value.get(key), dict):
            _scrub_mapping(value[key])


def _before_send(event, hint):
    """Strip PHI from Sentry payloads before transmission."""

    for section in ("extra", "contexts", "tags"):
        value = event.get(section)
        if isinstance(value, dict):
            _scrub_mapping(value)
    return event


def init_sentry(service_name: str, environment: str = "production") -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", environment),
        release=os.getenv("APP_VERSION", "unknown"),
        server_name=service_name,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        before_send=_before_send,
    )

