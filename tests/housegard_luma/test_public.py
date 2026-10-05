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
    registry.update("Detector A Alarm Restored SN:ABCDEF12".encode("utf-16-be"))
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
        "model": "Luma GW650",
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
        matches = [e for e in entities if e._attr_translation_key == field]
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


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Remote A Test Device SN:ABCDEF12", "test"),
        ("Remote A Silence Device SN:ABCDEF12", "hush"),
        ("Remote A Locate Device SN:ABCDEF12", "locate"),
        ("Remote A Locate Device No:ABCDEF12345", "locate"),
        ("Remote B SilHncH DHvice SN:12345678", "hush"),
        ("Remote A Locate Device SN:invalid", None),
        ("Remote A Unknown Device SN:ABCDEF12", None),
    ],
)
def test_operation_diagnostic_vocabulary(text, expected):
    from _luma_under_test.operation_log import classify_operation_log

    assert classify_operation_log(text.encode("utf-16-be")) == expected


def test_remote_reports_and_logs_never_send_commands(ha):
    gw, _ = gateway(ha)
    sent = []
    gw.manager.send_commands = lambda *args: sent.append(args)
    gw.registry.update(packet(alarm=1))
    gw._handle_live_packet(
        SimpleNamespace(
            value=packet(kind=10, index=43, name="Remote A"),
            code="sub_admin",
            received_at=datetime.now(UTC).isoformat(),
        )
    )
    gw._handle_operation_packet(
        SimpleNamespace(
            value="Remote A Locate Device SN:ABCDEF12".encode("utf-16-be"),
            origin="live_report",
            truncated=False,
            received_at=datetime.now(UTC).isoformat(),
        )
    )
    assert sent == []
    assert gw.registry.devices[42].smoke is True
    assert gw.registry.devices[43].device_type == 10


@pytest.mark.parametrize(
    "method,args,payload",
    [
        ("async_locate", (42,), "BwcqBA=="),
        ("async_network_test", (), "Bwf/Azw="),
        ("async_sound_test", (), "Bwf/Ag=="),
        ("async_request_inventory", (), "Agc="),
    ],
)
def test_explicit_commands_use_existing_tuya_manager(ha, method, args, payload):
    gw, _ = gateway(ha)
    gw.registry.update(packet())
    gw.manager.mq = SimpleNamespace(add_message_listener=lambda listener: None)
    sent = []
    gw.manager.send_commands = lambda *args: sent.append(args)
    asyncio.run(getattr(gw, method)(*args))
    assert sent == [("example", [{"code": "sub_admin", "value": payload}])]


@pytest.mark.parametrize("result", [False, {"success": False}, OSError("private")])
@pytest.mark.parametrize("method", ["async_network_test", "async_sound_test"])
def test_command_failures_are_reported_without_transport_details(ha, method, result):
    gw, _ = gateway(ha)
    gw.manager.mq = object()

    def send(*args):
        if isinstance(result, Exception):
            raise result
        return result

    gw.manager.send_commands = send
    with pytest.raises(RuntimeError) as error:
        asyncio.run(getattr(gw, method)())
    assert "private" not in str(error.value)
    assert gw.registry.devices == {}
