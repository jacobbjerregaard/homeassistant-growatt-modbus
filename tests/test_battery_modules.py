"""Tests for per-battery-module serial registers and count detection."""
import pytest

pytest.importorskip("pymodbus", reason="device.py imports the transport layer")

from growatt_api.const import DeviceTypes
from growatt_api.device import GrowattDevice, get_register_information
from growatt_api.device_type.storage_120 import (
    build_battery_module_registers,
    module_serial,
)


class _FakeModbus:
    def __init__(self, registers):
        self.registers = registers

    async def read_holding_registers(self, start_index, length, unit):
        return {a: self.registers.get(a, 0) for a in range(start_index, start_index + length)}


def test_module_serial_addresses():
    regs = {r.name: r.register for r in build_battery_module_registers(2)}
    assert regs["battery_module_1_serial_number"] == 5400
    assert regs["battery_module_2_serial_number"] == 5440  # +40 stride


def test_module_serial_decodes_and_strips_padding():
    # 0x4142="AB", 0x4344="CD", then null padding which is dropped.
    assert module_serial([0x4142, 0x4344, 0x0000, 0]) == "ABCD"


def test_modules_appended_to_storage_holding():
    info = get_register_information(DeviceTypes.STORAGE_120, battery_modules=3)
    names = {r.name for r in info.holding.values()}
    assert "battery_module_3_serial_number" in names
    assert "battery_module_4_serial_number" not in names


def test_no_modules_for_inverter_type():
    info = get_register_information(DeviceTypes.INVERTER_120, battery_modules=3)
    names = {r.name for r in info.holding.values()}
    assert not any(n.startswith("battery_module_") for n in names)


def test_zero_modules_adds_nothing():
    assert build_battery_module_registers(0) == ()


async def test_read_battery_module_count():
    device = GrowattDevice(_FakeModbus({185: 3}), DeviceTypes.STORAGE_120, 1)
    assert await device.read_battery_module_count() == 3


def test_set_battery_modules_rebuilds_register_map():
    device = GrowattDevice(_FakeModbus({}), DeviceTypes.STORAGE_120, 1)
    assert device.battery_modules == 0
    assert device.get_holding_register_by_name("battery_module_1_serial_number") is None

    device.set_battery_modules(2)
    assert device.battery_modules == 2
    assert device.get_holding_register_by_name("battery_module_2_serial_number") is not None
