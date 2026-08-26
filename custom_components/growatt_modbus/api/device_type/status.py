"""Inverter status, derating, warning and fault code tables."""

from enum import Enum
from typing import Any

from .attrs import ATTR_DERATING_MODE, ATTR_FAULT_CODE, ATTR_STATUS_CODE


class InverterStatus(Enum):
    "Enum of possible Inverter Status."

    Waiting = 0
    Normal = 1
    Fault = 3


INVERTER_DERATINGMODES = {
    0: "No Deratring",
    1: "PV",
    3: "Vac",
    4: "Fac",
    5: "Tboost",
    6: "Tinv",
    7: "Control",
    8: "*LoadSpeed",
    9: "*OverBackByTime",
}
INVERTER_WARNINGCODES = {
    0x0000: "None",
    0x0001: "Fan warning",
    0x0002: "String communication abnormal",
    0x0004: "StrPID config Warning",
    0x0008: "Fail to read EEPROM",
    0x0010: "DSP and COM firmware unmatch",
    0x0020: "Fail to write EEPROM",
    0x0040: "SPD abnormal",
    0x0080: "GND and N connect abnormal",
    0x0100: "PV1 or PV2 circuit short",
    0x0200: "PV1 or PV2 boost driver broken",
    0x0400: "",
    0x0800: "",
    0x1000: "",
    0x2000: "",
    0x4000: "",
    0x8000: "",
}
INVERTER_FAULTCODES = {
    0: "None",
    24: "Auto Test Failed",
    25: "No AC Connection",
    26: "PV Isolation Low",
    27: "Residual I High",
    28: "Output High DCI",
    29: "PV Voltage High",
    30: "AC V Out of Range",
    31: "AC F Out of Range",
    32: "Module Hot",
}
for i in range(1, 24):
    INVERTER_FAULTCODES[i] = f"Generic Error Code: {99 + i}"


def inverter_status(value: dict[str, Any]) -> str | None:
    """Returns status based on multiple registery values."""
    if ATTR_STATUS_CODE not in value.keys():
        return None

    status_value = InverterStatus(value[ATTR_STATUS_CODE])

    if status_value is InverterStatus.Waiting:
        return status_value.name

    elif status_value == InverterStatus.Normal:
        derating = value.get(ATTR_DERATING_MODE, None)
        if (
            derating is not None
            and derating in INVERTER_DERATINGMODES.keys()
            and derating != 0
        ):
            return f"{status_value.name} - {INVERTER_DERATINGMODES[derating]}"

        return status_value.name

    elif status_value is InverterStatus.Fault:
        fault = value.get(ATTR_FAULT_CODE, None)
        if fault is not None and fault != 0:
            return f"{status_value.name} - {INVERTER_FAULTCODES[fault]}"

    return None
