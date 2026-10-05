"""Explicit gateway actions and per-alarm Locate buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
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
    _attr_name = "Refresh devices"
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

    async def async_press(self):
        await self.gateway.async_request_inventory()


class LumaLocateButton(LumaEntity, ButtonEntity):
    _attr_name = "Locate"
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

    _attr_name = "Network Test"
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

    _attr_name = "Sound Test"
    _attr_icon = "mdi:volume-high"

    def __init__(self, gateway):
        super().__init__(gateway)
        self._attr_unique_id = f"{gateway.gateway_id}_sound_test"

    @property
    def available(self):
        return self.gateway.can_sound_test()

    async def async_press(self):
        await self.gateway.async_sound_test()
