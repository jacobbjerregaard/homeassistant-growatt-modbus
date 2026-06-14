"""Integration test: the set_time_slot service writes the slot registers."""
from homeassistant.helpers import device_registry as dr


async def test_set_time_slot_service(hass, setup_storage):
    entry, fake = setup_storage

    device_registry = dr.async_get(hass)
    device = next(iter(dr.async_entries_for_config_entry(device_registry, entry.entry_id)))

    assert hass.services.has_service("growatt_modbus", "set_time_slot")

    await hass.services.async_call(
        "growatt_modbus",
        "set_time_slot",
        {
            "device_id": device.id,
            "slot": 1,
            "start_time": "01:30:00",
            "end_time": "05:45:00",
            "priority": "battery",
            "enabled": True,
        },
        blocking=True,
    )

    writes = dict(fake.writes)
    # slot 1 -> registers 3038/3039
    assert writes[3038] == 30 | (1 << 8) | (1 << 13) | (1 << 15)  # 41246
    assert writes[3039] == 45 | (5 << 8)  # 1325
