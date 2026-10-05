"""Allowlisted protocol diagnostics without identities or raw name-bearing data."""

from copy import deepcopy
from dataclasses import asdict

REDACTED = "**REDACTED**"
PACKET_FIELDS = frozenset(
    {
        "sequence",
        "received_at_utc",
        "tuya_dp_timestamp",
        "origin",
        "code",
        "decoded_byte_length",
        "decoded_length_verified",
        "packet_family",
        "category",
        "truncated",
        "parse_result",
        "discovered_indexes",
        "unverified_status_bytes",
        "smoke_raw",
        "event_classification",
        "device_association",
        "text_encoding",
    }
)
CAPTURE_FIELDS = (
    "listener_attached",
    "capacity",
    "max_raw_bytes",
    "max_base64_characters",
    "total_captured",
    "overwritten_packets",
)
INVENTORY_FIELDS = (
    "variant",
    "packet_length",
    "declared_count",
    "reason",
    "consumed_bytes",
    "trailing_bytes",
    "parsed_count",
)


def _capture_diagnostics(capture):
    """Retain classification and framing, never reversible raw payloads."""
    data = capture.diagnostics()
    return {
        **{key: data[key] for key in CAPTURE_FIELDS},
        "contains_raw_device_names": False,
        "raw_payloads_excluded": True,
        "packets": [
            {key: value for key, value in packet.items() if key in PACKET_FIELDS}
            for packet in data["packets"]
        ],
    }


def _inventory_diagnostics(data):
    """Include known raw connectivity only, excluding opaque header bytes."""
    return {
        **{key: data[key] for key in INVENTORY_FIELDS if key in data},
        "records": [
            {
                key: record[key]
                for key in ("offset", "length", "reason", "online_status_raw")
                if key in record
            }
            for record in data.get("records", [])
        ],
    }


async def async_get_config_entry_diagnostics(hass, entry):
    gateway = entry.runtime_data
    devices = []
    for device in gateway.registry.devices.values():
        fields = asdict(device)
        fields["name"] = REDACTED
        fields["online"] = device.online
        fields["connectivity_source"] = (
            "operation_log"
            if device.online_event_received_at is not None
            else device.inventory_source
        )
        fields["online_status"] = (
            "unknown"
            if device.online is None
            else "online"
            if device.online
            else "offline"
        )
        devices.append(fields)
    return {
        "gateway_manufacturer": "Housegard",
        "gateway_model": "WS2GW-R",
        "gateway_available": gateway.available,
        "inventory_counts": gateway.registry.inventory_counts,
        "subdevices": devices,
        "inventory_refresh": deepcopy(gateway.inventory_refresh),
        "inventory_protocol": _inventory_diagnostics(
            gateway.registry.inventory_diagnostics
        ),
        "dp38_capture": _capture_diagnostics(gateway.capture),
        "dp26_capture": _capture_diagnostics(gateway.alarm_capture),
        "operation_log_capture": _capture_diagnostics(gateway.operation_capture),
    }
