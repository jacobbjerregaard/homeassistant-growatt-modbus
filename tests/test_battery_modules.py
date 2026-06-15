"""Tests for per-battery-module serial registers and count detection."""
import pytest

pytest.importorskip("pymodbus", reason="device.py imports the transport layer")

from growatt_api.const import DeviceTypes
from growatt_api.device import GrowattDevice, get_register_information
from growatt_api.device_type.storage_120 import (
    bat_soc,
    bat_soh,
    bat_sys_state,
    build_battery_module_registers,
    build_battery_module_input_registers,
    decode_ascii,
    firmware_code_version,
)


class _FakeModbus:
    def __init__(self, registers):
        self.registers = registers

    async def read_holding_registers(self, start_index, length, unit):
        return {a: self.registers.get(a, 0) for a in range(start_index, start_index + length)}


def test_module_register_addresses():
    regs = {r.name: r.register for r in build_battery_module_registers(2)}
    assert regs["battery_module_1_serial_number"] == 5400
    assert regs["battery_module_1_dsp_firmware"] == 5408
    assert regs["battery_module_1_mcu_firmware"] == 5411
    assert regs["battery_module_2_serial_number"] == 5440  # +40 stride


def test_module_telemetry_addresses():
    regs = {r.name: r.register for r in build_battery_module_input_registers(2)}
    assert regs["battery_module_1_soc"] == 5081
    assert regs["battery_module_1_voltage"] == 5083
    assert regs["battery_module_1_temperature_max"] == 5090
    assert regs["battery_module_2_soc"] == 5121  # +40 stride
    current = next(
        r for r in build_battery_module_input_registers(1)
        if r.name == "battery_module_1_current"
    )
    assert current.signed is True  # charge/discharge


def test_module_new_telemetry_addresses():
    regs = {r.name: r for r in build_battery_module_input_registers(2)}
    assert regs["battery_module_1_system_state"].register == 5080
    # BatTotalDischargeElectric is a u32 (5086-5087), 0.1 kWh.
    discharge = regs["battery_module_1_discharge_energy_total"]
    assert discharge.register == 5086
    assert discharge.length == 2
    assert discharge.scale == 10
    # Cell voltages are 0.001 V (scale 1000).
    assert regs["battery_module_1_cell_voltage_max"].register == 5088
    assert regs["battery_module_1_cell_voltage_max"].scale == 1000
    assert regs["battery_module_2_system_state"].register == 5120  # +40 stride


def test_bat_sys_state_text():
    assert bat_sys_state(2) == "Charging"
    assert bat_sys_state(3) == "Discharging"
    assert bat_sys_state(99).startswith("Unknown")


def test_bat_soc_decodes_low_byte():
    # 0x5F5F (24415) is SOC replicated in both bytes -> 95%.
    assert bat_soc(0x5F5F) == 95
    assert bat_soc(95) == 95


def test_bat_soh_masks_scrap_flag():
    # Bit7 is a scrap flag; SOH is the low 7 bits.
    assert bat_soh(95) == 95
    assert bat_soh(0x80 | 95) == 95


def test_decode_ascii_strips_padding():
    # 0x4142="AB", 0x4344="CD", then null padding which is dropped.
    assert decode_ascii([0x4142, 0x4344, 0x0000, 0]) == "ABCD"


def test_firmware_registers_present_for_storage():
    info = get_register_information(DeviceTypes.STORAGE_120)
    by_name = {r.name: r.register for r in info.holding.values()}
    assert by_name["control_firmware"] == 12
    assert by_name["bdc_firmware"] == 3099  # code (3099-3100) + version (3101)
    assert by_name["bms_firmware"] == 3105


def test_firmware_code_version_combines_code_and_version():
    # "ZE","BA" ASCII code + version word 10.
    assert firmware_code_version([0x5A45, 0x4241, 10]) == "ZEBA-10"
    # No code -> just the version number.
    assert firmware_code_version([0, 5]) == "5"


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
