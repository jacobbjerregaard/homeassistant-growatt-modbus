"""Tests for per-device-type register selection in ``API/device.py``.

These pin the register layout chosen for each device type after the
get_register_information refactor (if/elif chain -> table lookup). Importing
``growatt_api.device`` pulls in the transport module, which needs pymodbus.
"""
import pytest

from growatt_api.const import DeviceTypes
from growatt_api.device_type.inverter_120 import (
    HOLDING_REGISTERS_120,
    INPUT_REGISTERS_120,
    MAXIMUM_DATA_LENGTH_120,
)
from growatt_api.device_type.inverter_315 import (
    HOLDING_REGISTERS_315,
    INPUT_REGISTERS_315,
    MAXIMUM_DATA_LENGTH_315,
)
from growatt_api.device_type.storage_120 import (
    STORAGE_HOLDING_REGISTERS_120,
    STORAGE_INPUT_REGISTERS_120,
)

pytest.importorskip("pymodbus", reason="device.py imports the pymodbus transport")

from growatt_api.device import get_register_information  # noqa: E402


def _by_register(registers):
    return {reg.register: reg for reg in registers}


def test_inverter_and_315_use_the_315_layout():
    for device_type in (DeviceTypes.INVERTER, DeviceTypes.INVERTER_315):
        info = get_register_information(device_type)
        assert info.max_length == MAXIMUM_DATA_LENGTH_315
        assert info.holding == _by_register(HOLDING_REGISTERS_315)
        assert info.input == _by_register(INPUT_REGISTERS_315)


def test_inverter_120_uses_the_120_layout():
    info = get_register_information(DeviceTypes.INVERTER_120)
    assert info.max_length == MAXIMUM_DATA_LENGTH_120
    assert info.holding == _by_register(HOLDING_REGISTERS_120)
    assert info.input == _by_register(INPUT_REGISTERS_120)


def test_hybrid_120_merges_inverter_and_storage_inputs():
    info = get_register_information(DeviceTypes.HYBRID_120)
    assert info.holding == _by_register(STORAGE_HOLDING_REGISTERS_120)
    # Hybrid sees both the standard inverter inputs and the storage inputs.
    expected_input = _by_register(INPUT_REGISTERS_120)
    expected_input.update(_by_register(STORAGE_INPUT_REGISTERS_120))
    assert info.input == expected_input


def test_storage_120_uses_storage_layout_only():
    info = get_register_information(DeviceTypes.STORAGE_120)
    assert info.holding == _by_register(STORAGE_HOLDING_REGISTERS_120)
    assert info.input == _by_register(STORAGE_INPUT_REGISTERS_120)


def test_unsupported_device_type_raises():
    with pytest.raises(TypeError):
        get_register_information("not-a-device-type")
