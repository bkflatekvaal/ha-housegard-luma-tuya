"""Bridge the existing Tuya dispatcher to gateway-local entity state."""

import base64
import logging
from datetime import UTC, datetime
from time import monotonic

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .capture import DP26Capture, DP38Capture, OperationLogCapture
from .const import (
    CONF_TUYA_ENTRY_ID,
    DOMAIN,
    DP_SUB_ADMIN,
    INVENTORY_CODES,
    INVENTORY_COOLDOWN,
    INVENTORY_DP_CODES,
    INVENTORY_QUERY,
    INVENTORY_TIMEOUT,
    NETWORK_TEST_COMMAND,
    SOUND_TEST_COMMAND,
)
from .parser import inspect_inventory, raw_bytes
from .registry import SubdeviceRegistry
from .storage import RegistryStorage

_LOGGER = logging.getLogger(__name__)
MODELS = {
    0x02: "Luma Smoke Alarm",
    0x12: "Luma Heat Alarm",
    0x0A: "Luma RC350",
}


class LumaGateway:
    def __init__(self, hass, entry, manager, gateway_id):
        self.hass = hass
        self.entry = entry
        self.manager = manager
        self.gateway_id = gateway_id
        self.registry = SubdeviceRegistry(gateway_id)
        self.storage = RegistryStorage(hass, entry.entry_id, self.registry)
        self._closed = False
        self.capture = DP38Capture(gateway_id, self._queue_live_packet)
        self.alarm_capture = DP26Capture(gateway_id)
        self.operation_capture = OperationLogCapture(
            gateway_id, self._queue_operation_packet
        )
        self._startup_pending = True
        self._request_in_flight = False
        self._next_request = 0.0
        self._inventory_started = None
        self._inventory_cancel = None
        self.inventory_refresh = {"state": "idle"}
        self._inventory_slots = {}
        self.signal = f"{DOMAIN}_{entry.entry_id}_updated"

    @callback
    def sync_capture_connection(self, now=None):
        """Follow SDK connection replacement without creating a connection."""
        device = self.manager.device_map.get(self.gateway_id)
        mapping = {**INVENTORY_DP_CODES, 26: "alarm_msg"}
        for dp_id, info in (getattr(device, "local_strategy", None) or {}).items():
            if isinstance(info, dict) and info.get("status_code") in (
                *INVENTORY_CODES,
                "operation_log",
            ):
                if isinstance(dp_id, str) and dp_id.isdecimal():
                    dp_id = int(dp_id)
                if type(dp_id) is int and dp_id not in mapping:
                    mapping[dp_id] = info["status_code"]
        self.operation_capture.dp_codes = mapping
        self.operation_capture.attach(getattr(self.manager, "mq", None))
        self.capture.dp_codes = mapping
        self.capture.attach(getattr(self.manager, "mq", None))
        self.alarm_capture.attach(getattr(self.manager, "mq", None))

    @property
    def available(self):
        device = self.manager.device_map.get(self.gateway_id)
        return device is not None and bool(getattr(device, "online", True))

    @callback
    def handle_update(self, updated_status_properties=None, dp_timestamps=None):
        if self._closed:
            return
        startup = self._startup_pending
        self._startup_pending = False
        gateway = self.manager.device_map.get(self.gateway_id)
        if gateway is not None:
            status = getattr(gateway, "status", None) or {}
            for code in INVENTORY_CODES:
                if not startup and (
                    updated_status_properties is None
                    or code not in updated_status_properties
                ):
                    continue
                value = status.get(code)
                if startup and value is not None:
                    self.capture.record(value, "cached_startup", code=code)
                raw = raw_bytes(value)
                # Individual semantics are verified only on the original slot.
                if code != DP_SUB_ADMIN and (raw is None or raw[:2] != b"\x02\x07"):
                    continue
                self._publish_devices(self.registry.update_many(value, cached=True))
        self.sync_capture_connection()
        async_dispatcher_send(self.hass, self.signal)

    def _queue_operation_packet(self, packet):
        self.hass.add_job(self._handle_operation_packet, packet)

    @callback
    def _handle_operation_packet(self, packet):
        if self._closed or packet.origin != "live_report" or packet.truncated:
            return
        if self.registry.apply_online_event(
            packet.value, datetime.fromisoformat(packet.received_at)
        ):
            async_dispatcher_send(self.hass, self.signal)

    def _queue_live_packet(self, packet):
        """Transfer the immutable original snapshot from the SDK thread."""
        self.hass.add_job(self._handle_live_packet, packet)

    @callback
    def _handle_live_packet(self, packet):
        if self._closed:
            return
        raw = raw_bytes(packet.value)
        code = getattr(packet, "code", DP_SUB_ADMIN)
        self._record_inventory_response(code, raw, packet.received_at)
        if raw == b"\x00":
            return
        if code != DP_SUB_ADMIN and (raw is None or raw[:2] != b"\x02\x07"):
            return
        devices = self.registry.update_many(
            packet.value, received_at=datetime.fromisoformat(packet.received_at)
        )
        self._publish_devices(devices)
        if devices:
            async_dispatcher_send(self.hass, self.signal)

    @callback
    def _publish_devices(self, devices, *, save=True):
        for device in devices:
            registry = dr.async_get(self.hass)
            parent = ("tuya", self.gateway_id)
            kwargs = {}
            parent_device = registry.async_get_device_by_identifier(
                parent, self.entry.data[CONF_TUYA_ENTRY_ID]
            )
            if parent_device is not None:
                kwargs["via_device_id"] = parent_device.id
            registry.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, self.registry.identifier(device.index))},
                manufacturer="Housegard",
                name=device.name or f"Luma {device.index}",
                model=MODELS.get(device.device_type, "Luma subdevice"),
                sw_version=device.firmware,
                **kwargs,
            )
        if devices and save:
            self.storage.schedule_save()

    async def async_restore(self):
        await self.storage.async_load()
        self._publish_devices(list(self.registry.devices.values()), save=False)

    async def async_close(self):
        self._closed = True
        if self._inventory_cancel is not None:
            self._inventory_cancel()
            self._inventory_cancel = None
        self.capture.close()
        self.alarm_capture.close()
        self.operation_capture.close()
        await self.storage.async_flush()

    def can_locate(self, index):
        """Require an existing alarm identity and its unmodified one-byte index."""
        if type(index) is not int or not 0 <= index <= 0xFF:
            return False
        device = self.registry.devices.get(index)
        return (
            not self._closed
            and self.available
            and device is not None
            and type(device.index) is int
            and device.index == index
            and device.device_type in (0x02, 0x12)
            and getattr(self.manager, "mq", None) is not None
            and callable(getattr(self.manager, "send_commands", None))
        )

    async def async_locate(self, index):
        """Send one explicit Locate via the existing Tuya manager; no state writes."""
        if not self.can_locate(index):
            raise HomeAssistantError("Locate is unavailable for this alarm")
        value = base64.b64encode(bytes((0x07, 0x07, index, 0x04))).decode("ascii")
        try:
            result = await self.hass.async_add_executor_job(
                self.manager.send_commands,
                self.gateway_id,
                [{"code": DP_SUB_ADMIN, "value": value}],
            )
        except Exception:  # noqa: BLE001 - redact transport details/credentials
            raise HomeAssistantError("Could not send Locate command") from None
        if result is False or (
            isinstance(result, dict) and result.get("success") is False
        ):
            raise HomeAssistantError("Locate command was rejected")

    def can_network_test(self):
        """Check transport availability, not subdevice RF reachability."""
        return (
            not self._closed
            and self.available
            and getattr(self.manager, "mq", None) is not None
            and callable(getattr(self.manager, "send_commands", None))
        )

    async def async_network_test(self):
        """Replay the verified app start only on explicit press; no session claims."""
        if not self.can_network_test():
            raise HomeAssistantError("Network Test is unavailable")
        try:
            result = await self.hass.async_add_executor_job(
                self.manager.send_commands,
                self.gateway_id,
                [{"code": DP_SUB_ADMIN, "value": NETWORK_TEST_COMMAND}],
            )
        except Exception:  # noqa: BLE001 - redact transport details/credentials
            raise HomeAssistantError("Could not send Network Test command") from None
        if result is False or (
            isinstance(result, dict) and result.get("success") is False
        ):
            raise HomeAssistantError("Network Test command was rejected")

    def can_sound_test(self):
        """Check transport availability, not subdevice RF reachability."""
        return (
            not self._closed
            and self.available
            and getattr(self.manager, "mq", None) is not None
            and callable(getattr(self.manager, "send_commands", None))
        )

    async def async_sound_test(self):
        """Replay the verified app start only on explicit press; no session claims."""
        if not self.can_sound_test():
            raise HomeAssistantError("Sound Test is unavailable")
        try:
            result = await self.hass.async_add_executor_job(
                self.manager.send_commands,
                self.gateway_id,
                [{"code": DP_SUB_ADMIN, "value": SOUND_TEST_COMMAND}],
            )
        except Exception:  # noqa: BLE001 - redact transport details/credentials
            raise HomeAssistantError("Could not send Sound Test command") from None
        if result is False or (
            isinstance(result, dict) and result.get("success") is False
        ):
            raise HomeAssistantError("Sound Test command was rejected")

    async def async_request_inventory(self):
        """Request paired-device inventory, never fresh detector telemetry."""
        if (
            self._closed
            or self._request_in_flight
            or self.inventory_refresh.get("state") == "waiting"
            or monotonic() < self._next_request
        ):
            return False
        self.sync_capture_connection()
        if getattr(self.manager, "mq", None) is None:
            self.inventory_refresh = {"state": "unavailable"}
            _LOGGER.debug("Inventory request skipped: existing Tuya MQ is unavailable")
            return False
        self._request_in_flight = True
        self._inventory_started = monotonic()
        self._next_request = self._inventory_started + INVENTORY_COOLDOWN
        self._inventory_slots = {}
        self.inventory_refresh = {
            "state": "waiting",
            "last_inventory_request": datetime.now(UTC).isoformat(),
            "last_inventory_response": None,
            "response_slots_received": [],
            "non_empty_slots": 0,
            "empty_slots": 0,
            "records_received": 0,
            "refresh_duration": None,
            "timed_out": False,
        }
        self._inventory_cancel = async_call_later(
            self.hass, INVENTORY_TIMEOUT, self._inventory_timeout
        )
        try:
            # Same executor/manager path as HA TuyaEntity._async_send_commands.
            # The SDK forwards JSON values unchanged: RAW is already Base64 here.
            result = await self.hass.async_add_executor_job(
                self.manager.send_commands,
                self.gateway_id,
                [{"code": DP_SUB_ADMIN, "value": INVENTORY_QUERY}],
            )
            if result is False or (
                isinstance(result, dict) and result.get("success") is False
            ):
                self._finish_inventory("send_failed")
                _LOGGER.warning("Luma inventory command was rejected")
                return False
        except Exception:  # noqa: BLE001 - keep restored entities usable
            self._finish_inventory("send_failed")
            _LOGGER.warning("Could not send Luma inventory query")
            return False
        finally:
            self._request_in_flight = False
        return True

    @callback
    def _record_inventory_response(self, code, raw, received_at):
        if (
            self.inventory_refresh.get("state") != "waiting"
            or code not in INVENTORY_CODES
        ):
            return
        # Cached data and malformed/unsupported chunks never complete a session.
        if raw == b"\x00":
            count = 0
        elif raw is not None and raw[:2] == b"\x02\x07":
            devices, info = inspect_inventory(raw)
            if (
                info.get("variant") != "length_framed_missing_name_zero"
                or info.get("reason")
                or info.get("trailing_bytes")
                or len(devices) != info.get("declared_count")
            ):
                return
            count = len(devices)
        else:
            return
        if received_at < self.inventory_refresh["last_inventory_request"]:
            return
        self._inventory_slots[code] = count
        self.inventory_refresh.update(
            last_inventory_response=received_at,
            response_slots_received=[
                code for code in INVENTORY_CODES if code in self._inventory_slots
            ],
            non_empty_slots=sum(count > 0 for count in self._inventory_slots.values()),
            empty_slots=sum(count == 0 for count in self._inventory_slots.values()),
            records_received=sum(self._inventory_slots.values()),
        )
        if len(self._inventory_slots) == len(INVENTORY_CODES):
            self._finish_inventory("complete")

    @callback
    def _inventory_timeout(self, now):
        if not self._closed and self.inventory_refresh.get("state") == "waiting":
            self._finish_inventory("timed_out")

    @callback
    def _finish_inventory(self, state):
        if self._inventory_cancel is not None:
            self._inventory_cancel()
            self._inventory_cancel = None
        self.inventory_refresh.update(
            state=state,
            timed_out=state == "timed_out",
            refresh_duration=round(monotonic() - self._inventory_started, 3),
        )
