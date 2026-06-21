"""Integration test: config-entry setup creates the expected entities."""
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus.const import DOMAIN


async def test_storage_entities_created(hass, setup_storage):
    entry, _fake = setup_storage
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    assert entities, "no entities were created"
    by_uid = {e.unique_id: e for e in entities}

    def uid(key: str) -> str:
        return f"{DOMAIN}_{entry.unique_id}_{key}"

    # All four platforms must be present for a storage device.
    domains = {e.entity_id.split(".")[0] for e in entities}
    assert {"sensor", "number", "select", "switch"} <= domains

    # A representative entity from each platform.
    assert uid("soc") in by_uid                  # sensor
    assert uid("grid_first_stop_soc") in by_uid  # number
    assert uid("battery_type") in by_uid         # select
    assert uid("ac_charge_enabled") in by_uid    # switch


async def test_entity_categories_and_naming(hass, setup_storage):
    entry, _fake = setup_storage
    registry = er.async_get(hass)
    by_uid = {
        e.unique_id: e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    def uid(key: str) -> str:
        return f"{DOMAIN}_{entry.unique_id}_{key}"

    # Controls are configuration entities.
    assert by_uid[uid("grid_first_stop_soc")].entity_category == EntityCategory.CONFIG
    assert by_uid[uid("battery_type")].entity_category == EntityCategory.CONFIG
    # Internal readings are diagnostic.
    assert by_uid[uid("parallel_battery_num")].entity_category == EntityCategory.DIAGNOSTIC
    # Primary telemetry has no category.
    assert by_uid[uid("soc")].entity_category is None

    # has_entity_name: friendly name is "<device name> <entity name>".
    soc = hass.states.get(by_uid[uid("soc")].entity_id)
    assert soc.attributes["friendly_name"] == "Growatt Test SOC"


async def test_unload_entry(hass, setup_storage):
    entry, _fake = setup_storage
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_soc_sensor_has_state(hass, setup_storage):
    entry, fake = setup_storage
    fake.registers[3171] = 87  # SOC register
    # Refresh through the coordinator (re-reads via the fake transport).
    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    soc_uid = f"{DOMAIN}_{entry.unique_id}_soc"
    soc = next(
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id == soc_uid
    )
    state = hass.states.get(soc.entity_id)
    assert state is not None
    assert state.state == "87"


async def test_inverter_entities_created(hass, fake_modbus):
    """An inverter (non-storage) device sets up via the inverter sensor path."""
    from unittest.mock import patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from homeassistant.const import (
        CONF_ADDRESS,
        CONF_MODEL,
        CONF_NAME,
        CONF_SCAN_INTERVAL,
        CONF_TYPE,
    )
    from custom_components.growatt_modbus.const import (
        CONF_AC_PHASES,
        CONF_BATTERY_MODULES,
        CONF_BAUDRATE,
        CONF_BYTESIZE,
        CONF_DC_STRING,
        CONF_FIRMWARE,
        CONF_LAYER,
        CONF_PARITY,
        CONF_POWER_SCAN_ENABLED,
        CONF_POWER_SCAN_INTERVAL,
        CONF_SERIAL,
        CONF_SERIAL_NUMBER,
        CONF_SERIAL_PORT,
        CONF_STOPBITS,
        CONF_TOU_SLOTS,
    )

    data = {
        CONF_BATTERY_MODULES: 0,
        CONF_TOU_SLOTS: 0,
        CONF_LAYER: CONF_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUDRATE: 9600,
        CONF_STOPBITS: 1,
        CONF_PARITY: "None",
        CONF_BYTESIZE: 8,
        CONF_ADDRESS: 1,
        CONF_TYPE: "inverter_120",
        CONF_NAME: "Inv",
        CONF_MODEL: "MIC",
        CONF_DC_STRING: 2,
        CONF_AC_PHASES: 1,
        CONF_SCAN_INTERVAL: 60,
        CONF_POWER_SCAN_ENABLED: False,
        CONF_POWER_SCAN_INTERVAL: 5,
        CONF_SERIAL_NUMBER: "INVSERIAL1",
        CONF_FIRMWARE: "F1",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id="INVSERIAL1", title="Inv")
    entry.add_to_hass(hass)
    with patch(
        "custom_components.growatt_modbus.GrowattSerial", return_value=fake_modbus
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert entities
    assert "sensor" in {e.entity_id.split(".")[0] for e in entities}
