"""Decode verified Luma packet fields without Home Assistant dependencies."""

from __future__ import annotations

import base64
import binascii
import logging
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LumaSubdevice:
    index: int
    device_type: int
    tamper: bool | None
    battery: int | None
    unknown_13: int | None
    rssi: int | None
    firmware: str | None
    name: str
    smoke: bool | None = None
    last_seen: datetime | None = None
    restored: bool = False
    online_status_raw: int | None = None
    inventory_source: str = "none"
    inventory_received_at: datetime | None = None

    online_event_received_at: datetime | None = None
    heat: bool | None = None

    @property
    def online(self) -> bool | None:
        if self.online_event_received_at is not None:
            return True
        if self.inventory_source != "fresh":
            return None
        return {0: False, 1: True}.get(self.online_status_raw)


def raw_bytes(value: object) -> bytes | None:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            return None
    if isinstance(value, list) and all(type(v) is int and 0 <= v <= 255 for v in value):
        return bytes(value)
    return None


def parse_sub_admin(value: object) -> LumaSubdevice | None:
    raw = raw_bytes(value)
    if raw is None:
        return None
    if raw[:2] == b"\x03\x07":
        return _parse_individual_report(raw)
    # Use parse_inventory for multi-record 02 07 packets; short 01 is unsupported.
    return None


def _parse_individual_report(raw: bytes) -> LumaSubdevice | None:
    if len(raw) < 19:
        return None
    device_type = raw[3]
    # LINKD 0x17 provisionally shares the 0x02 layout; hardware confirmation pending.
    is_detector = device_type in (0x02, 0x17, 0x12)
    status = raw[8:10]
    tamper = {bytes((0, 0)): False, bytes((1, 0)): True}.get(status)
    name_len = int.from_bytes(raw[17:19], "little")
    end = 19 + name_len
    if name_len % 2:
        return None
    name_data = raw[19:]
    if end - len(raw) == 1 and len(name_data) % 2:
        # Live Tuya reports can omit the final UTF-16LE zero byte.
        # Recover only this one-byte shortfall, then decode strictly below.
        name_data += b"\x00"
    elif end != len(raw):
        return None
    try:
        name = name_data.decode("utf-16-le")
    except UnicodeDecodeError:
        return None

    # Real smoke Triggered -> Restored capture, 2026-09-27. Unknown is
    # deliberately not clear or a retained stale alarm state.
    if device_type in (0x02, 0x17) and raw[6] not in (0, 1):
        _LOGGER.debug("Unknown smoke state byte[6]=0x%02x at index %d", raw[6], raw[2])
    # Controlled Heat Test (2026-09-29): 00; thermal trigger (2026-10-05): 01.
    # This is full-packet offset 6, not an inventory body offset.
    if device_type == 0x12 and raw[6] not in (0, 1):
        _LOGGER.debug("Unknown heat state byte[6]=0x%02x at index %d", raw[6], raw[2])
    fw = raw[16]
    return LumaSubdevice(
        smoke={0: False, 1: True}.get(raw[6]) if device_type in (0x02, 0x17) else None,
        heat={0: False, 1: True}.get(raw[6]) if device_type == 0x12 else None,
        index=raw[2],
        device_type=device_type,
        tamper=tamper if is_detector else None,
        battery=raw[10] if is_detector and raw[10] <= 100 else None,
        unknown_13=raw[13],
        rssi=raw[14] if is_detector else None,
        firmware=f"{fw >> 4}.{fw & 0x0F}",
        name=name,
    )


def decode_alarm_msg(value: object) -> str | None:
    # Captured DP26 bytes are big-endian, unlike DP38 names.
    raw = raw_bytes(value)
    if raw is None:
        return None
    try:
        return raw.decode("utf-16-be")
    except UnicodeDecodeError:
        return None


def parse_inventory(value: object) -> list[LumaSubdevice]:
    """Decode the observed length-framed inventory variant only."""
    return inspect_inventory(value)[0]


def inspect_inventory(value: object) -> tuple[list[LumaSubdevice], dict]:
    """Return records and bounded, name-free framing diagnostics.

    Observed 02 07 variant (one five-record capture): byte 2 is consistent
    with a record count, followed by [body_length:u8, body] records. Length
    excludes its own byte. Body offsets: 0 index, 1 type, 14 firmware nibbles,
    15:17 declared UTF-16LE name length, 17: name. All five bodies contain
    declared_length - 1 name bytes (missing final zero), and body_length is
    16 + declared_length. Index/type/name have strong cross-report evidence;
    firmware alignment is consistent with 03 07 (2.1 remote, 2.7 detectors).
    Count/length semantics remain provisional beyond this captured variant.

    Cross-checks establish body[8] as battery percentage and body[12] as
    raw RSSI for the common record, including remotes. Battery above 100 and
    inventory RSSI 0xFF are conservatively unknown. Other bytes in offsets
    2:14 other than 8, 12 and 13 remain opaque. Body[13] is the
    controlled inventory Online field: 00 offline, 01 online; others unknown. Inventory does not establish a fresh individual report.
    The second supplied capture starts 02 07 08 00 and does not fit this
    framing. Never scan arbitrary bytes for guessed record boundaries or
    reassemble packets: chunk sequencing and pagination are unverified.
    """
    raw = raw_bytes(value)
    records = []
    info = {"variant": "unsupported", "records": []}
    if raw is None or raw[:2] != b"\x02\x07":
        return records, info
    info["packet_length"] = len(raw)
    if len(raw) < 3:
        info["reason"] = "missing_count"
        return records, info
    info["declared_count"] = raw[2]
    offset = 3
    for _ in range(raw[2]):
        if offset >= len(raw):
            info["reason"] = "missing_record"
            break
        length = raw[offset]
        detail = {"offset": offset, "length": length}
        info["records"].append(detail)
        end = offset + 1 + length
        if length < 17 or end > len(raw):
            detail["reason"] = "invalid_or_truncated_frame"
            break
        body = raw[offset + 1 : end]
        # Exclude names, tokens and gateway identity from diagnostics.
        detail["header_hex"] = body[:17].hex()
        offset = end
        name_length = int.from_bytes(body[15:17], "little")
        if name_length < 2 or name_length % 2 or length != 16 + name_length:
            detail["reason"] = "unsupported_name_framing"
            continue
        try:
            name = (body[17:] + b"\x00").decode("utf-16-le")
        except UnicodeDecodeError:
            detail["reason"] = "invalid_utf16"
            continue
        if body[1] not in (0x02, 0x17, 0x12, 0x0A):
            detail["reason"] = "unknown_type"
            continue
        records.append(
            LumaSubdevice(
                index=body[0],
                device_type=body[1],
                name=name,
                firmware=f"{body[14] >> 4}.{body[14] & 0x0F}",
                tamper=None,
                battery=body[8] if body[8] <= 100 else None,
                rssi=body[12] if body[12] != 0xFF else None,
                unknown_13=None,
                online_status_raw=body[13],
            )
        )
        detail["online_status_raw"] = body[13]
        detail["reason"] = "decoded"
    info["consumed_bytes"] = offset
    info["trailing_bytes"] = len(raw) - offset
    info["parsed_count"] = len(records)
    if records:
        info["variant"] = "length_framed_missing_name_zero"
    return records, info
