"""total_increasing counters must not dip: Home Assistant double-counts it.

Reported: sensor.inverter_battery_ac_charge_energy_today went 1.7 -> 1.6 kWh,
and Home Assistant logged "state is not strictly increasing". A drop that small
is not treated as a reset, so the 0.1 kWh is counted again when the counter
climbs back.
"""

from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus.const import DOMAIN

AC_CHARGE_TODAY = "battery_ac_charge_energy_today"
# Input registers 112/113: 32-bit, 0.1 kWh.
HIGH, LOW = 112, 113


def _entity_id(hass, entry) -> str:
    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{entry.unique_id}_{AC_CHARGE_TODAY}"
    return next(
        e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id == uid
    )


async def _poll(hass, entry, fake, tenths: int) -> str:
    fake.registers[HIGH], fake.registers[LOW] = divmod(tenths, 0x10000)
    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()
    return hass.states.get(_entity_id(hass, entry)).state


async def test_one_step_dip_keeps_the_previous_value(hass, setup_hybrid):
    entry, fake = setup_hybrid

    assert await _poll(hass, entry, fake, 17) == "1.7"
    # The reported glitch: one 0.1 kWh step down.
    assert await _poll(hass, entry, fake, 16) == "1.7"
    # The counter recovers and carries on from the real value.
    assert await _poll(hass, entry, fake, 18) == "1.8"


async def test_reset_to_zero_is_passed_through(hass, setup_hybrid):
    entry, fake = setup_hybrid

    assert await _poll(hass, entry, fake, 42) == "4.2"
    # The inverter's own midnight reset must still come through.
    assert await _poll(hass, entry, fake, 0) == "0.0"
    assert await _poll(hass, entry, fake, 1) == "0.1"
