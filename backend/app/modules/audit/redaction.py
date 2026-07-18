"""Recursive payload redaction. Secrets and common banking PII never reach storage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_SECRET_KEYS = re.compile(
    r"(^|_)(authorization|auth|api_?key|access_?token|refresh_?token|password|secret|cookie)($|_)",
    re.IGNORECASE,
)
_ACCOUNT_KEYS = re.compile(
    r"(^|_)(account_?number|citizen_?id|national_?id|passport_?number)($|_)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{9,19}(?!\d)")


@dataclass(frozen=True)
class RedactedPayload:
    value: Any
    count: int
    paths: tuple[str, ...]


def redact_payload(value: Any) -> RedactedPayload:
    paths: list[str] = []

    def walk(item: Any, path: str) -> Any:
        if isinstance(item, dict):
            result: dict[str, Any] = {}
            for key, child in item.items():
                child_path = f"{path}.{key}" if path else str(key)
                if _SECRET_KEYS.search(str(key)) or _ACCOUNT_KEYS.search(str(key)):
                    paths.append(child_path)
                    result[str(key)] = "[REDACTED]"
                else:
                    result[str(key)] = walk(child, child_path)
            return result
        if isinstance(item, list | tuple):
            return [walk(child, f"{path}[{index}]") for index, child in enumerate(item)]
        if isinstance(item, str):
            cleaned, bearer_count = _BEARER.subn("Bearer [REDACTED]", item)
            cleaned, digit_count = _LONG_DIGITS.subn("[REDACTED_NUMBER]", cleaned)
            if bearer_count or digit_count:
                paths.append(path or "$value")
            return cleaned
        return item

    redacted = walk(value, "")
    return RedactedPayload(redacted, len(paths), tuple(paths))
