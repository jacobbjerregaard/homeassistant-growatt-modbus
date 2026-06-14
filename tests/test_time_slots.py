"""Tests for battery time-slot register encoding."""
import pytest

from growatt_api.device_type.storage_120 import (
    TIME_SLOT_PRIORITIES,
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
