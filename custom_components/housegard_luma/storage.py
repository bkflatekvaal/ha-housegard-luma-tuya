"""Versioned, allowlisted gateway state using Home Assistant Store."""

import logging
from datetime import UTC, datetime

from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .parser import LumaSubdevice

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
SAVE_DELAY = 30
FIELDS = (
    "index",
    "device_type",
    "name",
    "firmware",
    "battery",
    "rssi",
    "tamper",
    "smoke",
    "heat",
    "last_seen",
)


def serialize(registry):
    """Persist parsed values only; never dataclass internals or raw bytes."""
    records = []
    for device in registry.devices.values():
        record = {key: getattr(device, key) for key in FIELDS}
        record["last_seen"] = device.last_seen.isoformat() if device.last_seen else None
        records.append(record)
    return {"gateway_id": registry.gateway_id, "devices": records}


def deserialize(data, gateway_id):
    """Ignore unknown fields and invalid optional values; reject wrong gateways."""
    if data is None:
        return {}
    if (
        not isinstance(data, dict)
        or data.get("gateway_id") != gateway_id
        or not isinstance(data.get("devices"), list)
    ):
        raise ValueError("Invalid registry envelope")
    devices = {}
    for record in data["devices"]:
        if not isinstance(record, dict):
            continue
        index, kind = record.get("index"), record.get("device_type")
        if (
            type(index) is not int
            or not 0 <= index <= 255
            or type(kind) is not int
            or kind not in (2, 0x17, 0x12, 0x0A)
        ):
            continue

        def number(key, maximum, record=record):
            value = record.get(key)
            return value if type(value) is int and 0 <= value <= maximum else None

        def boolean(key, record=record):
            value = record.get(key)
            return value if type(value) is bool else None

        seen = None
        if isinstance(record.get("last_seen"), str):
            try:
                seen = datetime.fromisoformat(record["last_seen"])
                seen = seen.astimezone(UTC) if seen.tzinfo is not None else None
            except (ValueError, OverflowError):
                seen = None
        devices[index] = LumaSubdevice(
            index=index,
            device_type=kind,
            name=record.get("name") if isinstance(record.get("name"), str) else "",
            firmware=record.get("firmware")
            if isinstance(record.get("firmware"), str)
            else None,
            battery=number("battery", 100),
            rssi=number("rssi", 255),
            tamper=boolean("tamper") if kind in (2, 0x17, 0x12) else None,
            smoke=boolean("smoke") if kind in (2, 0x17) else None,
            heat=boolean("heat") if kind == 0x12 else None,
            unknown_13=None,
            last_seen=seen,
            restored=True,
        )
    return devices


class RegistryStorage:
    """One Store per config entry; all access occurs on HA's event loop."""

    def __init__(self, hass, entry_id, registry):
        self.registry = registry
        self.store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.registry", atomic_writes=True
        )
        self.writable = True
        self.dirty = False
        self._last_scheduled = None

    async def async_load(self):
        try:
            data = await self.store.async_load()
        except Exception:  # noqa: BLE001 - persistence must not prevent live operation
            # Includes unsupported future schema. Never overwrite unreadable data.
            self.writable = False
            _LOGGER.warning(
                "Could not load Luma registry; persistence disabled for this load"
            )
            return
        try:
            self.registry.devices.update(deserialize(data, self.registry.gateway_id))
        except ValueError:
            _LOGGER.warning("Ignoring malformed Luma registry data")
        self._last_scheduled = serialize(self.registry)
        _LOGGER.debug("Restored %d Luma subdevices", len(self.registry.devices))

    def schedule_save(self):
        if not self.writable:
            return
        data = serialize(self.registry)
        if data == self._last_scheduled:
            return
        self.dirty = True
        try:
            self.store.async_delay_save(lambda: serialize(self.registry), SAVE_DELAY)
            self._last_scheduled = data
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not schedule Luma registry save")

    async def async_flush(self):
        if not self.writable or not self.dirty:
            return
        try:
            await self.store.async_save(serialize(self.registry))
            self.dirty = False
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not flush Luma registry")
