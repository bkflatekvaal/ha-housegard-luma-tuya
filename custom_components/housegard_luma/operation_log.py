"""Exact controlled RC350 evidence, without inferred addressing or commands."""

import re

from .parser import raw_bytes

# Literal UTF-16BE text, including capital H in the older captures and the
# independently captured 2026-10-05 Test/Hush spellings. Do not repair spellings,
# generalize suffixes, or decode an index.
_SIGNATURES = {
    "FjHrnkontroll SilHncH DHvice SN:0A011A1C".encode("utf-16-be"): "hush",
    "FjHrnkontroll Locate Device No:0A00A011A1A".encode("utf-16-be"): "locate",
    "Fjernkontroll Test Device SN:0A011A16".encode("utf-16-be"): "test",
    "Fjernkontroll Silence Device SN:0A011A1C".encode("utf-16-be"): "hush",
}


def classify_operation_log(value: object) -> str | None:
    """Recognize only entire verified byte strings; this supplies no identity."""
    raw = raw_bytes(value)
    return _SIGNATURES.get(raw) if raw is not None else None


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
