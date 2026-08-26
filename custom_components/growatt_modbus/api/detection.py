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

_LOGGER = logging.getLogger(__name__)


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
        elif fixed_device_types == DeviceTypes.INVERTER_315:
            return await device.get_device_info(
                HOLDING_REGISTERS_315, minimal_length, unit
            )
        else:
            return None

    _LOGGER.debug("Detecting Growatt device info")
    inverter_v120 = await device.get_device_info(
        HOLDING_REGISTERS_120, minimal_length, unit
    )
    _LOGGER.debug("Inverter Protocol v1.24: %s", inverter_v120)

    inverter_v315 = await device.get_device_info(
        HOLDING_REGISTERS_315, minimal_length, unit
    )
    _LOGGER.debug("Inverter Protocol v3.15: %s", inverter_v315)

    if 1.0 < inverter_v120.modbus_version < 1.25:
        return inverter_v120
    elif 3.0 < inverter_v315.modbus_version < 3.15:
        return inverter_v315
    else:
        _LOGGER.warning(
            "Inverter Modbus version is not supported by default. Check the "
            "full logs for the device information gathered with each "
            "supported protocol. fixed_device_types: %s",
            fixed_device_types,
        )
        return None
