"""Release checks using synthetic packets and HA interface doubles only."""

import asyncio
import importlib
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import PACKAGE, ROOT
from test_public import gateway, inventory, packet


class ExistingMQ:
    def __init__(self):
        self.listeners = []

    def add_message_listener(self, listener):
        assert listener not in self.listeners
        self.listeners.append(listener)

    def remove_message_listener(self, listener):
        self.listeners.remove(listener)


def integration():
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.integration", ROOT / "__init__.py"
    )
    spec.submodule_search_locations = None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostics_excludes_identifiers_and_reversible_payloads(ha):
    gw, entry = gateway(ha)
    now = datetime.now(UTC)
    name = "Private synthetic room"
    gw.registry.update_many(packet(name=name), received_at=now)
    gw.registry.update_many(inventory(), received_at=now)
    gw.capture.record(packet(name=name), "live_report")
    gw.capture.record(inventory(), "live_report")
    alarm = f"{name} Smoke Triggered SN:ABCDEF12".encode("utf-16-be")
    operation = f"{name} Locate Device SN:ABCDEF12".encode("utf-16-be")
    gw.alarm_capture.record(alarm, "live_report")
    gw.operation_capture.record(operation, "live_report")
    # An export must never traverse the manager's account/device metadata.
    gw.manager.local_key = "synthetic-secret"
    gw.manager.token = "synthetic-token"
    module = importlib.import_module(f"{PACKAGE}.diagnostics")
    result = asyncio.run(module.async_get_config_entry_diagnostics(gw.hass, entry))
    encoded = json.dumps(result, default=str)
    for private in (
        name,
        "Detector A",
        "ABCDEF12",
        "example",
        "synthetic-secret",
        "synthetic-token",
    ):
        assert private not in encoded
    for forbidden in ("base64", "hex", "decoded_text", "gateway_id", "header_hex"):
        assert f'"{forbidden}"' not in encoded
    assert result["gateway_model"] == "Luma GW650"
    assert result["gateway_tuya_model"] == "WS2GW-R"
    assert result["inventory_counts"]["online_devices"] == 1
    assert result["subdevices"][0]["name"] == "**REDACTED**"
    assert result["subdevices"][0]["last_seen"] == now
    assert (
        result["dp26_capture"]["packets"][0]["event_classification"]
        == "smoke_triggered"
    )
    assert (
        result["operation_log_capture"]["packets"][0]["event_classification"]
        == "locate"
    )
    assert result["inventory_protocol"]["records"][0]["online_status_raw"] == 1
    assert gw.capture.diagnostics()["contains_raw_device_names"] is True
    assert gw.registry.devices[42].name == "Detector A"


def test_entity_translations_metadata_and_fresh_telemetry(ha):
    gw, entry = gateway(ha)
    entities = {}
    for platform in ("sensor", "binary_sensor", "button"):
        module = importlib.import_module(f"{PACKAGE}.{platform}")
        entities[platform] = []
        gw.registry.update_many(inventory(), received_at=datetime.now(UTC))
        asyncio.run(module.async_setup_entry(gw.hass, entry, entities[platform].extend))
    english = json.loads((ROOT / "translations/en.json").read_text(encoding="utf-8"))
    assert json.loads((ROOT / "strings.json").read_text(encoding="utf-8")) == english
    norwegian = json.loads((ROOT / "translations/nb.json").read_text(encoding="utf-8"))
    assert norwegian["entity"]["binary_sensor"]["smoke"]["name"] == "Røyk"
    for platform, members in entities.items():
        for entity in members:
            key = entity._attr_translation_key
            assert english["entity"][platform][key]["name"]
            assert norwegian["entity"][platform][key]["name"]
            assert not hasattr(entity, "_attr_name")
            assert entity._attr_has_entity_name is True
            assert entity._attr_should_poll is False
    sensors = {entity.key: entity for entity in entities["sensor"]}
    assert sensors["battery"]._attr_device_class == "battery"
    assert sensors["battery"]._attr_native_unit_of_measurement == "%"
    assert sensors["last_seen"]._attr_device_class == "timestamp"
    assert not hasattr(sensors["rssi"], "_attr_device_class")
    assert not hasattr(sensors["rssi"], "_attr_native_unit_of_measurement")
    for key in ("battery", "rssi", "last_seen"):
        assert sensors[key]._attr_entity_category == "diagnostic"
        assert not hasattr(sensors[key], "_attr_state_class")
        assert not hasattr(sensors[key], "_unrecorded_attributes")
    now = datetime.now(UTC)
    for offset, rssi in enumerate((68, 69, 68)):
        raw = bytearray(packet())
        raw[14] = rssi
        received = now + timedelta(seconds=offset)
        gw.registry.update_many(raw, received_at=received)
        assert sensors["rssi"].native_value == rssi
        assert sensors["last_seen"].native_value == received
    gw.registry.update_many(inventory(online=0), received_at=received)
    assert sensors["last_seen"].native_value == received
    binary = {
        entity._attr_translation_key: entity for entity in entities["binary_sensor"]
    }
    for key, device_class in (
        ("smoke", "smoke"),
        ("tamper", "tamper"),
        ("online", "connectivity"),
    ):
        assert binary[key]._attr_device_class == device_class
    assert binary["online"].is_on is False
    assert binary["online"]._attr_entity_category == "diagnostic"
    assert binary["smoke"].is_on is False
    assert binary["tamper"].is_on is False
    assert "unknown_devices" not in sensors


def test_config_flow_ignores_unloaded_tuya_entries(ha, monkeypatch):
    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            pass

        def _async_current_entries(self):
            return []

        def async_abort(self, **kwargs):
            return {"type": "abort", **kwargs}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

    monkeypatch.setattr(
        sys.modules["homeassistant.config_entries"],
        "ConfigFlow",
        ConfigFlow,
        raising=False,
    )
    monkeypatch.delitem(sys.modules, f"{PACKAGE}.config_flow", raising=False)
    flow = importlib.import_module(f"{PACKAGE}.config_flow").HouseguardLumaConfigFlow()
    entries = [SimpleNamespace(entry_id="unloaded"), SimpleNamespace(runtime_data=None)]
    flow.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _: entries)
    )
    assert asyncio.run(flow.async_step_user()) == {
        "type": "abort",
        "reason": "no_gateways",
    }
    device = SimpleNamespace(
        id="synthetic-gateway", name="Example gateway", product_id="s3x3xmgbeohtvm40"
    )
    entries.append(
        SimpleNamespace(
            entry_id="ready",
            runtime_data=SimpleNamespace(
                manager=SimpleNamespace(device_map={device.id: device})
            ),
        )
    )
    assert asyncio.run(flow.async_step_user())["type"] == "form"


@pytest.mark.parametrize(
    "button_class",
    ["LumaRefreshButton", "LumaNetworkTestButton", "LumaSoundTestButton"],
)
def test_gateway_buttons_receive_availability_updates_and_cleanup(ha, button_class):
    gw, _ = gateway(ha)
    gw.manager.mq = ExistingMQ()
    gw.manager.send_commands = lambda *args: None
    button = getattr(importlib.import_module(f"{PACKAGE}.button"), button_class)(gw)
    button.hass = gw.hass
    asyncio.run(button.async_added_to_hass())
    assert button.available is True
    gw.manager.device_map["example"].online = False
    ha.send(gw.hass, gw.signal)
    assert button.writes == 1 and button.available is False
    button.remove()
    ha.send(gw.hass, gw.signal)
    assert button.writes == 1


def test_excessively_long_numeric_dp_id_does_not_escape_callback(ha):
    gw, _ = gateway(ha)
    gw.capture.receive(
        {
            "protocol": 4,
            "data": {
                "devId": "example",
                "status": [{"dpId": "1" * 5000, "value": packet()}],
            },
        }
    )
    ha.drain_jobs()
    assert not gw.registry.devices


@pytest.mark.parametrize(
    "failure", [False, {"success": False}, OSError("synthetic-secret")]
)
def test_refresh_failure_is_actionable_and_redacted(ha, failure):
    gw, _ = gateway(ha)
    gw.manager.mq = ExistingMQ()

    def send(*args):
        if isinstance(failure, Exception):
            raise failure
        return failure

    gw.manager.send_commands = send
    button = importlib.import_module(f"{PACKAGE}.button").LumaRefreshButton(gw)
    with pytest.raises(RuntimeError, match="Could not send Refresh devices command"):
        asyncio.run(button.async_press())
    assert not ha.later
    gw.manager.device_map["example"].online = False
    assert button.available is False
    with pytest.raises(RuntimeError, match="Refresh devices is unavailable"):
        asyncio.run(button.async_press())


@pytest.mark.parametrize(
    "code,dp_id", [([], 38), ({}, 38), ("sub_admin", []), ("sub_admin", {}), (None, [])]
)
def test_malformed_capture_metadata_is_ignored_safely(ha, code, dp_id):
    gw, _ = gateway(ha)
    gw.capture.receive(
        {
            "protocol": 4,
            "data": {
                "devId": "example",
                "status": [{"code": code, "dpId": dp_id, "value": packet()}],
            },
        }
    )
    ha.drain_jobs()
    # A valid explicit code with an unknown raw ID remains accepted.
    assert bool(gw.registry.devices) is (code == "sub_admin")


@pytest.mark.parametrize("setup_error", [None, RuntimeError, asyncio.CancelledError])
def test_setup_reload_cleanup_and_gateway_isolation(ha, setup_error):
    module = integration()
    mq = ExistingMQ()
    sent = []
    manager = SimpleNamespace(
        mq=mq,
        device_map={
            key: SimpleNamespace(status={}, online=True)
            for key in ("gateway-a", "gateway-b")
        },
        send_commands=lambda *args: sent.append(args),
    )
    cleanups = {}

    def entry(key):
        cleanups[key] = []
        return SimpleNamespace(
            entry_id=key,
            data={"tuya_entry_id": "tuya", "gateway_id": key},
            async_on_unload=cleanups[key].append,
        )

    async def forward(actual, platforms):
        if setup_error is not None:
            raise setup_error("synthetic platform failure")

    async def unload(actual, platforms):
        return True

    hass = SimpleNamespace(
        add_job=ha.add_job,
        async_add_executor_job=ha.executor,
        config_entries=SimpleNamespace(
            async_get_entry=lambda _: SimpleNamespace(
                runtime_data=SimpleNamespace(manager=manager)
            ),
            async_forward_entry_setups=forward,
            async_unload_platforms=unload,
        ),
    )

    async def cleanup(actual):
        for listener in reversed(cleanups[actual.entry_id]):
            result = listener()
            if result is not None:
                await result

    async def scenario():
        a = entry("gateway-a")
        if setup_error is not None:
            with pytest.raises(setup_error, match="synthetic platform failure"):
                await module.async_setup_entry(hass, a)
            await cleanup(a)
            assert not sent
        else:
            b = entry("gateway-b")
            assert await module.async_setup_entry(hass, a)
            assert await module.async_setup_entry(hass, b)
            assert len(mq.listeners) == 6
            assert a.runtime_data.signal != b.runtime_data.signal
            assert sent == [
                (key, [{"code": "sub_admin", "value": "Agc="}])
                for key in ("gateway-a", "gateway-b")
            ]
            old = a.runtime_data
            assert await module.async_unload_entry(hass, a)
            await cleanup(a)
            assert len(mq.listeners) == 3
            assert old._closed is True
            # Reload the same entry without duplicating old MQ listeners.
            a = entry("gateway-a")
            assert await module.async_setup_entry(hass, a)
            assert len(mq.listeners) == 6
            assert await module.async_unload_entry(hass, a)
            await cleanup(a)
            assert await module.async_unload_entry(hass, b)
            await cleanup(b)
        assert not mq.listeners
        assert not ha.timers
        assert not ha.later
        assert all(not listeners for listeners in ha.signals.values())

    asyncio.run(scenario())


@pytest.mark.parametrize("kind,field", [(2, "smoke"), (18, "heat")])
def test_restore_cached_inventory_and_verified_alarm_clear(ha, kind, field):
    storage = importlib.import_module(f"{PACKAGE}.storage")
    gw, _ = gateway(ha)
    now = datetime.now(UTC)
    gw.registry.update_many(packet(kind=kind, alarm=1), received_at=now)
    gw.registry.update_many(inventory(kind=kind, online=1), received_at=now)
    gw.registry.devices = storage.deserialize(storage.serialize(gw.registry), "example")
    device = gw.registry.devices[42]
    assert device.online is None
    assert getattr(device, field) is True
    assert (device.battery, device.rssi, device.last_seen) == (85, 50, now)
    gw.registry.update_many(inventory(kind=kind), cached=True)
    assert gw.registry.devices[42].online is None
    gw.registry.update_many(packet(kind=kind, alarm=255), received_at=now)
    assert getattr(gw.registry.devices[42], field) is True
    gw.registry.update_many(inventory(kind=kind, online=0), received_at=now)
    assert gw.registry.devices[42].online is False
    gw.registry.update_many(packet(kind=kind, alarm=0), received_at=now)
    assert getattr(gw.registry.devices[42], field) is False


@pytest.mark.parametrize("kind", [2, 18])
def test_locate_targets_current_index_and_selected_gateway_only(ha, kind):
    first, _ = gateway(ha)
    module = importlib.import_module(f"{PACKAGE}.coordinator")
    first.manager.device_map["another"] = SimpleNamespace(status={}, online=True)
    second = module.LumaGateway(
        first.hass,
        SimpleNamespace(entry_id="another", data={"tuya_entry_id": "tuya"}),
        first.manager,
        "another",
    )
    first.manager.mq = ExistingMQ()
    sent = []
    first.manager.send_commands = lambda *args: sent.append(args)
    first.handle_update()
    second.handle_update()
    assert sent == []
    first.registry.update_many(packet(kind=kind, index=42, alarm=1))
    second.registry.update_many(packet(kind=kind, index=43, alarm=1))
    asyncio.run(second.async_locate(43))
    assert sent == [("another", [{"code": "sub_admin", "value": "BwcrBA=="}])]
    assert first.registry.devices[42].online is None
    assert second.registry.devices[43].online is None
    field = "smoke" if kind == 2 else "heat"
    assert getattr(first.registry.devices[42], field) is True
    assert getattr(second.registry.devices[43], field) is True
    asyncio.run(first.async_close())
    asyncio.run(second.async_close())


def test_partial_inventory_retains_devices_and_unknown_type_has_generic_model(ha):
    gw, _ = gateway(ha)
    gw.registry.update_many(packet(index=43))
    gw.registry.update_many(inventory(), received_at=datetime.now(UTC))
    gw.registry.update_many(inventory(online=0), received_at=datetime.now(UTC))
    assert set(gw.registry.devices) == {42, 43}
    gw._publish_devices(gw.registry.update_many(packet(kind=255, index=44)))
    assert ha.devices[("housegard_luma", "example_44")]["model"] == "Luma subdevice"


def test_manifest_and_public_artifact_metadata():
    repo = Path(__file__).resolve().parents[2]
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((repo / "hacs.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "housegard_luma"
    assert manifest["dependencies"] == ["tuya"]
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_push"
    assert manifest["integration_type"] == "hub"
    assert hacs["homeassistant"] == "2026.9.4"
    assert f"## {manifest['version']}" in (repo / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
