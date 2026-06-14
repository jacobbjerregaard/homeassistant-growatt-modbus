"""Tests for battery time-slot register encoding."""
import pytest

from growatt_api.device_type.storage_120 import (
    TIME_SLOT_PRIORITIES,
    apply_time_slot_field,
    build_time_slot_registers,
    decode_time_slot,
    encode_time_slot,
    time_slot_register,
)


def test_time_slot_register_addresses():
    assert time_slot_register(1) == 3038
    assert time_slot_register(4) == 3044
    assert time_slot_register(5) == 3050
    assert time_slot_register(9) == 3058
    for bad in (0, 10, -1):
        with pytest.raises(ValueError):
            time_slot_register(bad)


def test_encode_time_slot_packs_bits():
    # 01:30 -> 05:45, battery priority (1), enabled
    reg1, reg2 = encode_time_slot(1, 30, 5, 45, TIME_SLOT_PRIORITIES["battery"], True)
    assert reg1 == 30 | (1 << 8) | (1 << 13) | (1 << 15)  # 41246
    assert reg2 == 45 | (5 << 8)  # 1325


def test_encode_time_slot_disabled_load_priority():
    reg1, reg2 = encode_time_slot(0, 0, 23, 59, TIME_SLOT_PRIORITIES["load"], False)
    assert reg1 == 0
    assert reg2 == 59 | (23 << 8)


def test_priorities_map():
    assert TIME_SLOT_PRIORITIES == {"load": 0, "battery": 1, "grid": 2}


def test_decode_is_inverse_of_encode():
    reg1, reg2 = encode_time_slot(1, 30, 5, 45, 1, True)
    assert decode_time_slot(reg1, reg2) == {
        "start_hour": 1,
        "start_minute": 30,
        "end_hour": 5,
        "end_minute": 45,
        "priority": 1,
        "enabled": True,
    }


def test_apply_time_slot_field_changes_one_field():
    reg1, reg2 = encode_time_slot(1, 30, 5, 45, 1, True)
    new1, new2 = apply_time_slot_field(reg1, reg2, priority=2, enabled=False)
    fields = decode_time_slot(new1, new2)
    assert fields["priority"] == 2
    assert fields["enabled"] is False
    # The other fields are preserved.
    assert fields["start_hour"] == 1 and fields["start_minute"] == 30
    assert fields["end_hour"] == 5 and fields["end_minute"] == 45


def test_build_time_slot_registers_addresses():
    regs = {r.name: r.register for r in build_time_slot_registers(2)}
    assert regs["tou_slot_1_word1"] == 3038
    assert regs["tou_slot_1_word2"] == 3039
    assert regs["tou_slot_2_word1"] == 3040
    assert regs["tou_slot_2_word2"] == 3041
