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


def test_input_112_to_115_are_not_mapped_as_ac_charge_energy():
    """Input 112-115 mean different things depending on the model.

    Protocol_II V1.39 documents 112-115 as ACCharge energy today/total only on
    Storage Power (SPH/SPA) models. The TL-X/MAX meaning - Warn Maincode, real
    Power Percent, inv start delay time, bINVAllFaultCode - applies to the
    plain inverters and, verified on a live MOD TL3-XH, to the TL-XH hybrids
    this integration's storage map covers: 113 read -30 (real power percent
    while charging) and 114 read 180 (start delay, s). Decoded as energy they
    gave a "1.7 kWh today" that tracked the power percentage and a 1,179,648
    kWh lifetime total, folded into TOTAL_INCREASING statistics.
    """
    for device_type in DeviceTypes:
        info = get_register_information(device_type, battery_modules=3, tou_slots=9)
        assert not [r for r in info.input.values() if "ac_charge" in r.name.lower()]
        for addr in (112, 113, 114, 115):
            assert addr not in info.input, (
                f"{device_type} maps input register {addr}, which is model-"
                "specific and not ACCharge energy on TL-X/TL-XH/MAX devices"
            )


def test_warning_code_is_a_single_register():
    """110 is "Warning bit H"; 111 is a separate "Warn Subcode".

    They are not the two halves of a 32-bit value, and the int decode path
    ignores `length` regardless - so declaring length=2 only caused register
    111 to be fetched every poll and thrown away.
    """
    info = get_register_information(DeviceTypes.INVERTER_120)
    warning = info.input[110]
    assert warning.name == "warning_code"
    assert warning.length == 1
    assert 111 not in info.input
