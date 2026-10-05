from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_GATEWAY_ID, CONF_TUYA_ENTRY_ID, DOMAIN, LUMA_PRODUCT_ID


class HouseguardLumaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        choices = {}
        for tuya_entry in self.hass.config_entries.async_entries("tuya"):
            runtime = getattr(tuya_entry, "runtime_data", None)
            manager = getattr(runtime, "manager", None)
            if manager is None:
                continue
            for device in manager.device_map.values():
                if getattr(device, "product_id", None) == LUMA_PRODUCT_ID:
                    key = f"{tuya_entry.entry_id}:{device.id}"
                    choices[key] = f"{device.name} ({device.id[-6:]})"

        configured = {
            e.data.get(CONF_GATEWAY_ID) for e in self._async_current_entries()
        }
        choices = {
            k: v for k, v in choices.items() if k.split(":", 1)[1] not in configured
        }
        if not choices:
            return self.async_abort(reason="no_gateways")

        if user_input is not None:
            selected = user_input["gateway"]
            if selected not in choices:
                return self.async_abort(reason="no_gateways")
            tuya_entry_id, gateway_id = selected.split(":", 1)
            await self.async_set_unique_id(gateway_id)
            self._abort_if_unique_id_configured()
            tuya_entry = self.hass.config_entries.async_get_entry(tuya_entry_id)
            dev = tuya_entry.runtime_data.manager.device_map[gateway_id]
            return self.async_create_entry(
                title=dev.name or f"Luma {gateway_id[-6:]}",
                data={CONF_TUYA_ENTRY_ID: tuya_entry_id, CONF_GATEWAY_ID: gateway_id},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("gateway"): vol.In(choices)}),
        )
