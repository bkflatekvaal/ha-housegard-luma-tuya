"""Bounded passive DP38/DP26 snapshots and optional live handoff; no network operations.

SharingMQ invokes listeners on its callback thread, in unspecified listener
order. Copy each original status item, not CustomerDevice.status. The callback
only filters and appends bounded immutable data; decoding/parsing happens when
HA requests diagnostics. An optional callback hands immutable live DP38
snapshots to the HA loop for registry updates; the SDK thread never mutates state.
"""

from __future__ import annotations

import base64
import re
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from .const import INVENTORY_CODES, INVENTORY_DP_CODES
from .parser import decode_alarm_msg, inspect_inventory, parse_sub_admin, raw_bytes

MAX_PACKETS = 128
MAX_BYTES = 4096
MAX_BASE64_CHARS = 4 * ((MAX_BYTES + 2) // 3)


@dataclass(frozen=True, slots=True)
class PacketSnapshot:
    sequence: int
    received_at: str
    dp_timestamp: int | None
    origin: str
    value: str | bytes | None
    source_length: int | None
    encoded: bool
    padding: int
    truncated: bool
    code: str = "sub_admin"


class DP38Capture:
    """One gateway's bounded history; duplicate packets are intentional."""

    dp_id = 38
    dp_code = "sub_admin"
    codes = INVENTORY_CODES

    def __init__(self, gateway_id: str, on_live_packet=None) -> None:
        self.gateway_id = gateway_id
        self._on_live_packet = on_live_packet
        self.dp_codes = {**INVENTORY_DP_CODES, 26: "alarm_msg"}
        self._packets: deque[PacketSnapshot] = deque(maxlen=MAX_PACKETS)
        self._sequence = 0
        self._mq = None
        self._closed = False

    def attach(self, mq) -> None:
        """Observe an existing SDK connection without changing subscriptions."""
        if self._closed or mq is self._mq:
            return
        if self._mq is not None:
            self._mq.remove_message_listener(self.receive)
        self._mq = mq
        if mq is not None:
            mq.add_message_listener(self.receive)

    def close(self) -> None:
        """Detach on entry unload; late callbacks cannot append anything."""
        self._closed = True
        if self._mq is not None:
            self._mq.remove_message_listener(self.receive)
        self._mq = None

    def receive(self, message: object) -> None:
        """SDK-thread callback: retain only this gateway and selected DP."""
        if self._closed or not isinstance(message, dict):
            return
        if message.get("protocol") != 4:
            return
        data = message.get("data")
        if not isinstance(data, dict) or data.get("devId") != self.gateway_id:
            return
        status = data.get("status")
        if not isinstance(status, list):
            return
        for item in status:
            if not isinstance(item, dict) or "value" not in item:
                continue
            code = self._resolve_code(item)
            if code is None:
                continue
            timestamp = item.get("t")
            if type(timestamp) is not int:
                timestamp = item.get(
                    "eventTime",
                    item.get(
                        "event_time", data.get("eventTime", data.get("event_time"))
                    ),
                )
            self.record(item["value"], "live_report", timestamp, code=code)

    def _resolve_code(self, item):
        """Use verified raw IDs, explicit codes and supplemental SDK metadata."""
        code, dp_id = item.get("code"), item.get("dpId")
        if isinstance(dp_id, str) and dp_id.isdecimal():
            dp_id = int(dp_id)
        mapped = self.dp_codes.get(dp_id) if type(dp_id) is int else None
        if code is not None:
            if code in self.codes and (mapped is None or mapped == code):
                return code
            return None
        return mapped if mapped in self.codes else None

    def record(
        self, value: object, origin: str, timestamp: object = None, *, code=None
    ) -> None:
        """Copy only a bounded raw scalar, never retain the incoming message."""
        if self._closed:
            return
        source_length = None
        encoded = isinstance(value, str)
        padding = 0
        truncated = False
        if encoded:
            source_length = len(value)
            padding = 2 if value.endswith("==") else int(value.endswith("="))
            truncated = source_length > MAX_BASE64_CHARS
            value = value[:MAX_BASE64_CHARS]
        elif isinstance(value, (bytes, bytearray)):
            source_length = len(value)
            truncated = source_length > MAX_BYTES
            value = bytes(value[:MAX_BYTES])
        elif isinstance(value, list):
            source_length = len(value)
            truncated = source_length > MAX_BYTES
            prefix = value[:MAX_BYTES]
            value = raw_bytes(prefix)
        else:
            # Do not stringify arbitrary objects: they could contain secrets.
            value = None
        self._sequence += 1
        packet = PacketSnapshot(
            sequence=self._sequence,
            received_at=datetime.now(UTC).isoformat(),
            dp_timestamp=timestamp if type(timestamp) is int else None,
            origin=origin,
            value=value,
            source_length=source_length,
            encoded=encoded,
            padding=padding,
            truncated=truncated,
            code=code or self.dp_code,
        )
        self._packets.append(packet)
        if origin == "live_report" and not truncated and self._on_live_packet:
            self._on_live_packet(packet)

    def diagnostics(self) -> dict:
        """Decode immutable snapshots on HA's thread, not the MQ thread."""
        snapshots = self._packets.copy()
        packets = [self._describe(packet) for packet in snapshots]
        latest = snapshots[-1].sequence if snapshots else 0
        return {
            "contains_raw_device_names": True,
            "listener_attached": self._mq is not None and not self._closed,
            "capacity": MAX_PACKETS,
            "max_raw_bytes": MAX_BYTES,
            "max_base64_characters": MAX_BASE64_CHARS,
            "total_captured": latest,
            "overwritten_packets": max(0, latest - len(snapshots)),
            "packets": packets,
        }

    def _describe(self, packet: PacketSnapshot) -> dict:
        raw = raw_bytes(packet.value)
        prefix = raw[:MAX_BYTES] if raw is not None else b""
        truncated = packet.truncated or (raw is not None and len(raw) > MAX_BYTES)
        length = len(raw) if raw is not None else None
        length_verified = not packet.truncated and raw is not None
        if packet.truncated:
            # The discarded suffix cannot be validated. For standard Base64,
            # its encoded size/padding still determines the declared byte size.
            # Report that calculation explicitly as unverified, never parse a
            # truncated prefix as if it were a complete protocol packet.
            if packet.encoded:
                length = (
                    packet.source_length // 4 * 3 - packet.padding
                    if packet.source_length % 4 == 0 and raw is not None
                    else None
                )
            else:
                length = packet.source_length
                length_verified = packet.value is not None
        indexes = []
        unverified_status_bytes = []
        if raw is None:
            result = "invalid_raw"
        elif truncated:
            result = "not_parsed_truncated"
        elif raw == b"\x00":
            result = "empty_inventory_slot"
        elif raw[:2] == b"\x03\x07":
            device = parse_sub_admin(raw)
            result = "individual" if device is not None else "malformed_individual"
            if device is not None:
                indexes = [device.index]
                unverified_status_bytes = [
                    {"index": device.index, "individual_raw_15": raw[15]}
                ]
        elif raw[:2] == b"\x02\x07":
            devices, info = inspect_inventory(raw)
            indexes = [device.index for device in devices]
            if not devices:
                result = "unsupported_or_malformed_inventory"
            elif (
                len(devices) != info.get("declared_count")
                or info.get("trailing_bytes")
                or info.get("reason")
            ):
                result = "partial_inventory"
            else:
                result = "inventory"
                # Complete, strictly parsed packet only. Preserve opaque values;
                # neither 0 nor 1 is assigned connectivity semantics here.
                unverified_status_bytes = [
                    {
                        "index": device.index,
                        "inventory_body_13": bytes.fromhex(detail["header_hex"])[13],
                    }
                    for device, detail in zip(devices, info["records"])
                ]
        else:
            result = "unsupported_family"
        return {
            "sequence": packet.sequence,
            "received_at_utc": packet.received_at,
            "tuya_dp_timestamp": packet.dp_timestamp,
            "gateway_id": self.gateway_id,
            "origin": packet.origin,
            "code": packet.code,
            "decoded_byte_length": length,
            "decoded_length_verified": length_verified,
            "packet_family": prefix[0] if prefix else None,
            "category": prefix[1] if len(prefix) > 1 else None,
            "base64": (
                packet.value
                if packet.encoded
                else base64.b64encode(prefix).decode("ascii")
                if raw is not None
                else None
            ),
            "hex": prefix.hex() if raw is not None else None,
            "truncated": truncated,
            "parse_result": result,
            "discovered_indexes": indexes,
            "unverified_status_bytes": unverified_status_bytes,
            "smoke_raw": (
                raw[6] if result == "individual" and raw[3] == 0x02 else None
            ),
        }


class DP26Capture(DP38Capture):
    """Passive alarm text evidence, never an input to subdevice state."""

    dp_id = 26
    dp_code = "alarm_msg"
    codes = ("alarm_msg",)

    def _describe(self, packet: PacketSnapshot) -> dict:
        result = super()._describe(packet)
        for key in (
            "packet_family",
            "category",
            "discovered_indexes",
            "smoke_raw",
            "unverified_status_bytes",
        ):
            result.pop(key)
        text = None
        if not result["truncated"]:
            text = decode_alarm_msg(packet.value)
        classification = None
        if text is not None:
            match = re.fullmatch(
                r".+ (Smoke Triggered|Alarm Restored|Tamper Event|Tamper Recovery)"
                r" SN:[0-9A-Fa-f]+",
                text,
            )
            if match:
                classification = {
                    "Smoke Triggered": "smoke_triggered",
                    "Alarm Restored": "alarm_restored",
                    "Tamper Event": "tamper_event",
                    "Tamper Recovery": "tamper_recovery",
                }[match[1]]
        result.update(
            decoded_text=text,
            text_encoding="utf-16-be" if text is not None else None,
            event_classification=classification,
            parse_result=(
                "not_parsed_truncated"
                if result["truncated"]
                else "alarm_text"
                if text is not None
                else "invalid_alarm_text"
            ),
        )
        return result


class OperationLogCapture(DP38Capture):
    """Diagnostic evidence only until remote identity is independently verified."""

    dp_code = "operation_log"
    codes = ("operation_log",)

    def _describe(self, packet: PacketSnapshot) -> dict:
        from .operation_log import classify_operation_log

        result = super()._describe(packet)
        for key in (
            "packet_family",
            "category",
            "discovered_indexes",
            "smoke_raw",
            "unverified_status_bytes",
        ):
            result.pop(key)
        text = None
        action = None
        if not result["truncated"]:
            raw = raw_bytes(packet.value)
            if raw is not None and raw:
                try:
                    text = raw.decode("utf-16-be")
                except UnicodeDecodeError:
                    pass
            action = classify_operation_log(packet.value)
        result.update(
            decoded_text=text,
            text_encoding="utf-16-be" if text is not None else None,
            event_classification=action,
            device_association=None,
            parse_result=(
                "not_parsed_truncated"
                if result["truncated"]
                else "verified_rc350_signature"
                if action is not None
                else "unknown_operation_log"
            ),
        )
        return result
