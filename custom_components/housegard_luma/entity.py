"""Shared push entity and discovery support."""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


@callback
def async_setup_subdevices(
    hass, entry, async_add_entities, factory, *, device_types=(0x02, 0x12)
):
    gateway = entry.runtime_data
    added = set()

    @callback
    def discover():
        entities = []
        for index, device in gateway.registry.devices.items():
            if index not in added and device.device_type in device_types:
                added.add(index)
                entities.extend(factory(gateway, index))
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(async_dispatcher_connect(hass, gateway.signal, discover))
    discover()


class LumaEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, gateway, index, key):
        self.gateway = gateway
        self.index = index
        identifier = gateway.registry.identifier(index)
        self._attr_unique_id = f"{identifier}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, identifier)})

    @property
    def device(self):
        return self.gateway.registry.devices[self.index]

    @property
    def available(self):
        return self.gateway.available

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.gateway.signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self):
        self.async_write_ha_state()
