"""Fixtures for the Home Assistant integration tests.

These run only when Home Assistant + pytest-homeassistant-custom-component are
installed (Python 3.13). They exercise the real config-entry setup, coordinators
and entity platforms against a faked Modbus transport - only the wire is mocked,
so the register map, decoding and write-encoding are all real.
"""
from collections import defaultdict
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)

from custom_components.growatt_modbus.const import (
    CONF_AC_PHASES,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DC_STRING,
    CONF_FIRMWARE,
    CONF_LAYER,
    CONF_PARITY,
    CONF_POWER_SCAN_ENABLED,
    CONF_POWER_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    DOMAIN,
)

TEST_SERIAL = "TESTSERIAL0001"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading the custom integration in every test."""
    yield


class FakeModbus:
    """Stand-in for GrowattModbusBase: canned reads, records writes."""

    def __init__(self):
        # defaultdict(int) -> unknown registers read as 0
        self.registers: dict[int, int] = defaultdict(int)
        self.writes: list[tuple[int, int]] = []

    async def connect(self):
        return None

    def connected(self):
        return True

    def close(self):
        return None

    async def read_holding_registers(self, start_index, length, unit):
        return {a: self.registers[a] for a in range(start_index, start_index + length)}

    async def read_input_registers(self, start_index, length, unit):
        return {a: self.registers[a] for a in range(start_index, start_index + length)}

    async def write_register(self, register, payload, unit):
        self.writes.append((register, payload))
        self.registers[register] = payload
        return None


def _entry_data() -> dict:
    return {
        CONF_LAYER: CONF_SERIAL,
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUDRATE: 9600,
        CONF_STOPBITS: 1,
        CONF_PARITY: "None",
        CONF_BYTESIZE: 8,
        CONF_ADDRESS: 1,
        CONF_TYPE: "storage_120",
        CONF_NAME: "Growatt Test",
        CONF_MODEL: "SPH",
        CONF_DC_STRING: 2,
        CONF_AC_PHASES: 1,
        CONF_SCAN_INTERVAL: 60,
        CONF_POWER_SCAN_ENABLED: False,
        CONF_POWER_SCAN_INTERVAL: 5,
        CONF_SERIAL_NUMBER: TEST_SERIAL,
        CONF_FIRMWARE: "TEST1.0",
    }


@pytest.fixture
def fake_modbus() -> FakeModbus:
    return FakeModbus()


@pytest.fixture
async def setup_storage(hass, fake_modbus):
    """Set up a storage device backed by the fake transport; yield (entry, fake).

    The GrowattSerial patch stays active for the whole test so a reload also
    uses the fake transport rather than touching a real serial port.
    """
    entry = MockConfigEntry(
        domain=DOMAIN, data=_entry_data(), unique_id=TEST_SERIAL, title="Growatt Test"
    )
    entry.add_to_hass(hass)

    patcher = patch(
        "custom_components.growatt_modbus.GrowattSerial", return_value=fake_modbus
    )
    patcher.start()
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, fake_modbus
    finally:
        patcher.stop()
