"""Compatibility surface for the split register modules.

The contents of this module now live in three focused ones:

    attrs.py   the ATTR_* result-key names
    models.py  GrowattDeviceRegisters, GrowattDeviceInfo and the identity
               registers every device exposes
    status.py  the status / derating / warning / fault code tables

Everything is re-exported here so existing imports keep working. Prefer
importing from the specific module in new code - importing the register
dataclass should not have to pull in 150 name constants.
"""
from .attrs import *  # noqa: F403
from .models import (  # noqa: F401
    DEVICE_TYPE_CODE_REGISTER,
    DEVICE_TYPE_CODES,
    FIRMWARE_REGISTER,
    NUMBER_OF_TRACKERS_AND_PHASES_REGISTER,
    SERIAL_NUMBER_REGISTER,
    GrowattDeviceInfo,
    GrowattDeviceRegisters,
    custom_function,
    device_type,
    trackers_and_phases,
)
from .status import (  # noqa: F401
    INVERTER_DERATINGMODES,
    INVERTER_FAULTCODES,
    INVERTER_WARNINGCODES,
    InverterStatus,
    inverter_status,
)
