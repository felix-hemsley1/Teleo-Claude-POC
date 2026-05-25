"""Redaction rules applied to every captured event before storage.

Pure logic — no Windows dependencies — so it can be unit-tested anywhere.
"""
import re
from typing import Optional

from capture.deny_list import (
    DENY_LIST_PROCESSES,
    DENY_LIST_URL_PATTERNS,
    PII_PATTERNS,
)

_URL_REGEXES = [re.compile(p, re.IGNORECASE) for p in DENY_LIST_URL_PATTERNS]
_PII_REGEXES = {name: re.compile(p) for name, p in PII_PATTERNS.items()}


def should_drop(process_name: str, url: Optional[str]) -> bool:
    """True if the whole event must be dropped (deny-listed app or URL)."""
    if process_name and process_name.lower() in DENY_LIST_PROCESSES:
        return True
    if url:
        for rx in _URL_REGEXES:
            if rx.search(url):
                return True
    return False


def redact_event(event: dict) -> Optional[dict]:
    """Apply redaction rules to an event dict.

    Returns the (possibly modified) event, or None if the event must be
    dropped entirely. Mutates and returns the same dict for convenience.

    Expected keys: process_name, url, is_password, control_value.
    """
    process_name = (event.get("process_name") or "").lower()
    url = event.get("url")

    if should_drop(process_name, url):
        return None

    flags = list(event.get("pii_flags") or [])
    redacted = bool(event.get("redacted", False))

    if event.get("is_password"):
        event["control_value"] = None
        flags.append("password_field")
        redacted = True

    value = event.get("control_value")
    if value:
        for name, rx in _PII_REGEXES.items():
            if rx.search(value):
                value = rx.sub("[REDACTED]", value)
                flags.append(name)
                redacted = True
        event["control_value"] = value

    event["pii_flags"] = flags
    event["redacted"] = redacted
    return event
