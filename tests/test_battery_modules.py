"""Tests for per-battery-module serial registers and count detection."""
import pytest

pytest.importorskip("pymodbus", reason="device.py imports the transport layer")

from growatt_api.const import DeviceTypes
from growatt_api.device import GrowattDevice, get_register_information
from growatt_api.device_type.base import ATTR_BATTERY_CURRENT
from growatt_api.device_type.storage_120 import (
    bat_balance_state,
    bat_internal_state,
    bat_soc,
    bat_soh,
    bat_subcode,
    bat_sys_state,
    bdc_derating_mode,
    module_derating_mode,
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


def test_module_capacity_and_health_addresses():
    regs = {r.name: r for r in build_battery_module_input_registers(2)}
    # 5095 BatCellCapacity, 0.1 Ah.
    assert regs["battery_module_1_cell_capacity"].register == 5095
    assert regs["battery_module_1_cell_capacity"].scale == 10
    # Cumulative u32 capacity counters.
    charge_e = regs["battery_module_1_charge_energy_total"]
    assert charge_e.register == 5100 and charge_e.length == 2 and charge_e.scale == 10
    dis_cap = regs["battery_module_1_discharge_capacity_total"]
    assert dis_cap.register == 5102 and dis_cap.length == 2 and dis_cap.scale == 100
    chg_cap = regs["battery_module_1_charge_capacity_total"]
    assert chg_cap.register == 5104 and chg_cap.length == 2 and chg_cap.scale == 100
    assert regs["battery_module_1_cell_capacity_min"].register == 5106
    assert regs["battery_module_1_ah_integral"].register == 5107
    assert regs["battery_module_1_cycle_count"].register == 5108
    assert regs["battery_module_1_fault_code"].register == 5097
    assert regs["battery_module_1_warning_code"].register == 5098
    # +40 stride for module 2.
    assert regs["battery_module_2_cell_capacity"].register == 5135


def test_bat_balance_state_splits_state_and_hours():
    # Bit15-8 state (2 = Top requested), Bit7-0 balance time = 12 h.
    decoded = bat_balance_state((2 << 8) | 12)
    assert decoded == {"state": "Top requested", "time_hours": 12}
    assert "Unknown" in bat_balance_state(99 << 8)["state"]


def test_bat_subcode_splits_flags():
    # charge+discharge enabled, warning subcode 3, fault subcode 5.
    decoded = bat_subcode(0b1 | 0b10 | (3 << 8) | (5 << 12))
    assert decoded == {
        "charge_enabled": 1,
        "discharge_enabled": 1,
        "warning_subcode": 3,
        "fault_subcode": 5,
    }


def test_bat_internal_state_splits_bytes():
    decoded = bat_internal_state((0x12 << 8) | 0x34)
    assert decoded == {"short_circuit": 0x12, "sox_correction": 0x34}


def test_multi_value_registers_advertise_sub_names():
    regs = {r.name: r for r in build_battery_module_input_registers(1)}
    balance = regs["battery_module_1_balance"]
    assert balance.value_names == (
        "battery_module_1_balance_state",
        "battery_module_1_balance_time_hours",
    )
    # Single-value registers do not advertise extra names.
    assert regs["battery_module_1_soc"].value_names == ()


def test_module_sub_names_visible_to_device():
    info = get_register_information(DeviceTypes.STORAGE_120, battery_modules=1)
    names = {r.name for r in info.input.values()}
    sub_names = set()
    for r in info.input.values():
        sub_names.update(r.value_names)
    # The register is keyed under its own name, but exposes the sub-values.
    assert "battery_module_1_balance" in names
    assert "battery_module_1_balance_state" in sub_names
    assert "battery_module_1_flags_fault_subcode" in sub_names


def test_module_derating_mode_text():
    assert module_derating_mode(0) == "No derating"
    assert module_derating_mode(1) == "Fault"
    assert module_derating_mode(19) == "Bus voltage too high"
    assert module_derating_mode(25) == "Reserved"
    assert "Unknown" in module_derating_mode(7)


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


def test_decode_ascii_preserves_meaningful_whitespace():
    # A 5-char firmware whose last char is a space: registers 12-14 = "ZBDB "
    # plus NUL padding. Only the NUL is dropped; the trailing space stays.
    assert decode_ascii([0x5A42, 0x4442, 0x2000]) == "ZBDB "
    # NUL-only padding is still removed entirely.
    assert decode_ascii([0x4142, 0x4344, 0x0000]) == "ABCD"


def test_battery_current_is_signed():
    info = get_register_information(DeviceTypes.STORAGE_120)
    current = next(
        r for r in info.input.values() if r.name == ATTR_BATTERY_CURRENT
    )
    assert current.register == 3170
    assert current.signed is True


def test_bdc_derating_mode_full_table():
    assert bdc_derating_mode(0) == "Normal, unrestricted"
    assert bdc_derating_mode(2) == "System warning"
    assert bdc_derating_mode(9) == "Full charged (charge)"
    assert bdc_derating_mode(17) == "Maximum battery current limit (discharge)"
    assert bdc_derating_mode(30) == "Reserved (discharge)"
    assert "Unknown" in bdc_derating_mode(99)


async def test_read_battery_module_count():
    device = GrowattDevice(_FakeModbus({185: 3}), DeviceTypes.STORAGE_120, 1)
    assert await device.read_battery_module_count() == 3


async def test_read_battery_module_serials():
    # Module 1 serial "MOD1" at holding 5400 (2 ASCII chars per register);
    # module 2 has no serial and must be omitted from the mapping.
    device = GrowattDevice(
        _FakeModbus({5400: 0x4D4F, 5401: 0x4431}), DeviceTypes.STORAGE_120, 1
    )
    device.set_battery_modules(2)
    serials = await device.read_battery_module_serials()
    assert serials == {1: "MOD1"}


def test_set_battery_modules_rebuilds_register_map():
    device = GrowattDevice(_FakeModbus({}), DeviceTypes.STORAGE_120, 1)
    assert device.battery_modules == 0
    assert device.get_holding_register_by_name("battery_module_1_serial_number") is None

    device.set_battery_modules(2)
    assert device.battery_modules == 2
    assert device.get_holding_register_by_name("battery_module_2_serial_number") is not None
