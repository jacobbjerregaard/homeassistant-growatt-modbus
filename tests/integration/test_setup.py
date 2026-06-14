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
