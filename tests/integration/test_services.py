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


async def test_set_time_slot_unknown_device_is_noop(hass, setup_storage):
    entry, fake = setup_storage
    before = list(fake.writes)
    await hass.services.async_call(
        "growatt_modbus",
        "set_time_slot",
        {
            "device_id": "deadbeef" * 4,  # 32 chars, not a registered device
            "slot": 1,
            "start_time": "01:00:00",
            "end_time": "02:00:00",
            "priority": "battery",
            "enabled": True,
        },
        blocking=True,
    )
    assert fake.writes == before  # nothing written for an unmatched target


async def test_setup_services_is_idempotent(hass, setup_storage):
    from custom_components.growatt_modbus.services import async_setup_services

    # Services were registered during setup; a second call returns early.
    async_setup_services(hass)
    assert hass.services.has_service("growatt_modbus", "run_optimization")


async def test_run_optimization_without_emhass_is_noop(hass, setup_storage):
    # No EMHASS configured -> optimizer is None -> handler logs and returns.
    await hass.services.async_call(
        "growatt_modbus", "run_optimization", {}, blocking=True
    )
