"""Integration tests: the writable control entities write the right registers."""
from homeassistant.helpers import entity_registry as er


def _entity_id(hass, entry, domain: str, unique_suffix: str) -> str:
    # ac_charge_enabled exists as both a sensor and a switch (same unique_id
    # suffix), so the platform domain must be part of the lookup.
    registry = er.async_get(hass)
    for e in er.async_entries_for_config_entry(registry, entry.entry_id):
        if e.domain == domain and e.unique_id.endswith(unique_suffix):
            return e.entity_id
    raise AssertionError(f"no {domain} entity ending {unique_suffix!r}")


async def test_export_limit_mode_select_writes(hass, setup_storage):
    entry, fake = setup_storage
    eid = _entity_id(hass, entry, "select", "_export_limit_mode")  # holding 122
    await hass.services.async_call(
        "select", "select_option", {"entity_id": eid, "option": "Enable (CT)"}, blocking=True
    )
    assert (122, 3) in fake.writes


async def test_export_limit_rate_number_writes_signed(hass, setup_storage):
    entry, fake = setup_storage
    eid = _entity_id(hass, entry, "number", "_export_limit_rate")  # holding 123, 0.1%
    await hass.services.async_call(
        "number", "set_value", {"entity_id": eid, "value": -50.0}, blocking=True
    )
    # -50.0% on a 0.1% (scale 10) register -> raw -500 (two's complement applied
    # by the real client; the fake records the signed value).
    assert (123, -500) in fake.writes


async def test_number_writes_register(hass, setup_storage):
    entry, fake = setup_storage
    eid = _entity_id(hass, entry, "number", "_grid_first_stop_soc")  # holding 3037, int %
    await hass.services.async_call(
        "number", "set_value", {"entity_id": eid, "value": 55}, blocking=True
    )
    assert (3037, 55) in fake.writes


async def test_select_writes_mapped_value(hass, setup_storage):
    entry, fake = setup_storage
    eid = _entity_id(hass, entry, "select", "_battery_type")  # holding 3070
    await hass.services.async_call(
        "select", "select_option", {"entity_id": eid, "option": "Lead-acid"}, blocking=True
    )
    assert (3070, 1) in fake.writes  # Lead-acid -> 1


async def test_switch_writes_one_and_zero(hass, setup_storage):
    entry, fake = setup_storage
    eid = _entity_id(hass, entry, "switch", "_ac_charge_enabled")  # holding 3049
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": eid}, blocking=True
    )
    assert (3049, 1) in fake.writes
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": eid}, blocking=True
    )
    assert (3049, 0) in fake.writes


async def test_number_reflects_register_after_refresh(hass, setup_storage):
    entry, fake = setup_storage
    eid = _entity_id(hass, entry, "number", "_battery_charge_stop_soc")  # holding 3048
    fake.registers[3048] = 90
    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert float(hass.states.get(eid).state) == 90.0
