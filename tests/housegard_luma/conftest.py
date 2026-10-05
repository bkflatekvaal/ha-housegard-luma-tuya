"""Load protocol code without executing the Home Assistant entry point."""

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "housegard_luma"
PACKAGE = "_luma_under_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package


@pytest.fixture
def ha(monkeypatch):
    """Small HA interface doubles; these tests do not claim full HA integration."""

    def module(name, **attrs):
        result = types.ModuleType(name)
        result.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, result)
        return result

    stores = {}
    jobs = []

    class Store:
        def __init__(self, hass, version, key, **kwargs):
            self.version, self.key = version, key
            self.pending = None
            self.saves = 0

        async def async_load(self):
            from copy import deepcopy

            return deepcopy(stores.get(self.key))

        def async_delay_save(self, data_func, delay):
            self.pending = data_func
            self.delay = delay

        async def async_save(self, data):
            from copy import deepcopy

            stores[self.key] = deepcopy(data)
            self.pending = None
            self.saves += 1

        async def fire_delay(self):
            if self.pending:
                await self.async_save(self.pending())

    def add_job(func, *args):
        jobs.append((func, args))

    def drain_jobs():
        while jobs:
            func, args = jobs.pop(0)
            func(*args)

    timers = []
    later = []

    def call_later(hass, delay, listener):
        later.append(listener)

        def cancel():
            if listener in later:
                later.remove(listener)

        return cancel

    async def executor(func, *args):
        return func(*args)

    signals = {}
    devices = {}
    parents = {}
    parent_lookups = []

    def connect(hass, signal, listener):
        signals.setdefault(signal, []).append(listener)
        return lambda: signals[signal].remove(listener)

    def send(hass, signal):
        for listener in list(signals.get(signal, [])):
            listener()

    def create(**kwargs):
        assert "via_device" not in kwargs, "Deprecated parent argument used"
        devices[next(iter(kwargs["identifiers"]))] = kwargs

    def get_by_identifier(identifier, config_entry_id):
        parent_lookups.append((identifier, config_entry_id))
        return parents.get((identifier, config_entry_id))

    # Deliberately omit deprecated async_get_device: any use fails the suite.
    registry = types.SimpleNamespace(
        async_get_device_by_identifier=get_by_identifier,
        async_get_or_create=create,
    )

    class Entity:
        def __init__(self):
            pass

        async def async_added_to_hass(self):
            pass

        def async_on_remove(self, listener):
            self.remove = listener

        def async_write_ha_state(self):
            self.writes = getattr(self, "writes", 0) + 1

    module("homeassistant")
    module("homeassistant.core", callback=lambda f: f, HomeAssistant=object)
    module("homeassistant.helpers")
    module(
        "homeassistant.helpers.entity_registry",
        async_get=lambda hass: types.SimpleNamespace(
            async_get_entity_id=lambda *args: None,
        ),
    )
    module("homeassistant.helpers.storage", Store=Store)

    def track_interval(hass, listener, interval):
        timers.append(listener)
        return lambda: timers.remove(listener)

    module(
        "homeassistant.helpers.event",
        async_track_time_interval=track_interval,
        async_call_later=call_later,
    )
    module(
        "homeassistant.helpers.device_registry",
        async_get=lambda hass: registry,
        DeviceInfo=dict,
    )
    module(
        "homeassistant.helpers.dispatcher",
        async_dispatcher_connect=connect,
        async_dispatcher_send=send,
    )
    module(
        "homeassistant.helpers.entity",
        Entity=Entity,
        EntityCategory=types.SimpleNamespace(DIAGNOSTIC="diagnostic"),
    )
    module("homeassistant.components")
    module(
        "homeassistant.components.button",
        ButtonEntity=type("ButtonEntity", (Entity,), {}),
    )
    module(
        "homeassistant.components.binary_sensor",
        BinarySensorEntity=type("BinarySensorEntity", (Entity,), {}),
        BinarySensorDeviceClass=types.SimpleNamespace(
            TAMPER="tamper", SMOKE="smoke", HEAT="heat", CONNECTIVITY="connectivity"
        ),
    )
    module(
        "homeassistant.components.sensor",
        SensorEntity=type("SensorEntity", (Entity,), {}),
        SensorDeviceClass=types.SimpleNamespace(
            BATTERY="battery", TIMESTAMP="timestamp"
        ),
    )
    module(
        "homeassistant.const",
        PERCENTAGE="%",
        Platform=types.SimpleNamespace(
            SENSOR="sensor", BINARY_SENSOR="binary_sensor", BUTTON="button"
        ),
    )
    module("homeassistant.config_entries", ConfigEntry=object)

    class ConfigEntryNotReady(Exception):
        pass

    module(
        "homeassistant.exceptions",
        ConfigEntryNotReady=ConfigEntryNotReady,
        HomeAssistantError=RuntimeError,
    )
    # Ensure each test imports modules against its own doubles.
    for name in (
        "coordinator",
        "entity",
        "sensor",
        "binary_sensor",
        "integration",
        "storage",
        "button",
    ):
        monkeypatch.delitem(sys.modules, f"{PACKAGE}.{name}", raising=False)
    return types.SimpleNamespace(
        later=later,
        executor=executor,
        stores=stores,
        jobs=jobs,
        add_job=add_job,
        drain_jobs=drain_jobs,
        signals=signals,
        devices=devices,
        parents=parents,
        parent_lookups=parent_lookups,
        send=send,
        not_ready=ConfigEntryNotReady,
        timers=timers,
    )
