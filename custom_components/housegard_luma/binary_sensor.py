"""Verified detector smoke, heat and tamper state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory

from .entity import LumaEntity, async_setup_subdevices


async def async_setup_entry(hass, entry, async_add_entities):
    async_setup_subdevices(
        hass,
        entry,
        async_add_entities,
        _detector_entities,
    )
    async_setup_subdevices(
        hass,
        entry,
        async_add_entities,
        lambda gateway, index: [LumaOnline(gateway, index)],
        device_types=(0x02, 0x12, 0x0A),
    )


class LumaTamper(LumaEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_name = "Tamper"

    def __init__(self, gateway, index):
        super().__init__(gateway, index, "tamper")

    @property
    def is_on(self):
        return self.device.tamper


def _detector_entities(gateway, index):
    entities = [LumaTamper(gateway, index)]
    if gateway.registry.devices[index].device_type == 0x02:
        entities.append(LumaSmoke(gateway, index))
    elif gateway.registry.devices[index].device_type == 0x12:
        entities.append(LumaHeat(gateway, index))
    return entities


class LumaSmoke(LumaEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _attr_name = "Smoke"

    def __init__(self, gateway, index):
        super().__init__(gateway, index, "smoke")

    @property
    def available(self):
        return super().available and self.is_on is not None

    @property
    def is_on(self):
        return self.device.smoke


class LumaHeat(LumaEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_name = "Heat"

    def __init__(self, gateway, index):
        super().__init__(gateway, index, "heat")

    @property
    def available(self):
        return super().available and self.is_on is not None

    @property
    def is_on(self):
        return self.device.heat


class LumaOnline(LumaEntity, BinarySensorEntity):
    """Last fresh inventory reachability, independent of entity availability."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, gateway, index):
        super().__init__(gateway, index, "online")

    @property
    def is_on(self):
        return self.device.online
