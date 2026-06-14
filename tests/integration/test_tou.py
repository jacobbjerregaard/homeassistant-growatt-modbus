"""Integration tests for the time-of-use slot GUI entities."""
from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus.const import DOMAIN

# Slot 1 encoded: start 01:30, end 05:45, priority battery (1), enabled.
SLOT1_WORD1 = 30 | (1 << 8) | (1 << 13) | (1 << 15)  # 41246
SLOT1_WORD2 = 45 | (5 << 8)  # 1325


def _entity_id(hass, entry, field_suffix: str) -> str:
    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{entry.unique_id}_tou_slot_1_{field_suffix}"
    entity = next(
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id == uid
    )
    return entity.entity_id


async def _refresh(hass, entry):
    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_tou_entities_reflect_registers(hass, setup_storage_tou):
    entry, fake = setup_storage_tou
    fake.registers[3038] = SLOT1_WORD1
    fake.registers[3039] = SLOT1_WORD2
    await _refresh(hass, entry)

    assert hass.states.get(_entity_id(hass, entry, "start_time")).state == "01:30:00"
    assert hass.states.get(_entity_id(hass, entry, "end_time")).state == "05:45:00"
    assert hass.states.get(_entity_id(hass, entry, "priority")).state == "Battery First"
    assert hass.states.get(_entity_id(hass, entry, "enabled")).state == "on"


async def test_changing_priority_rewrites_slot(hass, setup_storage_tou):
    entry, fake = setup_storage_tou
    fake.registers[3038] = SLOT1_WORD1
    fake.registers[3039] = SLOT1_WORD2
    await _refresh(hass, entry)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _entity_id(hass, entry, "priority"), "option": "Grid First"},
        blocking=True,
    )

    # priority bits (13-14) now 2, other fields preserved.
    new1 = fake.registers[3038]
    assert (new1 >> 13) & 0x3 == 2
    assert new1 & 0xFF == 30  # start minute preserved
    assert (new1 >> 15) & 0x1 == 1  # still enabled


async def test_setting_start_time_rewrites_slot(hass, setup_storage_tou):
    entry, fake = setup_storage_tou
    fake.registers[3038] = SLOT1_WORD1
    fake.registers[3039] = SLOT1_WORD2
    await _refresh(hass, entry)

    await hass.services.async_call(
        "time",
        "set_value",
        {"entity_id": _entity_id(hass, entry, "start_time"), "time": "06:15:00"},
        blocking=True,
    )

    new1 = fake.registers[3038]
    assert (new1 >> 8) & 0x1F == 6   # start hour
    assert new1 & 0xFF == 15         # start minute
