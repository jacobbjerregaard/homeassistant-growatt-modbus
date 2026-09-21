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


async def test_diagnostics_redacts_emhass_token_and_serials(hass, setup_storage):
    entry, _fake = setup_storage
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "emhass_url": "http://10.0.0.5:5000",
            "emhass_token": "s3cret-token",
        },
    )
    # The options change reloads the entry; use the reloaded runtime data.
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.main_coordinator
    coordinator.data = {
        "serial number": "INVERTER123",
        "battery_module_1_serial_number": "MODULE123",
        "soc": 50,
    }

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "s3cret-token" not in str(diag)
    assert "10.0.0.5" not in str(diag)
    data = diag["coordinators"]["main"]["data"]
    assert data["serial number"] == "**REDACTED**"
    assert data["battery_module_1_serial_number"] == "**REDACTED**"
    assert data["soc"] == 50
