"""Device defaults for a Growatt Inverter."""
from .base import (
    GrowattDeviceRegisters,
    custom_function,
    FIRMWARE_REGISTER,
    DEVICE_TYPE_CODE_REGISTER,
    NUMBER_OF_TRACKERS_AND_PHASES_REGISTER,
    ATTR_BATTERY_NUMBER_OF_MODULES,
    ATTR_INVERTER_MODEL,
    ATTR_MODBUS_VERSION,
    ATTR_SOC_PERCENTAGE,
    ATTR_DISCHARGE_POWER,
    ATTR_CHARGE_POWER,
    ATTR_ENERGY_TO_USER_TODAY,
    ATTR_ENERGY_TO_USER_TOTAL,
    ATTR_ENERGY_TO_GRID_TODAY,
    ATTR_ENERGY_TO_GRID_TOTAL,
    ATTR_DISCHARGE_ENERGY_TODAY,
    ATTR_DISCHARGE_ENERGY_TOTAL,
    ATTR_CHARGE_ENERGY_TODAY,
    ATTR_CHARGE_ENERGY_TOTAL,
    ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST,
    ATTR_BATTERY_CHARGE_STOP_SOC,
    ATTR_BATTERY_PACK_NUMBER,
    ATTR_AC_CHARGE_ENABLED,
    ATTR_SERIAL_NUMBER,
    ATTR_METER_POWER_NETTO,
    ATTR_INVERTER_STATUS,
    ATTR_INVERTER_MODE,
    ATTR_BDC_DATA_FLAG,
    ATTR_BDC_DERATING_MODE,
    ATTR_BMS_TEMPERATURE_A,
    ATTR_BMS_TEMPERATURE_B,
)
MAXIMUM_DATA_LENGTH = 100
def model(registers) -> str:
    mo = (registers[0] << 16) + registers[1]
    return "A{:X} B{:X} D{:X} T{:X} P{:X} U{:X} M{:X} S{:X}".format(
        (mo & 0xF0000000) >> 28,
        (mo & 0x0F000000) >> 24,
        (mo & 0x00F00000) >> 20,
        (mo & 0x000F0000) >> 16,
        (mo & 0x0000F000) >> 12,
        (mo & 0x00000F00) >> 8,
        (mo & 0x000000F0) >> 4,
        (mo & 0x0000000F)
    )
SERIAL_NUMBER_REGISTER = GrowattDeviceRegisters(
    name=ATTR_SERIAL_NUMBER, register=3001, value_type=str, length=15
)

def inverter_status(register) -> str:
    web_status = register & 0x00FF
    if web_status == 0:
        return "Standby"
    if web_status == 1:
        return "Normal"
    if web_status == 3:
        return "Fault"
    if web_status == 4:
        return "Flash"

def inverter_mode(register) -> str:
    if register == 0:
        return "Load"
    if register == 1:
        return "Battery"
    if register == 2:
        return "Grid"

    return f"Unknown value: {register}"

def bdc_data_flag(register) -> str:
    if register == 0:
        return "No need"
    if register == 1:
        return "Need"
    
    return f"Unknown value: {register}"

def bdc_derating_mode(register) -> str:
    if register == 0:
        return "Normal"
    if register == 1:
        return "Standby or fault"
    if register == 2:
        return "Maximum battery current limit (Discharge)"
    if register == 3:
        return "Battery discharge Enable (Discharge)"
    if register == 4:
        return "High bus discharge derating (Discharge)"
    if register == 5:
        return "High temperature discharge derating (Discharge)"
    if register == 6:
        return "System warning No discharge (Discharge)"
    if register >= 7 and register <= 15:
        return "Reserved (Discharge)"
    if register == 16:
        return "Maximum charging current of battery (Charging)"
    if register == 17:
        return "High Temperature (LLC and Buckboost) (Charging)"
    if register == 18:
        return "Final soft charge"
    if register == 19:
        return "SOC setting limits (Charging)"
    if register == 20:
        return "Battery low temperature (Charging)"
    if register == 21:
        return "High bus voltage (Charging)"
    if register == 22:
        return "Battery SOC (Charging)"
    if register == 23:
        return "Need to charge (Charging)"
    if register == 24:
        return "System warning not charging (Charging)"
    if register >= 25 and register <= 29:
        return "Reserved (Charging)"
    
    return f"Unknown value: {register}"



def netto_meter_energy(registers) -> float:
    production = (registers[0] * 65536.0 + registers[1])* 0.1
    consumption = (registers[2] * 65536.0 + registers[3]) * 0.1 

    return production - consumption


STORAGE_HOLDING_REGISTERS_120: tuple[GrowattDeviceRegisters, ...] = (
    FIRMWARE_REGISTER,
    SERIAL_NUMBER_REGISTER,
    GrowattDeviceRegisters(
        name=ATTR_INVERTER_MODEL,
        register=28,
        value_type=custom_function,
        length=2,
        function=model
    ),
    DEVICE_TYPE_CODE_REGISTER,
    NUMBER_OF_TRACKERS_AND_PHASES_REGISTER,
    GrowattDeviceRegisters(
        name=ATTR_MODBUS_VERSION,
        register=88,
        value_type=float,
        scale=100
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_NUMBER_OF_MODULES,
        register=185,
        value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST,
        register=3047,
        value_type=int,
        length=1
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_CHARGE_STOP_SOC,
        register=3048,
        value_type=int,
        length=1
    ),
    GrowattDeviceRegisters(
        name=ATTR_AC_CHARGE_ENABLED,
        register=3049,
        value_type=int,
        length=1
    ),
)

STORAGE_INPUT_REGISTERS_120: tuple[GrowattDeviceRegisters, ...] = (
    GrowattDeviceRegisters(
        name=ATTR_INVERTER_STATUS,
        register=3000,
        value_type=custom_function,
        length=1,
        function=inverter_status
    ),
    GrowattDeviceRegisters(
        name=ATTR_METER_POWER_NETTO,
        register=3041,
        value_type=custom_function,
        length=4,
        function=netto_meter_energy
    ),
    GrowattDeviceRegisters(
        name=ATTR_INVERTER_MODE,
        register=3144,
        value_type=custom_function,
        length=1,
        function=inverter_mode
    ),
    GrowattDeviceRegisters(
        name=ATTR_BDC_DATA_FLAG,
        register=3164,
        value_type=custom_function,
        length=1,
        function=bdc_data_flag
    ),
    GrowattDeviceRegisters(
        name=ATTR_BDC_DERATING_MODE,
        register=3165,
        value_type=custom_function,
        length=1,
        function=bdc_derating_mode
    ),
    GrowattDeviceRegisters(
        name=ATTR_SOC_PERCENTAGE, register=3171, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_DISCHARGE_POWER, register=3178, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_CHARGE_POWER, register=3180, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_ENERGY_TO_USER_TODAY, register=3067, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_ENERGY_TO_USER_TOTAL, register=3069, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_ENERGY_TO_GRID_TODAY, register=3071, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_ENERGY_TO_GRID_TOTAL, register=3073, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_DISCHARGE_ENERGY_TODAY, register=3125, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_DISCHARGE_ENERGY_TOTAL, register=3127, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_CHARGE_ENERGY_TODAY, register=3129, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_CHARGE_ENERGY_TOTAL, register=3131, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_TEMPERATURE_A, register=3176, value_type=float
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_TEMPERATURE_B, register=3177, value_type=float
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_PACK_NUMBER, register=3262, value_type=int
    ),
)