"""Unit tests for GrowattDevice (API/device.py) error/edge branches."""
import asyncio

import pytest

pytest.importorskip("pymodbus", reason="device.py imports the transport layer")

from growatt_api.const import DeviceTypes
from growatt_api.device import GrowattDevice
from growatt_api.device_type.base import ATTR_STATUS, GrowattDeviceRegisters


class _FakeModbus:
    def __init__(self, holding=None, raise_on_read=False):
        self.holding = holding or {}
        self.raise_on_read = raise_on_read

    async def read_holding_registers(self, start_index, length, unit):
        if self.raise_on_read:
            raise ConnectionError("modbus down")
        return {a: self.holding.get(a, 0) for a in range(start_index, start_index + length)}

    async def read_input_registers(self, start_index, length, unit):
        if self.raise_on_read:
            raise ConnectionError("modbus down")
        return {a: 0 for a in range(start_index, start_index + length)}


def _device(modbus, battery_modules=1):
    return GrowattDevice(modbus, DeviceTypes.STORAGE_120, 1, battery_modules=battery_modules)


def test_read_battery_module_count_reads_register():
    dev = _device(_FakeModbus(holding={185: 3}))
    assert asyncio.run(dev.read_battery_module_count()) == 3


def test_read_battery_module_count_returns_zero_on_error():
    dev = _device(_FakeModbus(raise_on_read=True))
    assert asyncio.run(dev.read_battery_module_count()) == 0


def test_read_battery_module_serials_empty_when_no_modules():
    dev = _device(_FakeModbus(), battery_modules=0)
    assert asyncio.run(dev.read_battery_module_serials()) == {}


def test_read_battery_module_serials_returns_empty_on_error():
    dev = _device(_FakeModbus(raise_on_read=True), battery_modules=1)
    assert asyncio.run(dev.read_battery_module_serials()) == {}


def test_get_keys_by_name_expands_status():
    dev = _device(_FakeModbus())
    # Requesting ATTR_STATUS takes the expansion branch (adds the packed
    # status/fault/derating sub-registers) without error.
    keys = dev.get_keys_by_name([ATTR_STATUS])
    assert keys.holding is not None and keys.input is not None


def test_register_lookup_by_name():
    dev = _device(_FakeModbus())
    # A known holding register resolves; an unknown name returns None.
    some_name = next(iter(dev.device_registers.holding.values())).name
    assert dev.get_holding_register_by_name(some_name) is not None
    assert dev.get_holding_register_by_name("nope-not-real") is None
    assert dev.get_input_register_by_name("nope-not-real") is None


def test_read_holding_register_decodes_values():
    dev = _device(_FakeModbus(holding={999: 42}))
    reg = (GrowattDeviceRegisters(name="probe", register=999, value_type=int),)
    result = asyncio.run(dev.read_holding_register(reg))
    assert result["probe"] == 42
