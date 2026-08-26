"""Tests for ``process_registers`` value decoding in ``API/utils.py``."""

from growatt_api.device_type.base import GrowattDeviceRegisters, custom_function
from growatt_api.utils import process_registers, to_signed


def _reg(name, register, value_type, **kw) -> GrowattDeviceRegisters:
    return GrowattDeviceRegisters(
        name=name, register=register, value_type=value_type, **kw
    )


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
    registers = {10: _reg("sum", 10, custom_function, length=3, function=sum)}
    assert process_registers(registers, {10: 1, 11: 2, 12: 3}) == {"sum": 6}


def test_custom_function_without_function_is_skipped():
    registers = {10: _reg("noop", 10, custom_function, function=None)}
    assert process_registers(registers, {10: 5}) == {}


def test_custom_function_dict_expands_into_suffixed_keys():
    # A packed bitfield can decode one register into several named values.
    registers = {
        10: _reg(
            "module_1_flags",
            10,
            custom_function,
            function=lambda v: {"low": v & 0xFF, "high": v >> 8},
        )
    }
    assert process_registers(registers, {10: 0x1234}) == {
        "module_1_flags_low": 0x34,
        "module_1_flags_high": 0x12,
    }


def test_unknown_register_address_is_ignored():
    registers = {10: _reg("voltage", 10, float, scale=10)}
    # address 99 has no register definition and must not appear in the result.
    assert process_registers(registers, {10: 100, 99: 1234}) == {"voltage": 10.0}


# --- signed decoding -----------------------------------------------------


def test_to_signed_helper():
    assert to_signed(0x0000, 16) == 0
    assert to_signed(0x7FFF, 16) == 32767
    assert to_signed(0xFFFF, 16) == -1
    assert to_signed(0xFFF6, 16) == -10
    assert to_signed(0x8000, 16) == -32768
    assert to_signed(0xFFFFFFFF, 32) == -1


def test_signed_float_u16_negative_temperature():
    # 0xFFF6 == 65526 unsigned; as a signed 16-bit it is -10, /10 -> -1.0 C
    registers = {10: _reg("temperature", 10, float, scale=10, signed=True)}
    assert process_registers(registers, {10: 0xFFF6}) == {"temperature": -1.0}


def test_unsigned_float_u16_would_misread_negative():
    # Same raw value without the signed flag decodes as a nonsensical 6552.6 —
    # this pins the old (incorrect) behaviour the signed flag exists to fix.
    registers = {10: _reg("temperature", 10, float, scale=10)}
    assert process_registers(registers, {10: 0xFFF6}) == {"temperature": 6552.6}


def test_signed_float_u32_negative_reactive_power():
    # -100 as a signed 32-bit value, /10 -> -10.0
    raw = (-100) & 0xFFFFFFFF
    registers = {10: _reg("reactive", 10, float, length=2, scale=10, signed=True)}
    assert process_registers(registers, {10: raw >> 16, 11: raw & 0xFFFF}) == {
        "reactive": -10.0
    }


def test_signed_int_register():
    registers = {10: _reg("offset", 10, int, signed=True)}
    assert process_registers(registers, {10: 0xFFFF}) == {"offset": -1}


def test_signed_positive_values_unchanged():
    # The signed flag must not alter values that are within the positive range.
    registers = {10: _reg("temperature", 10, float, scale=10, signed=True)}
    assert process_registers(registers, {10: 235}) == {"temperature": 23.5}


def test_firmware_register_reads_only_three_words():
    from growatt_api.device_type.base import FIRMWARE_REGISTER

    assert FIRMWARE_REGISTER.length == 3
    registers = {FIRMWARE_REGISTER.register: FIRMWARE_REGISTER}
    # 9-11 = "ABCDEF"; register 12 is the separate control firmware and must
    # not bleed into the firmware string.
    values = {9: 0x4142, 10: 0x4344, 11: 0x4546, 12: 0x5858}
    assert process_registers(registers, values) == {"firmware": "ABCDEF"}


def test_negative_output_power_decodes_as_negative():
    """Regression: register 0xFFFFFF1B is -22.9 W, not 429,496,706.7 W.

    Captured from a real inverter at 05:28 on a summer morning, sitting just
    below zero output while drawing standby power. output_power was declared
    unsigned, so the 32-bit two's-complement value decoded as a huge positive
    number - one sample in 329, exactly at the zero crossing.
    """
    from growatt_api.device_type.inverter_120 import INPUT_REGISTERS_120

    registers = {r.register: r for r in INPUT_REGISTERS_120}
    decoded = process_registers(registers, {35: 0xFFFF, 36: 0xFF1B})
    assert decoded["output_power"] == -22.9


def test_32bit_power_and_energy_registers_are_signed():
    """Any 32-bit measurement that can cross zero must decode as signed.

    An unsigned 32-bit register reading -0.1 shows as 429,496,729.5. For
    energy sensors (state_class TOTAL_INCREASING) Home Assistant treats the
    subsequent drop as a meter reset and adds the spike to the lifetime
    total permanently.

    Signed decoding is a no-op for real readings: 100 kW is 1e6 raw and
    1 GWh is 1e7 raw, both far below the 2^31 sign bit.
    """
    from growatt_api.device_type.inverter_120 import INPUT_REGISTERS_120
    from growatt_api.device_type.inverter_315 import INPUT_REGISTERS_315
    from growatt_api.device_type.storage_120 import STORAGE_INPUT_REGISTERS_120

    for label, regs in (
        ("inverter_120", INPUT_REGISTERS_120),
        ("inverter_315", INPUT_REGISTERS_315),
        ("storage_120", STORAGE_INPUT_REGISTERS_120),
    ):
        for r in regs:
            if (
                r.value_type is float
                and r.length == 2
                and ("power" in r.name or "energy" in r.name)
            ):
                assert r.signed, (
                    f"{label}: {r.name} (register {r.register}) is unsigned"
                )
