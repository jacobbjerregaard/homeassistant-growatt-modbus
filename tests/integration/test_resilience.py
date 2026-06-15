"""Tests for connection resilience and the per-module unique_id migration."""
from unittest.mock import AsyncMock, patch

from pymodbus.exceptions import ConnectionException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus import _async_migrate_module_unique_ids
from custom_components.growatt_modbus.const import CONF_SERIAL_NUMBER, DOMAIN


def _any_sensor_entity_id(hass, entry):
    registry = er.async_get(hass)
    for e in er.async_entries_for_config_entry(registry, entry.entry_id):
        if e.domain == "sensor":
            return e.entity_id
    raise AssertionError("no sensor entity found")


async def test_entities_unavailable_on_connection_loss(hass, setup_storage):
    entry, _fake = setup_storage
    entity_id = _any_sensor_entity_id(hass, entry)
    assert hass.states.get(entity_id).state != "unavailable"

    # A dropped Modbus link must surface as UpdateFailed so the entities go
    # unavailable instead of silently keeping their last value.
    with patch.object(
        entry.runtime_data.device,
        "update",
        new=AsyncMock(side_effect=ConnectionException("lost")),
    ):
        await entry.runtime_data.main_coordinator.async_refresh()
        await hass.async_block_till_done()

    assert entry.runtime_data.main_coordinator.last_update_success is False
    assert hass.states.get(entity_id).state == "unavailable"


async def test_setup_retries_when_device_unreachable(setup_unreachable):
    # ConfigEntryNotReady -> HA schedules a retry rather than failing outright.
    assert setup_unreachable.state is ConfigEntryState.SETUP_RETRY


async def test_migrates_slot_unique_ids_to_serial(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_NUMBER: "INV1"},
        unique_id="INV1",
        title="Growatt Test",
    )
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    # A pre-0.12 slot-based per-module entity...
    old = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_INV1_battery_module_1_soc", config_entry=entry
    )
    # ...and an unrelated entity that must be left untouched.
    other = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_INV1_battery_voltage", config_entry=entry
    )

    await _async_migrate_module_unique_ids(hass, entry, {1: "MODONE", 2: "MODTWO"})

    assert registry.async_get(old.entity_id).unique_id == f"{DOMAIN}_INV1_module_MODONE_soc"
    assert registry.async_get(other.entity_id).unique_id == f"{DOMAIN}_INV1_battery_voltage"
