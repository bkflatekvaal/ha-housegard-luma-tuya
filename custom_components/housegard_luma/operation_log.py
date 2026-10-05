"""Classify operation vocabulary without installation-specific identifiers."""

import re

from .parser import raw_bytes

_ACTIONS = {
    "Test Device SN": "test",
    "Silence Device SN": "hush",
    "SilHncH DHvice SN": "hush",
    "Locate Device SN": "locate",
    "Locate Device No": "locate",
}


def classify_operation_log(value: object) -> str | None:
    """Recognize action text only; names and opaque suffixes supply no identity."""
    raw = raw_bytes(value)
    if raw is None or len(raw) > 4096:
        return None
    try:
        text = raw.decode("utf-16-be")
    except UnicodeDecodeError:
        return None
    match = re.fullmatch(
        r"[^\x00-\x1f\x7f]+ (Test Device SN|Silence Device SN|SilHncH DHvice SN|"
        r"Locate Device SN|Locate Device No):[0-9A-F]{8,11}",
        text,
    )
    return _ACTIONS[match[1]] if match is not None else None


def parse_online_event(value: object) -> tuple[str, int] | None:
    """Read verified Online vocabulary; SN remains opaque, never an address."""
    raw = raw_bytes(value)
    if raw is None or len(raw) > 4096:
        return None
    try:
        text = raw.decode("utf-16-be")
    except UnicodeDecodeError:
        return None
    match = re.fullmatch(
        r"([^\x00-\x1f\x7f]+) (Smoke|Heat) Online SN:[0-9A-F]{8}", text
    )
    if match is None:
        return None
    return match[1], {"Smoke": 0x02, "Heat": 0x12}[match[2]]
