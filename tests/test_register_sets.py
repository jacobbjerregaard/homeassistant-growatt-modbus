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


def test_ac_charge_energy_only_on_storage_models():
    """Input 112-115 mean different things depending on the model.

    Protocol_II V1.39 documents 112-115 as ACCharge energy today/total
    (0.1 kWh) on Storage Power models. On the MAX series the same addresses
    are Warn Maincode, real Power Percent, inv start delay time and
    bINVAllFaultCode. Decoding those four as a pair of 32-bit energy
    counters produces large nonsense values, and because the sensors are
    TOTAL_INCREASING the nonsense accumulates permanently.
    """
    plain = get_register_information(DeviceTypes.INVERTER_120)
    assert not [r for r in plain.input.values() if "ac_charge" in r.name.lower()]
    for addr in (112, 113, 114, 115):
        assert addr not in plain.input, (
            f"plain inverter map claims input register {addr}, which is "
            "model-specific and not ACCharge energy on the MAX series"
        )

    for device_type in (DeviceTypes.HYBRID_120, DeviceTypes.STORAGE_120):
        info = get_register_information(device_type)
        names = {r.name.lower() for r in info.input.values()}
        assert "battery_ac_charge_energy_today" in names
        assert "battery_ac_charge_energy_total" in names


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
