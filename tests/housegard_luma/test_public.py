"""Synthetic behavioral cases only: no household names or captured user packets."""

import asyncio
import importlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from _luma_under_test.parser import parse_inventory, parse_sub_admin
from _luma_under_test.registry import SubdeviceRegistry
from conftest import PACKAGE


def packet(kind=2, alarm=0, index=42, name="Detector A", firmware=0x27):
    """Construct an artificial individual report using the established layout."""
    header = bytes(
        (3, 7, index, kind, 255, 255, alarm, 0, 0, 0, 85, 255, 255, 22, 50, 1, firmware)
    )
    encoded = name.encode("utf-16-le")
    return header + len(encoded).to_bytes(2, "little") + encoded


def inventory(kind=2, online=1):
    body = bytearray(packet(kind=kind)[2:-1])
    body[13] = online
    return bytes((2, 7, 1, len(body))) + body


@pytest.mark.parametrize("kind,field", [(2, "smoke"), (18, "heat")])
@pytest.mark.parametrize("state,expected", [(0, False), (1, True), (255, None)])
def test_alarm_states(kind, field, state, expected):
    device = parse_sub_admin(packet(kind=kind, alarm=state))
    assert getattr(device, field) is expected
    assert device.name == "Detector A"
    assert (device.battery, device.rssi, device.tamper) == (85, 50, False)


@pytest.mark.parametrize("name", ["A", "Detector B", "Example ø", "Demo 🔥"])
def test_name_framing(name):
    raw = packet(name=name)
    assert parse_sub_admin(raw).name == name
    if raw[-1] == 0:
        assert parse_sub_admin(raw[:-1]).name == name
    else:
        assert parse_sub_admin(raw[:-1]) is None
    assert parse_sub_admin(raw[:-2]) is None


@pytest.mark.parametrize("kind", [2, 18, 10])
def test_inventory_online_transitions(kind):
    registry = SubdeviceRegistry("example-gateway")
    for online in (1, 0, 1):
        raw = inventory(kind, online)
        assert len(parse_inventory(raw)) == 1
        registry.update_many(raw, received_at=datetime.now(UTC))
        assert registry.devices[42].online is bool(online)
        assert registry.inventory_counts == {
            "devices": 1,
            "online_devices": online,
            "offline_devices": 1 - online,
        }


@pytest.mark.parametrize("kind,field", [(2, "smoke"), (18, "heat")])
def test_remote_inventory_and_text_do_not_clear_alarm(kind, field):
    registry = SubdeviceRegistry("example-gateway")
    registry.update(packet(kind=kind, alarm=1))
    registry.update(packet(kind=10, index=43, name="Remote A"))
    registry.update_many(inventory(kind))
    registry.update("Detector A Alarm Restored SN:022A141C".encode("utf-16-be"))
    assert getattr(registry.devices[42], field) is True
    registry.update(packet(kind=kind, alarm=0))
    assert getattr(registry.devices[42], field) is False


def gateway(ha):
    module = importlib.import_module(f"{PACKAGE}.coordinator")
    entry = SimpleNamespace(
        entry_id="example",
        data={"tuya_entry_id": "example-tuya"},
        async_on_unload=lambda listener: None,
    )
    manager = SimpleNamespace(
        device_map={"example": SimpleNamespace(status={}, online=True)}
    )
    gw = module.LumaGateway(
        SimpleNamespace(add_job=ha.add_job, async_add_executor_job=ha.executor),
        entry,
        manager,
        "example",
    )
    entry.runtime_data = gw
    return gw, entry


@pytest.mark.parametrize(
    "kind,model", [(2, "Luma Smoke Alarm"), (18, "Luma Heat Alarm"), (10, "Luma RC350")]
)
@pytest.mark.parametrize("firmware", [0x27, 0x39, 0xFF])
def test_generic_model_survives_firmware_changes(ha, kind, model, firmware):
    gw, _ = gateway(ha)
    gw._publish_devices(gw.registry.update_many(packet(kind=kind, firmware=firmware)))
    assert ha.devices[("housegard_luma", "example_42")]["model"] == model


@pytest.mark.parametrize(
    "button_class",
    ["LumaRefreshButton", "LumaNetworkTestButton", "LumaSoundTestButton"],
)
def test_gateway_metadata_does_not_rename_device(ha, button_class):
    gw, _ = gateway(ha)
    button = getattr(importlib.import_module(f"{PACKAGE}.button"), button_class)(gw)
    assert button._attr_device_info == {
        "identifiers": {("tuya", "example")},
        "manufacturer": "Housegard",
        "model": "WS2GW-R",
    }


@pytest.mark.parametrize("kind,field", [(2, "smoke"), (18, "heat")])
def test_same_entity_updates_without_recreation(ha, kind, field):
    gw, entry = gateway(ha)
    platform = importlib.import_module(f"{PACKAGE}.binary_sensor")
    entities = []
    asyncio.run(platform.async_setup_entry(gw.hass, entry, entities.extend))
    alarm = None
    for state in (0, 1, 0):
        gw._publish_devices(gw.registry.update_many(packet(kind=kind, alarm=state)))
        ha.send(gw.hass, gw.signal)
        matches = [e for e in entities if e._attr_name.lower() == field]
        assert len(matches) == 1
        if alarm is None:
            alarm = matches[0]
        assert matches[0] is alarm and alarm.is_on is bool(state)


def test_store_round_trip_and_gateway_isolation(ha):
    storage = importlib.import_module(f"{PACKAGE}.storage")
    registry = SubdeviceRegistry("example-gateway")
    registry.update(packet(kind=18, alarm=1))
    data = storage.serialize(registry)
    assert storage.deserialize(data, "example-gateway")[42].heat is True
    with pytest.raises(ValueError):
        storage.deserialize(data, "another-example")


def test_command_constants_unchanged():
    from _luma_under_test.const import (
        INVENTORY_QUERY,
        NETWORK_TEST_COMMAND,
        SOUND_TEST_COMMAND,
    )

    assert INVENTORY_QUERY == "Agc="
    assert NETWORK_TEST_COMMAND == "Bwf/Azw="
    assert SOUND_TEST_COMMAND == "Bwf/Ag=="
