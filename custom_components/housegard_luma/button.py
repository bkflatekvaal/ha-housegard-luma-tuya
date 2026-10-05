"""Explicit gateway actions and per-alarm Locate buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .entity import LumaEntity, async_setup_subdevices


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            LumaRefreshButton(entry.runtime_data),
            LumaNetworkTestButton(entry.runtime_data),
            LumaSoundTestButton(entry.runtime_data),
        ]
    )
    async_setup_subdevices(
        hass,
        entry,
        async_add_entities,
        lambda gateway, index: [LumaLocateButton(gateway, index)],
    )


class LumaRefreshButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "refresh_devices"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, gateway):
        self.gateway = gateway
        self._attr_unique_id = f"{gateway.gateway_id}_refresh_devices"
        self._attr_device_info = DeviceInfo(
            identifiers={("tuya", gateway.gateway_id)},
            manufacturer="Housegard",
            model="WS2GW-R",
        )

    @property
    def available(self):
        return self.gateway.can_network_test()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.gateway.signal, self.async_write_ha_state
            )
        )

    async def async_press(self):
        if not self.available:
            raise HomeAssistantError("Refresh devices is unavailable")
        sent = await self.gateway.async_request_inventory()
        if not sent and self.gateway.inventory_refresh.get("state") in (
            "send_failed",
            "unavailable",
        ):
            raise HomeAssistantError("Could not send Refresh devices command")


class LumaLocateButton(LumaEntity, ButtonEntity):
    _attr_translation_key = "locate"
    _attr_icon = "mdi:bullhorn"

    def __init__(self, gateway, index):
        super().__init__(gateway, index, "locate")

    @property
    def available(self):
        return self.gateway.can_locate(self.index)

    async def async_press(self):
        await self.gateway.async_locate(self.index)


class LumaNetworkTestButton(LumaRefreshButton):
    """Explicit gateway RF test; completion and per-device status are unverified."""

    _attr_translation_key = "network_test"
    _attr_icon = "mdi:access-point-network"

    def __init__(self, gateway):
        super().__init__(gateway)
        self._attr_unique_id = f"{gateway.gateway_id}_network_test"

    @property
    def available(self):
        return self.gateway.can_network_test()

    async def async_press(self):
        await self.gateway.async_network_test()


class LumaSoundTestButton(LumaRefreshButton):
    """Potentially noisy gateway action; only an explicit press sends it."""

    _attr_translation_key = "sound_test"
    _attr_icon = "mdi:volume-high"

    def __init__(self, gateway):
        super().__init__(gateway)
        self._attr_unique_id = f"{gateway.gateway_id}_sound_test"

    @property
    def available(self):
        return self.gateway.can_sound_test()

    async def async_press(self):
        await self.gateway.async_sound_test()
