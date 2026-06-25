"""Tests for the Peak Shaving holding registers (Protocol II V1.39, 3306-3310).

Pure-logic: pins the register addresses/types/scaling and the decode/encode
round trips. The control entities are covered in tests/integration/test_controls.
"""
import pytest

from growatt_api.utils import process_registers, to_register_value

pytest.importorskip("pymodbus", reason="storage register defs import the transport layer indirectly")

from growatt_api.const import DeviceTypes  # noqa: E402
from growatt_api.device import get_register_information  # noqa: E402


def _storage_holding_by_name():
    holding = get_register_information(DeviceTypes.STORAGE_120).holding
    return {register.name: register for register in holding.values()}


def test_peak_shaving_registers_present_with_correct_addresses():
    by_name = _storage_holding_by_name()
    assert by_name["peak_shaving_mode"].register == 3306
    assert by_name["peak_shaving_import_limit"].register == 3307
    assert by_name["peak_shaving_export_limit"].register == 3308
    assert by_name["reserved_soc_for_peak_shaving_enable"].register == 3309
    assert by_name["reserved_soc_for_peak_shaving"].register == 3310


def test_enable_and_soc_registers_are_plain_int():
    by_name = _storage_holding_by_name()
    for key in (
        "peak_shaving_mode",
        "reserved_soc_for_peak_shaving_enable",
        "reserved_soc_for_peak_shaving",
    ):
        assert by_name[key].value_type is int
        assert by_name[key].signed is False


def test_limit_registers_are_scaled_kilowatts():
    by_name = _storage_holding_by_name()
    imp = by_name["peak_shaving_import_limit"]
    exp = by_name["peak_shaving_export_limit"]
    # 0.1 kW resolution -> scale 10 (raw / 10 = kW).
    assert imp.value_type is float and imp.scale == 10
    assert imp.signed is False  # grid import cap is never negative
    assert exp.value_type is float and exp.scale == 10
    assert exp.signed is True  # export limit may be set negative (V1.39 / spec)


def test_import_limit_decode_encode_round_trip():
    reg = _storage_holding_by_name()["peak_shaving_import_limit"]
    # 5.0 kW on a 0.1 kW (scale 10) register -> raw 50.
    assert to_register_value(reg, 5.0) == 50
    assert process_registers({3307: reg}, {3307: 50}) == {"peak_shaving_import_limit": 5.0}


def test_export_limit_handles_negative_values():
    reg = _storage_holding_by_name()["peak_shaving_export_limit"]
    # -3.0 kW -> raw -30; the Modbus client encodes the two's complement on write.
    assert to_register_value(reg, -3.0) == -30
    # raw 0xFFE2 == -30 as signed 16-bit, / 10 -> -3.0 kW.
    assert process_registers({3308: reg}, {3308: 0xFFE2}) == {"peak_shaving_export_limit": -3.0}


def test_reserved_soc_round_trip():
    reg = _storage_holding_by_name()["reserved_soc_for_peak_shaving"]
    assert to_register_value(reg, 30) == 30
    assert process_registers({3310: reg}, {3310: 30}) == {"reserved_soc_for_peak_shaving": 30}
