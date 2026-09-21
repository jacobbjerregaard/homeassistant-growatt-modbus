"""The hybrid must not expose input 112-115 as AC charge energy sensors.

Reported: sensor.inverter_battery_ac_charge_energy_today went 1.7 -> 1.6 kWh
and Home Assistant logged "state is not strictly increasing". On the reporter's
MOD TL3-XH those registers hold the real power percentage (113) and the start
delay (114), not AC charge energy - the "energy" moved with the output power.
"""

from homeassistant.helpers import entity_registry as er


async def test_hybrid_has_no_ac_charge_energy_sensors(hass, setup_hybrid):
    entry, _fake = setup_hybrid
    registry = er.async_get(hass)

    unique_ids = [
        e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    ]

    assert unique_ids, "the hybrid set up no entities at all"
    assert not [uid for uid in unique_ids if "ac_charge_energy" in uid.lower()]
