"""Repair of entries that were set up with an empty inverter serial.

The config flow used to read the serial from holding 23, which is empty on the
storage/hybrid types (their serial is at holding 3001), so those entries got
"" as serial and unique_id, and every entity/device identity was built on it.
"""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.growatt_modbus.api.device_type.base import GrowattDeviceInfo
from custom_components.growatt_modbus.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    DOMAIN,
)

SERIAL = "HHM0DAA03B"
MODULE_SERIAL = "0FDP78ED355T007D"
_SERIAL_FORM = {
    CONF_SERIAL_PORT: "/dev/ttyUSB0",
    CONF_BAUDRATE: 9600,
    CONF_STOPBITS: 1,
    CONF_PARITY: "None",
    CONF_BYTESIZE: 8,
    CONF_ADDRESS: 1,
}


def _write_serial(fake, serial: str = SERIAL) -> None:
    """Holding 3001+ holds the serial, two ASCII characters per register."""
    padded = serial.ljust(30, "\x00")
    for index in range(15):
        high, low = padded[2 * index], padded[2 * index + 1]
        fake.registers[3001 + index] = (ord(high) << 8) | ord(low)


def _empty_serial_entry(hass, entry_data, **data_overrides) -> MockConfigEntry:
    """An entry as the old config flow created it for a hybrid: serial ""."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**entry_data(0), CONF_SERIAL_NUMBER: "", **data_overrides},
        unique_id="",
        title="Growatt SPH",
    )
    entry.add_to_hass(hass)
    return entry


def _register_old_identities(hass, entry):
    """Registry state of an install that ran with the empty serial."""
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    inverter = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "")}, name="Inverter"
    )
    module = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"_battery_module_{MODULE_SERIAL}")},
        name=f"Module {MODULE_SERIAL}",
        via_device_id=inverter.id,
    )
    soc = entities.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DOMAIN}__soc",
        config_entry=entry,
        device_id=inverter.id,
        suggested_object_id="inverter_soc",
    )
    return inverter, module, soc


async def _setup(hass, entry, fake):
    with patch("custom_components.growatt_modbus.GrowattSerial", return_value=fake):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_empty_serial_entry_is_repaired(hass, fake_modbus, entry_data):
    _write_serial(fake_modbus)
    entry = _empty_serial_entry(hass, entry_data)
    inverter, module, soc = _register_old_identities(hass, entry)
    fake_modbus.registers[3171] = 73  # SOC

    await _setup(hass, entry, fake_modbus)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == SERIAL
    assert entry.data[CONF_SERIAL_NUMBER] == SERIAL

    # Same entity (entity_id, and so its history), repaired unique_id, and it
    # is the one the platform updates - not a new duplicate.
    entities = er.async_get(hass)
    migrated = entities.async_get(soc.entity_id)
    assert migrated.unique_id == f"{DOMAIN}_{SERIAL}_soc"
    assert entities.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}__soc") is None
    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(soc.entity_id).state == "73"

    devices = dr.async_get(hass)
    assert devices.async_get(inverter.id).identifiers == {(DOMAIN, SERIAL)}
    assert devices.async_get(module.id).identifiers == {
        (DOMAIN, f"{SERIAL}_battery_module_{MODULE_SERIAL}")
    }
    # No duplicate inverter device was created next to the repaired one.
    assert [
        d.id
        for d in dr.async_entries_for_config_entry(devices, entry.entry_id)
        if (DOMAIN, SERIAL) in d.identifiers
    ] == [inverter.id]


async def test_repair_is_retried_when_the_serial_cannot_be_read(
    hass, fake_modbus, entry_data
):
    # Serial registers read as zeros: nothing to repair with yet.
    entry = _empty_serial_entry(hass, entry_data)
    _inverter, _module, soc = _register_old_identities(hass, entry)

    await _setup(hass, entry, fake_modbus)

    # The entry still loads, and is left untouched for a later attempt.
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == ""
    assert er.async_get(hass).async_get(soc.entity_id).unique_id == f"{DOMAIN}__soc"


async def test_repair_skipped_when_another_entry_has_the_serial(
    hass, fake_modbus, entry_data
):
    MockConfigEntry(
        domain=DOMAIN, data=entry_data(0), unique_id=SERIAL, title="Other"
    ).add_to_hass(hass)
    _write_serial(fake_modbus)
    entry = _empty_serial_entry(hass, entry_data)

    await _setup(hass, entry, fake_modbus)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == ""


async def test_interrupted_repair_is_completed(hass, fake_modbus, entry_data):
    """The entry already has its serial, but some identities still use ""."""
    entry = _empty_serial_entry(hass, entry_data, **{CONF_SERIAL_NUMBER: SERIAL})
    inverter, _module, soc = _register_old_identities(hass, entry)

    await _setup(hass, entry, fake_modbus)

    assert (
        er.async_get(hass).async_get(soc.entity_id).unique_id
        == f"{DOMAIN}_{SERIAL}_soc"
    )
    assert dr.async_get(hass).async_get(inverter.id).identifiers == {(DOMAIN, SERIAL)}


async def test_reconfigure_adopts_the_serial_of_an_empty_serial_entry(hass, entry_data):
    """Reconfigure cannot match "" against the device, so it adopts the serial."""
    entry = _empty_serial_entry(hass, entry_data)
    info = GrowattDeviceInfo(
        serial_number=SERIAL,
        model="MOD",
        firmware="DN1.0",
        mppt_trackers=2,
        grid_phases=3,
        modbus_version=3.08,
    )

    class _Server:
        async def connect(self):
            return True

        def connected(self):
            return True

        def close(self):
            return None

    result = await entry.start_reconfigure_flow(hass)
    with (
        patch(
            "custom_components.growatt_modbus.config_flow.GrowattSerial",
            return_value=_Server(),
        ),
        patch(
            "custom_components.growatt_modbus.config_flow.get_device_info",
            AsyncMock(return_value=info),
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_schedule_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _SERIAL_FORM,
        )

    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == SERIAL
    assert entry.data[CONF_SERIAL_NUMBER] == SERIAL

    # A different device is still refused once the entry has its serial.
    other = replace(info, serial_number="SOMEOTHER")
    result = await entry.start_reconfigure_flow(hass)
    with (
        patch(
            "custom_components.growatt_modbus.config_flow.GrowattSerial",
            return_value=_Server(),
        ),
        patch(
            "custom_components.growatt_modbus.config_flow.get_device_info",
            AsyncMock(return_value=other),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _SERIAL_FORM,
        )
    assert result["reason"] == "wrong_device"
