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
    ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST,
    ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST,
    ATTR_BATTERY_CHARGE_STOP_SOC,
    ATTR_BATTERY_PACK_NUMBER,
    ATTR_AC_CHARGE_ENABLED,
    ATTR_GRID_FIRST_STOP_SOC,
    ATTR_ON_GRID_DISCHARGE_STOP_SOC,
    ATTR_BATTERY_TYPE,
    ATTR_PRE_PTO_ENABLED,
    ATTR_GENERATOR_CHARGE_ENABLED,
    ATTR_GENERATOR_FORCE,
    ATTR_UPS_FUNCTION_ENABLED,
    ATTR_UPS_OUTPUT_VOLTAGE,
    ATTR_UPS_OUTPUT_FREQUENCY,
    ATTR_DRY_CONTACT_ENABLED,
    ATTR_SERIAL_NUMBER,
    ATTR_METER_POWER_NETTO,
    ATTR_INVERTER_STATUS,
    ATTR_INVERTER_MODE,
    ATTR_BDC_DATA_FLAG,
    ATTR_BDC_DERATING_MODE,
    ATTR_BMS_TEMPERATURE_A,
    ATTR_BMS_TEMPERATURE_B,
    ATTR_BATTERY_VOLTAGE,
    ATTR_BATTERY_CURRENT,
    ATTR_SELF_CONSUMPTION_POWER,
    ATTR_SYSTEM_ENERGY_TODAY,
    ATTR_SYSTEM_ENERGY_TOTAL,
    ATTR_SELF_CONSUMPTION_ENERGY_TODAY,
    ATTR_SELF_CONSUMPTION_ENERGY_TOTAL,
    ATTR_BMS_MAX_SOC,
    ATTR_BMS_MIN_SOC,
    ATTR_PARALLEL_BATTERY_NUM,
    ATTR_STORAGE_FAULT_CODE,
    ATTR_STORAGE_WARNING_CODE,
    ATTR_BMS_DERATE_REASON,
    ATTR_BMS_STATUS,
    ATTR_BMS_SOC,
    ATTR_BMS_MAX_CHARGE_CURRENT,
    ATTR_BMS_MAX_DISCHARGE_CURRENT,
    ATTR_BMS_CYCLE_COUNT,
    ATTR_BMS_SOH,
    ATTR_BMS_CELL_VOLTAGE_MAX,
    ATTR_BMS_CELL_VOLTAGE_MIN,
)
MAXIMUM_DATA_LENGTH = 100


def bms_status(register) -> str:
    return {
        0: "Dormancy",
        1: "Charging",
        2: "Discharging",
        3: "Free",
        4: "Standby",
        5: "Soft start",
        6: "Fault",
        7: "Update",
    }.get(register, f"Unknown value: {register}")


# Per-parallel-BDC ("battery module") telemetry block. Each module occupies 108
# registers starting at 4000; the first 8 are the serial number, the next 69
# mirror the aggregate data block at input 3165-3233. So module n's data block
# starts at 4008 + (n-1)*108, and a field at aggregate address A is at that base
# plus (A - 3165). See "BDC and BMS information" in the V1.39 spec.
_MODULE_BLOCK_BASE = 4000
_MODULE_BLOCK_SIZE = 108
_MODULE_DATA_OFFSET = 8  # serial number occupies the first 8 registers
_MODULE_AGGREGATE_BASE = 3165

# (aggregate address, name suffix, value_type, scale, signed)
_BATTERY_MODULE_FIELDS = (
    (3169, "voltage", float, 100, False),
    (3170, "current", float, 10, True),
    (3171, "soc", int, 10, False),
    (3176, "temperature", float, 10, True),
    (3222, "soh", int, 10, False),
)


# Battery charge/discharge time slots 1-9. Each slot is a register pair:
#   reg1: Bit0-7 start minute | Bit8-12 start hour | Bit13-14 priority | Bit15 enable
#   reg2: Bit0-7 end minute   | Bit8-12 end hour
# Slots 1-4 are at 3038/3040/3042/3044; slots 5-9 at 3050/3052/.../3058.
TIME_SLOT_PRIORITIES = {"load": 0, "battery": 1, "grid": 2}


def time_slot_register(slot: int) -> int:
    """Return the first holding register of time slot `slot` (1-9)."""
    if 1 <= slot <= 4:
        return 3038 + (slot - 1) * 2
    if 5 <= slot <= 9:
        return 3050 + (slot - 5) * 2
    raise ValueError(f"time slot must be 1-9, got {slot}")


def encode_time_slot(
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    priority: int,
    enabled: bool,
) -> tuple[int, int]:
    """Encode a time slot into its two register values (reg1, reg2)."""
    reg1 = (
        (start_minute & 0xFF)
        | ((start_hour & 0x1F) << 8)
        | ((priority & 0x3) << 13)
        | ((1 if enabled else 0) << 15)
    )
    reg2 = (end_minute & 0xFF) | ((end_hour & 0x1F) << 8)
    return reg1, reg2


def build_battery_module_registers(count: int) -> tuple[GrowattDeviceRegisters, ...]:
    """Generate per-module input registers for `count` parallel battery modules."""
    registers: list[GrowattDeviceRegisters] = []
    for module in range(1, count + 1):
        base = _MODULE_BLOCK_BASE + (module - 1) * _MODULE_BLOCK_SIZE + _MODULE_DATA_OFFSET
        for aggregate_addr, suffix, value_type, scale, signed in _BATTERY_MODULE_FIELDS:
            registers.append(
                GrowattDeviceRegisters(
                    name=f"battery_module_{module}_{suffix}",
                    register=base + (aggregate_addr - _MODULE_AGGREGATE_BASE),
                    value_type=value_type,
                    scale=scale,
                    signed=signed,
                )
            )
    return tuple(registers)
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
        name=ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST,
        register=3036,
        value_type=int,
        length=1
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
    # --- Writable command registers added in Protocol II V1.39 ---
    GrowattDeviceRegisters(
        name=ATTR_DRY_CONTACT_ENABLED, register=3016, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_GRID_FIRST_STOP_SOC, register=3037, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_ON_GRID_DISCHARGE_STOP_SOC, register=3067, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_TYPE, register=3070, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_PRE_PTO_ENABLED, register=3072, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_GENERATOR_CHARGE_ENABLED, register=3073, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_GENERATOR_FORCE, register=3074, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_UPS_FUNCTION_ENABLED, register=3079, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_UPS_OUTPUT_VOLTAGE, register=3080, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_UPS_OUTPUT_FREQUENCY, register=3081, value_type=int
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
        name=ATTR_BMS_TEMPERATURE_A, register=3176, value_type=float, signed=True
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_TEMPERATURE_B, register=3177, value_type=float, signed=True
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_PACK_NUMBER, register=3262, value_type=int
    ),
    # --- Telemetry registers added in Protocol II V1.39 ---
    GrowattDeviceRegisters(
        name=ATTR_SELF_CONSUMPTION_POWER, register=3121, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_SYSTEM_ENERGY_TODAY, register=3123, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_SYSTEM_ENERGY_TOTAL, register=3137, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_SELF_CONSUMPTION_ENERGY_TODAY, register=3139, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_SELF_CONSUMPTION_ENERGY_TOTAL, register=3141, value_type=float, length=2
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_VOLTAGE, register=3169, value_type=float, scale=100
    ),
    GrowattDeviceRegisters(
        name=ATTR_BATTERY_CURRENT, register=3170, value_type=float
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_MAX_SOC, register=3196, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_MIN_SOC, register=3197, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_PARALLEL_BATTERY_NUM, register=3198, value_type=int
    ),
    # --- Battery / BMS detail and fault registers (3165-3233 block) ---
    GrowattDeviceRegisters(
        name=ATTR_STORAGE_FAULT_CODE, register=3167, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_STORAGE_WARNING_CODE, register=3168, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_DERATE_REASON, register=3199, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_STATUS, register=3212, value_type=custom_function, function=bms_status
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_SOC, register=3215, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_MAX_CHARGE_CURRENT, register=3219, value_type=float, scale=100
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_MAX_DISCHARGE_CURRENT, register=3220, value_type=float, scale=100
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_CYCLE_COUNT, register=3221, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_SOH, register=3222, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_CELL_VOLTAGE_MAX, register=3230, value_type=float, scale=1000
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_CELL_VOLTAGE_MIN, register=3231, value_type=float, scale=1000
    ),
)