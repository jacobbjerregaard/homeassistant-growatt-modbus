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


def test_storage_exposes_battery_charge_discharge_stop_soc():
    """951/952 (uwBatChargeStopSoc / uwBatDisChargeStopSoc) are writable SOC limits."""
    by_reg = _by_register(STORAGE_HOLDING_REGISTERS_120)
    assert 951 in by_reg, "missing uwBatChargeStopSoc (holding 951)"
    assert 952 in by_reg, "missing uwBatDisChargeStopSoc (holding 952)"
    assert by_reg[951].name == "battery_global_charge_stop_soc"
    assert by_reg[952].name == "battery_global_discharge_stop_soc"
    assert by_reg[951].value_type is int
    assert by_reg[952].value_type is int


def test_unsupported_device_type_raises():
    with pytest.raises(TypeError):
        get_register_information("not-a-device-type")


def test_energy_registers_all_divide_by_ten():
    """Every energy register is 0.1 kWh per LSB, so scale must be 10.

    battery_ac_charge_energy_today/_total previously carried scale=0.1, which
    the decoder applies as `raw / 0.1` - multiplying by 10 rather than
    dividing. That overstated the value 100x and raised the ceiling for a
    single reading from ~429 GWh to ~42.9 TWh.
    """
    for device_type in (
        DeviceTypes.INVERTER,
        DeviceTypes.INVERTER_120,
        DeviceTypes.INVERTER_315,
        DeviceTypes.HYBRID_120,
        DeviceTypes.STORAGE_120,
    ):
        info = get_register_information(device_type)
        for bank in (info.holding, info.input):
            for register in bank.values():
                if "energy" in register.name and register.value_type is float:
                    assert register.scale == 10, (
                        f"{device_type.value}: {register.name} (register "
                        f"{register.register}) has scale={register.scale}, "
                        "expected 10"
                    )


def test_no_register_scale_below_one():
    """A scale below 1 multiplies instead of divides - almost always a typo."""
    for device_type in DeviceTypes:
        info = get_register_information(device_type)
        for bank in (info.holding, info.input):
            for register in bank.values():
                if register.value_type is float:
                    assert register.scale >= 1, (
                        f"{device_type.value}: {register.name} has "
                        f"scale={register.scale}"
                    )
