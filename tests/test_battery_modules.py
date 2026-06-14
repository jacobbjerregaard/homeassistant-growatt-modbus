"""Tests for per-battery-module register generation."""
import pytest

pytest.importorskip("pymodbus", reason="device.py imports the transport layer")

from growatt_api.const import DeviceTypes
from growatt_api.device import get_register_information
from growatt_api.device_type.storage_120 import build_battery_module_registers


def test_module_register_addresses():
    regs = {r.name: r.register for r in build_battery_module_registers(2)}
    # Module 1 block data starts at 4008 (4000 + 8 serial regs); fields mirror
    # the aggregate block at 3165, so address = 4008 + (aggregate - 3165).
    assert regs["battery_module_1_voltage"] == 4012  # 3169 -> +4
    assert regs["battery_module_1_soc"] == 4014      # 3171 -> +6
    assert regs["battery_module_1_soh"] == 4065      # 3222 -> +57
    # Module 2 is one 108-register block further along.
    assert regs["battery_module_2_voltage"] == 4120
    assert regs["battery_module_2_soc"] == 4122


def test_modules_appended_to_storage_input():
    info = get_register_information(DeviceTypes.STORAGE_120, battery_modules=3)
    names = {r.name for r in info.input.values()}
    assert "battery_module_3_soc" in names
    assert "battery_module_4_soc" not in names


def test_no_modules_for_inverter_type():
    info = get_register_information(DeviceTypes.INVERTER_120, battery_modules=3)
    names = {r.name for r in info.input.values()}
    assert not any(n.startswith("battery_module_") for n in names)


def test_zero_modules_adds_nothing():
    assert build_battery_module_registers(0) == ()
