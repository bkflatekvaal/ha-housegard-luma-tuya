"""Housegard Luma using Home Assistant's existing Tuya push connection."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_GATEWAY_ID, CONF_TUYA_ENTRY_ID
from .coordinator import LumaGateway

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    tuya_entry = hass.config_entries.async_get_entry(entry.data[CONF_TUYA_ENTRY_ID])
    runtime = getattr(tuya_entry, "runtime_data", None)
    manager = getattr(runtime, "manager", None)
    gateway_id = entry.data[CONF_GATEWAY_ID]
    if manager is None or gateway_id not in manager.device_map:
        raise ConfigEntryNotReady("Selected Tuya gateway is not available yet")

    gateway = entry.runtime_data = LumaGateway(hass, entry, manager, gateway_id)
    # HA also runs unload callbacks when setup fails or is cancelled.
    entry.async_on_unload(gateway.async_close)
    await gateway.async_restore()
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"tuya_entry_update_{gateway_id}", gateway.handle_update
        )
    )
    entry.async_on_unload(gateway.capture.close)
    entry.async_on_unload(gateway.alarm_capture.close)
    entry.async_on_unload(gateway.operation_capture.close)
    # Normal SDK reconnects reuse the MQ object. Also follow explicit object
    # replacement without ever invoking refresh_mq or modifying subscriptions.
    entry.async_on_unload(
        async_track_time_interval(
            hass, gateway.sync_capture_connection, timedelta(seconds=30)
        )
    )
    gateway.handle_update()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await gateway.async_request_inventory()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_close()
    return True
