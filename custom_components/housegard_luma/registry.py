"""Gateway-local protocol state, independent of Home Assistant."""

from dataclasses import replace
from datetime import datetime

from .operation_log import parse_online_event
from .parser import LumaSubdevice, inspect_inventory, parse_sub_admin, raw_bytes


class SubdeviceRegistry:
    """Retain every discovered device across partial inventory updates."""

    def __init__(self, gateway_id: str) -> None:
        self.gateway_id = gateway_id
        self.devices: dict[int, LumaSubdevice] = {}
        self.inventory_diagnostics: dict = {}

    def update(self, value: object) -> LumaSubdevice | None:
        """Compatibility entry point for callers expecting a single report."""
        devices = self.update_many(value)
        return devices[0] if devices else None

    def update_many(
        self,
        value: object,
        *,
        received_at: datetime | None = None,
        cached: bool = False,
    ) -> list[LumaSubdevice]:
        raw = raw_bytes(value)
        if raw is not None and raw[:2] == b"\x02\x07":
            incoming, self.inventory_diagnostics = inspect_inventory(raw)
            merged = []
            for device in incoming:
                previous = self.devices.get(device.index)
                device.inventory_source = "cached" if cached else "fresh"
                device.inventory_received_at = None if cached else received_at
                connectivity = {
                    key: getattr(device, key)
                    for key in (
                        "online_status_raw",
                        "inventory_source",
                        "inventory_received_at",
                        "online_event_received_at",
                    )
                }
                if (
                    cached
                    and previous is not None
                    and previous.inventory_source == "fresh"
                ):
                    connectivity = {key: getattr(previous, key) for key in connectivity}
                if cached and previous is not None:
                    connectivity["online_event_received_at"] = (
                        previous.online_event_received_at
                    )
                if previous is not None:
                    # Inventory updates telemetry/connectivity, never alarm state or Last seen.
                    device = replace(
                        previous,
                        **connectivity,
                        device_type=device.device_type,
                        name=device.name,
                        firmware=device.firmware,
                        battery=device.battery
                        if device.battery is not None
                        else previous.battery,
                        rssi=device.rssi if device.rssi is not None else previous.rssi,
                    )
                self.devices[device.index] = device
                merged.append(device)
            return merged
        device = parse_sub_admin(value)
        if device is not None:
            previous = self.devices.get(device.index)
            if previous is not None and cached:
                # Cache has no freshness guarantee. Preserve known telemetry.
                device = replace(
                    previous,
                    device_type=device.device_type,
                    name=device.name,
                    firmware=device.firmware,
                )
            else:
                if previous is not None:
                    device.online_status_raw = previous.online_status_raw
                    device.inventory_source = previous.inventory_source
                    device.inventory_received_at = previous.inventory_received_at
                    device.online_event_received_at = previous.online_event_received_at
                device.last_seen = received_at
                # A restored alarm needs an explicit verified clear report.
                if (
                    previous is not None
                    and previous.restored
                    and previous.smoke is True
                    and device.smoke is not False
                ):
                    device.smoke = True
                    device.restored = True
                if (
                    previous is not None
                    and previous.restored
                    and previous.heat is True
                    and device.heat is not False
                ):
                    device.heat = True
                    device.restored = True
            self.devices[device.index] = device
            return [device]
        return []

    def identifier(self, index: int) -> str:
        return f"{self.gateway_id}_{index}"

    @property
    def inventory_counts(self):
        """Retained inventory records only; no inference from individual reports."""
        devices = [d for d in self.devices.values() if d.inventory_source != "none"]
        if not devices:
            return None
        online = sum(d.online is True for d in devices)
        offline = len(devices) - online
        return {
            "devices": len(devices),
            "online_devices": online,
            "offline_devices": offline,
        }

    def apply_online_event(self, value, received_at):
        """Resolve an exact, unique registered name/type inside this gateway."""
        event = parse_online_event(value)
        if event is None:
            return False
        name, kind = event
        matches = [d for d in self.devices.values() if d.name == name]
        if len(matches) != 1 or matches[0].device_type != kind:
            return False
        matches[0].online_event_received_at = received_at
        return True
