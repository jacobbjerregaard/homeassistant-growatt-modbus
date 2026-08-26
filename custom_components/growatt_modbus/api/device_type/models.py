"""The register dataclasses and the device-identity registers.

Everything here is model-agnostic: the shape of a register definition, the
decoded device info, and the handful of registers every Growatt device
exposes for identification.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .attrs import (
    ATTR_DEVICE_TYPE_CODE,
    ATTR_FIRMWARE,
    ATTR_NUMBER_OF_TRACKERS_AND_PHASES,
    ATTR_SERIAL_NUMBER,
)


class custom_function(type):
    """
    Object to be used as value_type in a `GrowattDeviceRegisters` whose raw
    value needs a custom function to translate it.
    """

    pass


@dataclass
class GrowattDeviceRegisters:
    """Dataclass object to define register value for Growatt devices using modbus."""

    name: str
    register: int
    value_type: type
    length: int = 1
    scale: float = 10
    function: Callable | None = None
    # When True the raw register value is interpreted as a two's-complement
    # signed integer (16-bit for length 1, 32-bit for length 2). Needed for
    # quantities that can be negative, e.g. temperatures or reactive power.
    signed: bool = False
    # The full result keys this register decodes to when its custom_function
    # expands one register into several named values (a packed bitfield). Empty
    # means the register produces a single value under ``name``.
    value_names: tuple[str, ...] = ()


@dataclass
class GrowattDeviceInfo:
    serial_number: str
    model: str
    firmware: str
    mppt_trackers: int
    grid_phases: int
    modbus_version: float
    device_type: str = ""


DEVICE_TYPE_CODES = {
    0x100: "1 tracker and 1phase Grid connect PV inverter TL",
    0x200: "2 tracker and 1phase Grid connect PV inverter TL",
    0x300: "1 tracker and 1phase Grid connect PV inverter HF",
    0x400: "2 tracker and 1phase Grid connect PV inverter HF",
    0x500: "1 tracker and 1phase Grid connect PV inverter LF",
    0x600: "2 tracker and 1phase Grid connect PV inverter LF",
    0x700: "1 tracker and 3phase Grid connect PV inverter TL",
    0x800: "2 tracker and 3phase Grid connect PV inverter TL",
    0x900: "1 tracker and 3phase Grid connect PV inverter LF",
    0xA00: "2 tracker and 3phase Grid connect PV inverter LF",
    0xC00: "Front 1 tracker PV Storage",
    0xD00: "OffGrid SPF 3-5K",
    0x1500: "2 tracker and 3phase Grid connect Hybrid inverter",
    10001: "RF-ShineVersion",
    10002: "Web-ShinePano",
    10003: "Web-ShineWebBox",
    10004: "WL-WIFI Module",
}


def device_type(register) -> str:
    not_defined = f"Device type {register} not defined in protocol"

    if 10000 < register <= 10004:
        return DEVICE_TYPE_CODES.get(register, not_defined)

    return DEVICE_TYPE_CODES.get(register & 0xFF00, not_defined)


def trackers_and_phases(register) -> tuple[int, int]:
    # number of mppt trackers high byte, grid phases low byte
    return (register >> 8, register & 0xFF)


# Firmware is registers 9-11 (3 words / 6 ASCII chars). Registers 12-14 are a
# separate "control firmware" version, so reading length=6 mashed both together.
FIRMWARE_REGISTER = GrowattDeviceRegisters(
    name=ATTR_FIRMWARE, register=9, value_type=str, length=3
)
SERIAL_NUMBER_REGISTER = GrowattDeviceRegisters(
    name=ATTR_SERIAL_NUMBER, register=23, value_type=str, length=5
)
DEVICE_TYPE_CODE_REGISTER = GrowattDeviceRegisters(
    name=ATTR_DEVICE_TYPE_CODE,
    register=43,
    value_type=custom_function,
    function=device_type,
)
NUMBER_OF_TRACKERS_AND_PHASES_REGISTER = GrowattDeviceRegisters(
    name=ATTR_NUMBER_OF_TRACKERS_AND_PHASES,
    register=44,
    value_type=custom_function,
    function=trackers_and_phases,
)
