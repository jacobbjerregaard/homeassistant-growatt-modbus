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
