"""Define constants for the Growatt Server component."""
from enum import StrEnum
from homeassistant.const import Platform

CONF_LAYER = "communication_layer"
CONF_SERIAL = "serial"
CONF_TCP = "tcp"
CONF_UDP = "udp"

CONF_FRAME = "modbus_frame"

CONF_SERIAL_PORT = "port"
CONF_BAUDRATE = "baudrate"
CONF_STOPBITS = "stopbits"
CONF_PARITY = "parity"
CONF_BYTESIZE = "bytesize"

CONF_DC_STRING = "dc_string"
CONF_AC_PHASES = "ac_phases"
CONF_BATTERY_MODULES = "battery_modules"
CONF_TOU_SLOTS = "time_of_use_slots"

CONF_POWER_SCAN_INTERVAL = "power_scan_interval"
CONF_POWER_SCAN_ENABLED = "power_scan_enabled"
CONF_INVERTER_POWER_CONTROL = "inverter_power_control"

CONF_SERIAL_NUMBER = "serial_number"
CONF_FIRMWARE = "firmware"

# EMHASS energy optimizer (see emhass_client.py / optimizer.py). The optimizer
# is optional: it is only wired up when an EMHASS URL is configured.
CONF_EMHASS_URL = "emhass_url"
CONF_EMHASS_TOKEN = "emhass_token"
CONF_OPTIMIZER_ENABLED = "optimizer_enabled"
CONF_OPTIMIZER_SOC_SENSOR = "optimizer_soc_sensor"
CONF_OPTIMIZER_INTERVAL = "optimizer_interval"

DEFAULT_OPTIMIZER_INTERVAL = 300


class ParityOptions(StrEnum):
    NONE = "None"
    EVEN = "Even"
    ODD = "Odd"
    MARK = "Mark"
    SPACE = "Space"


DEFAULT_PLANT_ID = "0"

DEFAULT_NAME = "Growatt Modbus"

DOMAIN = "growatt_modbus"

PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.TIME,
]
