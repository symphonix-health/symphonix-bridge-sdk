from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from bridge_sdk.adapters.base import REQUIRED_GOVERNANCE_CONTROLS


ADAPTERS = [
    ("bridge_sdk.adapters.fhir", "FhirAdapter"),
    ("bridge_sdk.adapters.hl7v2", "Hl7v2Adapter"),
    ("bridge_sdk.adapters.kafka_adapter", "KafkaAdapter"),
    ("bridge_sdk.adapters.nexus_a2a", "NexusA2aAdapter"),
    ("bridge_sdk.adapters.rest", "RestAdapter"),
]


@pytest.mark.parametrize(("module_name", "class_name"), ADAPTERS)
def test_external_adapters_declare_governance_controls(
    module_name: str, class_name: str
) -> None:
    module = import_module(module_name)
    adapter_cls = getattr(module, class_name)

    assert tuple(adapter_cls.governance_controls) == REQUIRED_GOVERNANCE_CONTROLS

    text = Path(module.__file__).read_text(encoding="utf-8").lower()
    for control in REQUIRED_GOVERNANCE_CONTROLS:
        assert control in text
    assert "normalize" in text
