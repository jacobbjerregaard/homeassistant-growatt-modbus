"""
Growatt device detection.

Probes a connected Modbus device to determine which protocol/register layout
it speaks, used by the config flow before a device type is committed.
"""

import logging

from .client import GrowattModbusBase
from .const import DeviceTypes
from .device_type.base import GrowattDeviceInfo
from .device_type.inverter_120 import HOLDING_REGISTERS_120, MAXIMUM_DATA_LENGTH_120
from .device_type.inverter_315 import HOLDING_REGISTERS_315, MAXIMUM_DATA_LENGTH_315
from .exception import ModbusException

_LOGGER = logging.getLogger(__name__)


async def _probe(
    device: GrowattModbusBase, registers, max_length: int, unit: int
) -> GrowattDeviceInfo | None:
    """Read the identity registers of one protocol layout.

    A device that speaks the other protocol may reject these addresses with a
    Modbus exception response. That means "not this protocol", not a failed
    detection, so it must not stop the other layout from being tried.
    """
    try:
        return await device.get_device_info(registers, max_length, unit)
    except ModbusException as err:
        _LOGGER.debug("Protocol probe rejected by the device: %s", err)
        return None


async def get_device_info(
    device: GrowattModbusBase, unit: int, fixed_device_types: DeviceTypes | None = None
) -> GrowattDeviceInfo | None:
    # Use the smallest of the supported maximums: every candidate device has
    # to be able to serve a read of this length.
    minimal_length = min((MAXIMUM_DATA_LENGTH_120, MAXIMUM_DATA_LENGTH_315))

    if fixed_device_types is not None:
        if fixed_device_types in (
            DeviceTypes.INVERTER_120,
            DeviceTypes.HYBRID_120,
            DeviceTypes.STORAGE_120,
        ):
            return await device.get_device_info(
                HOLDING_REGISTERS_120, minimal_length, unit
            )
        # The legacy "inverter" type uses the v3.15 register map.
        elif fixed_device_types in (DeviceTypes.INVERTER_315, DeviceTypes.INVERTER):
            return await device.get_device_info(
                HOLDING_REGISTERS_315, minimal_length, unit
            )
        else:
            return None

    _LOGGER.debug("Detecting Growatt device info")
    inverter_v120 = await _probe(device, HOLDING_REGISTERS_120, minimal_length, unit)
    _LOGGER.debug("Inverter Protocol v1.24: %s", inverter_v120)

    inverter_v315 = await _probe(device, HOLDING_REGISTERS_315, minimal_length, unit)
    _LOGGER.debug("Inverter Protocol v3.15: %s", inverter_v315)

    if inverter_v120 is not None and 1.0 < inverter_v120.modbus_version < 1.25:
        return inverter_v120
    # Inclusive: a device reporting exactly 3.15 speaks the protocol this
    # layout is named after.
    elif inverter_v315 is not None and 3.0 < inverter_v315.modbus_version <= 3.15:
        return inverter_v315
    else:
        _LOGGER.warning(
            "Inverter Modbus version is not supported by default. Check the "
            "full logs for the device information gathered with each "
            "supported protocol. fixed_device_types: %s",
            fixed_device_types,
        )
        return None


def default_device_type(info: GrowattDeviceInfo) -> DeviceTypes:
    """The device type to preselect for a detected device.

    ``info.device_type`` is the register-43 description ("2 tracker and 3phase
    ..."), not a :class:`DeviceTypes` value, so it cannot be the form default.
    Detection cannot tell a plain v1.24 inverter from a hybrid; the user
    picks hybrid where it applies.
    """
    if info.modbus_version >= 3.0:
        return DeviceTypes.INVERTER_315
    return DeviceTypes.INVERTER_120
