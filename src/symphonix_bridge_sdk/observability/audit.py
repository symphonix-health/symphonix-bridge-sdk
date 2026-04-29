"""FHIR AuditEvent-compatible audit logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

_audit_log = logging.getLogger("audit")


class AuditLogger:
    """Emits HL7 FHIR R4 AuditEvent-compatible structured audit records."""

    def __init__(self, service_name: str):
        self.service = service_name

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_id: str,
        outcome: str = "0",
        details: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "resourceType": "AuditEvent",
            "type": {
                "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
                "code": "rest",
            },
            "action": action,
            "recorded": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,
            "agent": [{"who": {"identifier": {"value": actor_id}}, "requestor": True}],
            "entity": [{"what": {"reference": f"{resource_type}/{resource_id}"}}],
            "source": {"observer": {"display": self.service}},
        }
        if details:
            event["_details"] = details
        _audit_log.info(json.dumps(event, separators=(",", ":")))

