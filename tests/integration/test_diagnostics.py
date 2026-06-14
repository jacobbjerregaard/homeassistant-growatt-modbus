"""Integration test: config-entry diagnostics redact secrets and dump data."""
from custom_components.growatt_modbus.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_and_dumps(hass, setup_storage):
    entry, fake = setup_storage
    fake.registers[3171] = 73  # SOC
    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    diag = await async_get_config_entry_diagnostics(hass, entry)

    # Serial number is redacted.
    assert diag["entry"]["data"]["serial_number"] == "**REDACTED**"
    # Non-secret config is preserved.
    assert diag["entry"]["data"]["type"] == "storage_120"
    # Coordinator data is included; the power coordinator is absent here.
    main = diag["coordinators"]["main"]
    assert main["last_update_success"] is True
    assert main["data"]["soc"] == 73
    assert diag["coordinators"]["power"] is None
