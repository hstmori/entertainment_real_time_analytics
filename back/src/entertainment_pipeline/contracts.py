"""Load and validate event payloads against versioned JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_FILES = {
    "user_activity": "user-activity-v1.schema.json",
    "booking": "booking-v1.schema.json",
    "subscription": "subscription-v1.schema.json",
    "event_attendance": "event-attendance-v1.schema.json",
}


class ContractValidationError(ValueError):
    """Raised when an event does not comply with its domain contract."""


class ContractRegistry:
    """Preloads JSON Schemas and exposes domain-aware validation."""

    def __init__(self, contracts_dir: Path) -> None:
        self.contracts_dir = contracts_dir
        self._validators: dict[str, Draft202012Validator] = {}

        for event_type, filename in SCHEMA_FILES.items():
            path = contracts_dir / filename
            if not path.is_file():
                raise FileNotFoundError(f"Contract file not found: {path}")
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            self._validators[event_type] = Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            )

    @property
    def event_types(self) -> tuple[str, ...]:
        return tuple(self._validators)

    def validate(self, event_type: str, payload: Mapping[str, Any]) -> None:
        try:
            validator = self._validators[event_type]
        except KeyError as exc:
            raise ContractValidationError(f"Unknown event type: {event_type}") from exc

        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
        if errors:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
                for error in errors
            )
            raise ContractValidationError(f"Invalid {event_type} event: {details}")

