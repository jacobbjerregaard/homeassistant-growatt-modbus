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


async def test_per_battery_module_serial_sensors(hass, setup_storage_modules):
    entry, fake = setup_storage_modules
    # Module 1 serial "TESTSN01" at holding 5400 (2 ASCII chars per register).
    for addr, word in {5400: 0x5445, 5401: 0x5354, 5402: 0x534E, 5403: 0x3031}.items():
        fake.registers[addr] = word
    # Module 2 serial "MOD2" at holding 5440.
    for addr, word in {5440: 0x4D4F, 5441: 0x4432}.items():
        fake.registers[addr] = word

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "battery_module_1_serial_number") == "TESTSN01"
    assert _state(hass, entry, "battery_module_2_serial_number") == "MOD2"
