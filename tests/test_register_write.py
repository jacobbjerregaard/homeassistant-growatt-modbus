"""Tests for write-side register encoding (to_register_value) and a
read/write round trip over the real storage register definitions."""
import pytest

from growatt_api.device_type.base import GrowattDeviceRegisters
from growatt_api.utils import process_registers, to_register_value


def _reg(value_type, scale=10, signed=False):
    return GrowattDeviceRegisters(
        name="x", register=100, value_type=value_type, scale=scale, signed=signed
    )


def test_int_register_writes_value_unchanged():
    assert to_register_value(_reg(int), 57) == 57


def test_float_register_applies_inverse_scale():
    # 23.5 V on a 0.1V (scale 10) register -> raw 235
    assert to_register_value(_reg(float, scale=10), 23.5) == 235
    # 52.0 V on a 0.01V (scale 100) register -> raw 5200
    assert to_register_value(_reg(float, scale=100), 52.0) == 5200


def test_float_rounds_to_nearest_int():
    assert to_register_value(_reg(float, scale=10), 23.54) == 235
    assert to_register_value(_reg(float, scale=10), 23.55) == 236


def test_signed_negative_value_passed_through():
    # The Modbus client encodes the two's complement on write.
    assert to_register_value(_reg(float, scale=10, signed=True), -1.0) == -10


def test_read_write_round_trip_int():
    reg = _reg(int)
    raw = to_register_value(reg, 80)
    decoded = process_registers({100: reg}, {100: raw})
    assert decoded == {"x": 80}


def test_read_write_round_trip_float():
    reg = _reg(float, scale=100)
    raw = to_register_value(reg, 53.2)
    decoded = process_registers({100: reg}, {100: raw})
    assert decoded["x"] == pytest.approx(53.2)


pytest.importorskip("pymodbus", reason="storage register defs import the transport layer indirectly")


def test_new_v139_command_registers_present():
    from growatt_api.device import get_register_information
    from growatt_api.const import DeviceTypes

    holding = get_register_information(DeviceTypes.STORAGE_120).holding
    by_name = {r.name: r.register for r in holding.values()}
    # A representative sample of the new V1.39 control registers.
    assert by_name["grid_first_stop_soc"] == 3037
    assert by_name["battery_type"] == 3070
    assert by_name["generator_force"] == 3074
    assert by_name["ups_output_voltage"] == 3080
    assert by_name["pre_pto_enabled"] == 3072


def test_new_v139_telemetry_registers_present():
    from growatt_api.device import get_register_information
    from growatt_api.const import DeviceTypes

    inp = get_register_information(DeviceTypes.STORAGE_120).input
    by_name = {r.name: r.register for r in inp.values()}
    assert by_name["battery_voltage"] == 3169
    assert by_name["battery_current"] == 3170
    assert by_name["system_energy_total"] == 3137
    assert by_name["bms_max_soc"] == 3196
