"""Tests for ``process_registers`` value decoding in ``API/utils.py``."""
from growatt_api.device_type.base import GrowattDeviceRegisters, custom_function
from growatt_api.utils import process_registers


def _reg(name, register, value_type, **kw) -> GrowattDeviceRegisters:
    return GrowattDeviceRegisters(name=name, register=register, value_type=value_type, **kw)


def test_int_value_passthrough():
    registers = {10: _reg("count", 10, int)}
    assert process_registers(registers, {10: 42}) == {"count": 42}


def test_float_u16_is_scaled():
    registers = {10: _reg("voltage", 10, float, scale=10)}
    assert process_registers(registers, {10: 2353}) == {"voltage": 235.3}


def test_float_u32_combines_two_words():
    registers = {10: _reg("energy", 10, float, length=2, scale=10)}
    # (1 << 16) + 0 == 65536, /10 -> 6553.6
    assert process_registers(registers, {10: 1, 11: 0}) == {"energy": 6553.6}


def test_float_u32_skipped_when_second_word_missing():
    registers = {10: _reg("energy", 10, float, length=2, scale=10)}
    assert process_registers(registers, {10: 1}) == {}


def test_string_decoding():
    registers = {10: _reg("serial", 10, str, length=2)}
    # 0x4142 -> "AB", 0x4344 -> "CD"
    assert process_registers(registers, {10: 0x4142, 11: 0x4344}) == {"serial": "ABCD"}


def test_bool_decoding():
    registers = {10: _reg("enabled", 10, bool)}
    assert process_registers(registers, {10: 1}) == {"enabled": True}
    assert process_registers(registers, {10: 0}) == {"enabled": False}


def test_custom_function_single_word():
    registers = {10: _reg("doubled", 10, custom_function, function=lambda v: v * 2)}
    assert process_registers(registers, {10: 21}) == {"doubled": 42}


def test_custom_function_multi_word_receives_list():
    registers = {
        10: _reg("sum", 10, custom_function, length=3, function=lambda vals: sum(vals))
    }
    assert process_registers(registers, {10: 1, 11: 2, 12: 3}) == {"sum": 6}


def test_custom_function_without_function_is_skipped():
    registers = {10: _reg("noop", 10, custom_function, function=None)}
    assert process_registers(registers, {10: 5}) == {}


def test_unknown_register_address_is_ignored():
    registers = {10: _reg("voltage", 10, float, scale=10)}
    # address 99 has no register definition and must not appear in the result.
    assert process_registers(registers, {10: 100, 99: 1234}) == {"voltage": 10.0}
