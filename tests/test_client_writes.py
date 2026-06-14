"""Regression tests for the Modbus write path.

The integration tests use a fake transport that bypasses pymodbus, so they
missed that write_register called convert_to_registers with renamed kwargs and
passed a list + positional unit. These tests pin the call we make and check it
against the real pymodbus write_register signature.
"""
import inspect
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("pymodbus", reason="needs the real pymodbus client signature")

from pymodbus.client import AsyncModbusTcpClient

from growatt_api.client import GrowattModbusBase


def _base() -> GrowattModbusBase:
    base = GrowattModbusBase()  # initialises the asyncio lock
    base.client = AsyncMock()
    return base


async def test_write_register_calls_pymodbus_with_device_id():
    base = _base()
    await base.write_register(3067, 80, 7)
    base.client.write_register.assert_awaited_once_with(3067, 80, device_id=7)


async def test_write_register_encodes_signed_as_twos_complement():
    base = _base()
    await base.write_register(100, -10, 1)
    base.client.write_register.assert_awaited_once_with(100, 0xFFF6, device_id=1)


async def test_write_register_value_carries_high_bit():
    base = _base()
    # Time-slot word with the enable bit (15) set: 41246 > int16 max.
    await base.write_register_value(3038, 41246, 1)
    base.client.write_register.assert_awaited_once_with(3038, 41246, device_id=1)


def test_call_matches_installed_pymodbus_signature():
    # The (address, value, device_id=...) call we make must bind to the real
    # pymodbus write_register signature - this would have caught the original
    # wordorder/byteorder/positional-unit breakage.
    sig = inspect.signature(AsyncModbusTcpClient.write_register)
    sig.bind(object(), 3067, 80, device_id=7)  # self, address, value, device_id
