"""Integration tests for the battery / BMS detail sensors."""
from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus.const import DOMAIN


def _state(hass, entry, key: str) -> str:
    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{entry.unique_id}_{key}"
    entity = next(
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id == uid
    )
    return hass.states.get(entity.entity_id).state


async def test_bms_detail_sensors(hass, setup_storage):
    entry, fake = setup_storage
    fake.registers[3222] = 96    # SOH %
    fake.registers[3212] = 1     # BMS status -> Charging
    fake.registers[3230] = 3340  # cell voltage max 0.001V -> 3.34 V
    fake.registers[3219] = 5000  # max charge current 0.01A -> 50.0 A
    fake.registers[3167] = 7     # storage fault code

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "bms_soh") == "96"
    assert _state(hass, entry, "bms_status") == "Charging"
    assert float(_state(hass, entry, "bms_cell_voltage_max")) == 3.34
    assert float(_state(hass, entry, "bms_max_charge_current")) == 50.0
    assert _state(hass, entry, "storage_fault_code") == "7"
