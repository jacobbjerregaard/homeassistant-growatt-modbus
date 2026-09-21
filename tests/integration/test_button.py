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


async def test_sync_time_writes_home_assistant_local_time(hass, setup_storage, freezer):
    """The inverter runs its TOU slots on local wall time with no time zone.

    The clock must be set from Home Assistant's configured zone, not the
    host/container zone (often UTC), or every slot is shifted by the offset.
    """
    entry, fake = setup_storage
    await hass.config.async_set_time_zone("Europe/Copenhagen")
    freezer.move_to("2026-09-20T06:48:51+00:00")  # 08:48:51 in Copenhagen (CEST)
    registry = er.async_get(hass)
    button_id = next(
        e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == "button"
    )

    await hass.services.async_call(
        "button", "press", {"entity_id": button_id}, blocking=True
    )

    assert fake.time_writes[-1][:6] == (2026, 9, 20, 8, 48, 51)
