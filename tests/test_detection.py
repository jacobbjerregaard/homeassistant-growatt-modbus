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


def test_fixed_legacy_inverter_uses_315_registers():
    # The legacy "inverter" type polls the v3.15 map (see device._REGISTER_SETS);
    # returning None here made such entries impossible to reconfigure.
    from growatt_api.device_type.inverter_315 import HOLDING_REGISTERS_315

    device = _StubDevice()
    assert asyncio.run(get_device_info(device, 1, DeviceTypes.INVERTER)) is not None
    assert device.requested is HOLDING_REGISTERS_315


from growatt_api.device_type.base import GrowattDeviceInfo  # noqa: E402
from growatt_api.device_type.inverter_120 import HOLDING_REGISTERS_120  # noqa: E402


def _info(version):
    return GrowattDeviceInfo(
        serial_number="S",
        model="M",
        firmware="F",
        mppt_trackers=1,
        grid_phases=1,
        modbus_version=version,
        device_type="t",
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


def test_autodetect_accepts_exactly_v315():
    result = asyncio.run(get_device_info(_VersionDevice(0.0, 3.15), 1))
    assert result is not None and result.modbus_version == 3.15


def test_autodetect_tries_v315_when_v120_probe_is_rejected():
    """A v3.15 inverter may reject the v1.24 identity addresses outright.

    That exception used to abort detection before the v3.15 layout was tried.
    """
    from growatt_api.exception import ModbusException

    class _Rejects120(_VersionDevice):
        async def get_device_info(self, registers, max_length, unit):
            if registers is HOLDING_REGISTERS_120:
                raise ModbusException("illegal data address")
            return await super().get_device_info(registers, max_length, unit)

    result = asyncio.run(get_device_info(_Rejects120(0.0, 3.05), 1))
    assert result is not None and result.modbus_version == 3.05


@pytest.mark.parametrize(
    ("version", "expected"),
    [(1.24, DeviceTypes.INVERTER_120), (3.05, DeviceTypes.INVERTER_315)],
)
def test_default_device_type_is_a_selectable_type(version, expected):
    from growatt_api.detection import default_device_type

    assert default_device_type(_info(version)) is expected


@pytest.mark.parametrize(
    "device_type", [DeviceTypes.HYBRID_120, DeviceTypes.STORAGE_120]
)
def test_storage_types_read_the_serial_from_3001(device_type):
    """Holding 23 is empty on storage/hybrid devices; the serial is at 3001.

    Verified on a MOD TL3-XH: 23-27 read zeros, 3001+ read "HHM0DAA03B".
    Reading 23 gave these entries an empty serial as their unique_id.
    """
    from growatt_api.device_type.attrs import ATTR_SERIAL_NUMBER

    device = _StubDevice()
    asyncio.run(get_device_info(device, 1, device_type))

    serial = [r for r in device.requested if r.name == ATTR_SERIAL_NUMBER]
    assert [(r.register, r.length) for r in serial] == [(3001, 15)]


def test_plain_v124_inverter_still_reads_the_serial_from_23():
    from growatt_api.device_type.attrs import ATTR_SERIAL_NUMBER

    device = _StubDevice()
    asyncio.run(get_device_info(device, 1, DeviceTypes.INVERTER_120))

    serial = [r for r in device.requested if r.name == ATTR_SERIAL_NUMBER]
    assert [r.register for r in serial] == [23]
