"""Device-reported battery and RSSI, without inferred conversions."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import LumaEntity, async_setup_subdevices


async def async_setup_entry(hass, entry, async_add_entities):
    registry = er.async_get(hass)
    obsolete = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.runtime_data.gateway_id}_unknown_devices"
    )
    if obsolete is not None:
        record = registry.async_get(obsolete)
        if record is not None and record.config_entry_id == entry.entry_id:
            registry.async_remove(obsolete)
    async_add_entities(
        [
            LumaInventoryCount(entry.runtime_data, key)
            for key in ("devices", "online_devices", "offline_devices")
        ]
    )
    async_setup_subdevices(
        hass,
        entry,
        async_add_entities,
        lambda gateway, index: [
            LumaSensor(gateway, index, key) for key in ("battery", "rssi", "last_seen")
        ],
        device_types=(0x02, 0x17, 0x12, 0x0A),
    )


class LumaSensor(LumaEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, gateway, index, key):
        super().__init__(gateway, index, key)
        self.key = key
        self._attr_translation_key = key
        if key == "battery":
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif key == "last_seen":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        else:
            self._attr_icon = "mdi:wifi"
            # HA signal_strength requires dB/dBm. The protocol's positive
            # byte has no verified unit; do not misrepresent it as dBm.

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def native_value(self):
        return getattr(self.device, self.key)


class LumaInventoryCount(SensorEntity):
    """Counts of retained inventory records, not inferred test completion."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:counter"

    def __init__(self, gateway, key):
        self.gateway = gateway
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{gateway.gateway_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={("tuya", gateway.gateway_id)})

    @property
    def available(self):
        return self.gateway.available

    @property
    def native_value(self):
        counts = self.gateway.registry.inventory_counts
        return counts[self.key] if counts is not None else None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.gateway.signal, self.async_write_ha_state
            )
        )
