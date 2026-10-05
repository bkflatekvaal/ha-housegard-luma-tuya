"""Redacted device state plus separate raw DP38/DP26 captures (may contain names)."""

from copy import deepcopy
from dataclasses import asdict


async def async_get_config_entry_diagnostics(hass, entry):
    gateway = entry.runtime_data
    devices = []
    for device in gateway.registry.devices.values():
        fields = asdict(device)
        fields["name"] = "**REDACTED**"
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
        "gateway_available": gateway.available,
        "inventory_counts": gateway.registry.inventory_counts,
        "subdevices": devices,
        "inventory_refresh": deepcopy(gateway.inventory_refresh),
        "inventory_protocol": gateway.registry.inventory_diagnostics,
        "dp38_capture": gateway.capture.diagnostics(),
        "dp26_capture": gateway.alarm_capture.diagnostics(),
        "operation_log_capture": gateway.operation_capture.diagnostics(),
    }
