"""Integration test: the sync-time button writes the device clock."""
from homeassistant.helpers import entity_registry as er


async def test_sync_time_button_writes_clock(hass, setup_storage):
    entry, fake = setup_storage
    registry = er.async_get(hass)
    button_id = next(
        e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == "button"
    )

    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )

    assert len(fake.time_writes) == 1
    # Last element of the recorded write is the Modbus unit (CONF_ADDRESS == 1).
    assert fake.time_writes[0][-1] == 1
