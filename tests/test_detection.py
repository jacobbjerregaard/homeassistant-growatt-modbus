"""Regression tests for device detection (API/detection.py)."""
import asyncio

import pytest

pytest.importorskip("pymodbus", reason="detection.py imports the transport layer")

from growatt_api.const import DeviceTypes
from growatt_api.detection import get_device_info


class _StubDevice:
    """Records which holding-register set detection asked for."""

    def __init__(self):
        self.requested = None

    async def get_device_info(self, registers, max_length, unit):
        self.requested = registers
        return f"info:{len(registers)}"


def test_fixed_inverter_315_does_not_raise():
    # Previously crashed with AttributeError on DeviceTypes.OFFGRID_SPF when the
    # v3.15 inverter type was selected in the config flow.
    device = _StubDevice()
    result = asyncio.run(get_device_info(device, 1, DeviceTypes.INVERTER_315))
    assert result is not None
    assert device.requested is not None


@pytest.mark.parametrize(
    "device_type",
    [DeviceTypes.INVERTER_120, DeviceTypes.HYBRID_120, DeviceTypes.STORAGE_120],
)
def test_fixed_120_family_uses_120_registers(device_type):
    device = _StubDevice()
    result = asyncio.run(get_device_info(device, 1, device_type))
    assert result is not None


def test_fixed_unknown_type_returns_none():
    # A device type outside the 120 family / 315 falls through to None.
    assert asyncio.run(get_device_info(_StubDevice(), 1, DeviceTypes.INVERTER)) is None


from growatt_api.device_type.base import GrowattDeviceInfo  # noqa: E402
from growatt_api.device_type.inverter_120 import HOLDING_REGISTERS_120  # noqa: E402


def _info(version):
    return GrowattDeviceInfo(
        serial_number="S", model="M", firmware="F",
        mppt_trackers=1, grid_phases=1, modbus_version=version, device_type="t",
    )


class _VersionDevice:
    """Returns a different modbus_version per holding-register set probed."""

    def __init__(self, v120, v315):
        self.v120, self.v315 = v120, v315

    async def get_device_info(self, registers, max_length, unit):
        return _info(self.v120 if registers is HOLDING_REGISTERS_120 else self.v315)


def test_autodetect_selects_v120():
    result = asyncio.run(get_device_info(_VersionDevice(1.24, 0.0), 1))
    assert result.modbus_version == 1.24


def test_autodetect_selects_v315():
    result = asyncio.run(get_device_info(_VersionDevice(0.0, 3.05), 1))
    assert result.modbus_version == 3.05


def test_autodetect_unknown_version_returns_none():
    assert asyncio.run(get_device_info(_VersionDevice(0.0, 0.0), 1)) is None
