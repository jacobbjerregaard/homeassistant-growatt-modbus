"""Device defaults for a Growatt Inverter."""
from .base import (
    GrowattDeviceRegisters,
    custom_function,
    FIRMWARE_REGISTER,
    DEVICE_TYPE_CODE_REGISTER,
    NUMBER_OF_TRACKERS_AND_PHASES_REGISTER,
    ATTR_BATTERY_NUMBER_OF_MODULES,
    ATTR_INVERTER_MODEL,
    ATTR_INVERTER_RATED_POWER,
    ATTR_RATED_CELL_CAPACITY,
    ATTR_RATED_BATTERY_CAPACITY,
    ATTR_MODBUS_VERSION,
    ATTR_CONTROL_FIRMWARE,
    ATTR_BDC_FIRMWARE,
    ATTR_BMS_FIRMWARE,
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
    ATTR_EXPORT_LIMIT_MODE,
    ATTR_EXPORT_LIMIT_RATE,
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


_BMS_STATUSES = {
    0: "Dormancy",
    1: "Charging",
    2: "Discharging",
    3: "Free",
    4: "Standby",
    5: "Soft start",
    6: "Fault",
    7: "Update",
}
BMS_STATUS_OPTIONS = [*_BMS_STATUSES.values(), "Unknown"]


def bms_status(register) -> str:
    return _BMS_STATUSES.get(register, "Unknown")


# Per-module info block ("Special for APX", holding registers): battery module n
# occupies 40 registers at 5400 + (n-1)*40, the first 8 of which are the 16-char
# serial number. The protocol exposes per-module *identity* here (serial,
# software versions, manufacturer) but no per-module live telemetry - the live
# voltage/temperature/SOC values are battery-system aggregates (3165-3233 block).
_MODULE_INFO_BASE = 5400
_MODULE_INFO_STRIDE = 40
_MODULE_SERIAL_LENGTH = 8  # registers (16 ASCII characters)

# Holding register reporting the number of battery modules.
BATTERY_MODULE_COUNT_REGISTER = 185

# Per-module live telemetry block (input registers, "Special for APX"): module n
# occupies 40 registers at 5080 + (n-1)*40 with the same layout as 5080-5119.
_MODULE_TELEMETRY_BASE = 5080
_MODULE_TELEMETRY_STRIDE = 40


_BAT_SYS_STATES = {
    0: "Initialize",
    1: "Standby",
    2: "Charging",
    3: "Discharging",
    4: "Shutdown",
    5: "Fault",
    6: "Update",
}
BAT_SYS_STATE_OPTIONS = [*_BAT_SYS_STATES.values(), "Unknown"]


def bat_sys_state(register) -> str:
    return _BAT_SYS_STATES.get(register, "Unknown")


def bat_soc(register) -> int:  # SOC is replicated in both bytes (Bit15-8 / Bit7-0)
    return register & 0xFF


def bat_soh(register) -> int:  # Bit6-0 = SOH; bit7 = scrap flag
    return register & 0x7F


_BALANCE_STATES = {
    0: "Not balancing",
    1: "Bottom end requested",
    2: "Top requested",
    3: "Charge terminal requested",
    4: "Even channels (parity limited)",
    5: "Odd channels (parity limited)",
    6: "Closed (incomplete)",
    7: "Parity channels (unlimited)",
    8: "Complete",
}


BALANCE_STATE_OPTIONS = [*_BALANCE_STATES.values(), "Unknown"]


def bat_balance_state(register) -> dict:  # Bit15-8 state; Bit7-0 balance time (h)
    state = (register >> 8) & 0xFF
    return {
        "state": _BALANCE_STATES.get(state, "Unknown"),
        "time_hours": register & 0xFF,
    }


def bat_subcode(register) -> dict:
    # Bit0 charge-enable, Bit1 discharge-enable, Bit8-11 warning subcode,
    # Bit12-15 fault subcode.
    return {
        "charge_enabled": (register >> 0) & 0x1,
        "discharge_enabled": (register >> 1) & 0x1,
        "warning_subcode": (register >> 8) & 0xF,
        "fault_subcode": (register >> 12) & 0xF,
    }


def bat_internal_state(register) -> dict:
    # Bit15-8 internal short-circuit condition; Bit7-0 SOX correction status.
    return {
        "short_circuit": (register >> 8) & 0xFF,
        "sox_correction": register & 0xFF,
    }


# Per-module (5110) derating enumeration. Distinct from the pack-level
# bdc_derating_mode (register 3165), which uses a different numbering.
_MODULE_DERATING_MODES = {
    0: "No derating",
    1: "Fault",
    17: "Max battery discharge current",
    18: "Battery discharge enabled",
    19: "Bus voltage too high",
    20: "Discharge NTC high temperature",
    21: "Discharge system alarm",
    22: "Discharge upper computer settings",
}


MODULE_DERATING_OPTIONS = [*dict.fromkeys(_MODULE_DERATING_MODES.values()), "Reserved", "Unknown"]


def module_derating_mode(register) -> str:
    if 23 <= register <= 32:
        return "Reserved"
    return _MODULE_DERATING_MODES.get(register, "Unknown")


# Decode functions that expand one register into several named values; the
# tuple lists the result-key suffixes each produces (kept in sync with the
# dict returned by the function above).
_MULTI_VALUE_DECODERS = {
    bat_balance_state: ("state", "time_hours"),
    bat_subcode: ("charge_enabled", "discharge_enabled", "warning_subcode", "fault_subcode"),
    bat_internal_state: ("short_circuit", "sox_correction"),
}


# (offset from block start, name suffix, value_type, scale, length, signed, function)
_MODULE_TELEMETRY_FIELDS = (
    (0, "system_state", custom_function, 1, 1, False, bat_sys_state),  # 5080
    (1, "soc", custom_function, 1, 1, False, bat_soc),         # 5081 BatSOC, %
    (2, "soh", custom_function, 1, 1, False, bat_soh),         # 5082 BatSOH, %
    (3, "voltage", float, 10, 1, False, None),                # 5083 BatVolt, 0.1V
    (4, "current", float, 10, 1, True, None),                 # 5084 BatCurrent, 0.1A
    (5, "power", int, 1, 1, True, None),                      # 5085 BatPower, 1W
    (6, "discharge_energy_total", float, 10, 2, False, None), # 5086-5087, 0.1kWh
    (8, "cell_voltage_max", float, 1000, 1, False, None),     # 5088, 0.001V
    (9, "cell_voltage_min", float, 1000, 1, False, None),     # 5089, 0.001V
    (10, "temperature_max", float, 10, 1, True, None),        # 5090 BatMaxTemp, 0.1C
    (11, "temperature_min", float, 10, 1, True, None),        # 5091 BatMinTemp, 0.1C
    (14, "balance", custom_function, 1, 1, False, bat_balance_state),  # 5094 state + h
    (15, "cell_capacity", float, 10, 1, False, None),         # 5095 BatCellCapacity, 0.1Ah
    (17, "fault_code", int, 1, 1, False, None),               # 5097 BatFaultCode
    (18, "warning_code", int, 1, 1, False, None),             # 5098 BatWarningCode
    (19, "flags", custom_function, 1, 1, False, bat_subcode), # 5099 BatSubCode bitfield
    (20, "charge_energy_total", float, 10, 2, False, None),   # 5100-5101, 0.1kWh
    (22, "discharge_capacity_total", float, 100, 2, False, None),  # 5102-5103, 0.01Ah
    (24, "charge_capacity_total", float, 100, 2, False, None),     # 5104-5105, 0.01Ah
    (26, "cell_capacity_min", float, 10, 1, False, None),     # 5106 BatMinCellCapacity, 0.1Ah
    (27, "ah_integral", float, 10, 1, False, None),           # 5107 BatAHIntegralValue, 0.1Ah
    (28, "cycle_count", float, 10, 1, False, None),           # 5108 BatCyclesNumber, 0.1Cyc
    (29, "internal", custom_function, 1, 1, False, bat_internal_state),  # 5109 BatInternalState
    (30, "derating_mode", custom_function, 1, 1, False, module_derating_mode),  # 5110 BDCDeratingMode
)


def build_battery_module_input_registers(count: int) -> tuple[GrowattDeviceRegisters, ...]:
    """Generate per-module live telemetry input registers for `count` modules."""
    registers: list[GrowattDeviceRegisters] = []
    for module in range(1, count + 1):
        base = _MODULE_TELEMETRY_BASE + (module - 1) * _MODULE_TELEMETRY_STRIDE
        for offset, suffix, value_type, scale, length, signed, function in _MODULE_TELEMETRY_FIELDS:
            name = f"battery_module_{module}_{suffix}"
            value_names = tuple(
                f"{name}_{sub}" for sub in _MULTI_VALUE_DECODERS.get(function, ())
            )
            registers.append(
                GrowattDeviceRegisters(
                    name=name,
                    register=base + offset,
                    value_type=value_type,
                    scale=scale,
                    length=length,
                    signed=signed,
                    function=function,
                    value_names=value_names,
                )
            )
    return tuple(registers)


def decode_ascii(registers) -> str:
    """Decode register words to an ASCII string, dropping NUL padding.

    Only NUL bytes (0x00) are treated as padding. A meaningful trailing space
    or other whitespace is part of the value (e.g. a 5-character firmware whose
    last character is a space) and must be preserved.
    """
    chars: list[str] = []
    for value in registers:
        if value is None:
            continue
        chars.append(chr(value >> 8))
        chars.append(chr(value & 0x00FF))
    return "".join(chars).replace("\x00", "")


def firmware_code_version(registers) -> str:
    """Combine an ASCII firmware code (leading words) with its version number.

    e.g. registers [3099, 3100, 3101] -> "<code>-<version>", where the code is
    the ASCII of all-but-last words and the version is the last word's value.
    """
    code = decode_ascii(registers[:-1])
    version = registers[-1]
    if version is None:
        return code
    return f"{code}-{version}" if code else str(version)


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


def decode_time_slot(reg1: int, reg2: int) -> dict:
    """Decode a slot register pair into its fields."""
    return {
        "start_hour": (reg1 >> 8) & 0x1F,
        "start_minute": reg1 & 0xFF,
        "end_hour": (reg2 >> 8) & 0x1F,
        "end_minute": reg2 & 0xFF,
        "priority": (reg1 >> 13) & 0x3,
        "enabled": bool((reg1 >> 15) & 0x1),
    }


def apply_time_slot_field(reg1: int, reg2: int, **changes) -> tuple[int, int]:
    """Return new (reg1, reg2) with `changes` applied to the decoded fields."""
    fields = decode_time_slot(reg1, reg2)
    fields.update(changes)
    return encode_time_slot(
        fields["start_hour"],
        fields["start_minute"],
        fields["end_hour"],
        fields["end_minute"],
        fields["priority"],
        fields["enabled"],
    )


def build_time_slot_registers(count: int) -> tuple[GrowattDeviceRegisters, ...]:
    """Raw register pair (word1/word2) for each of `count` time-of-use slots."""
    registers: list[GrowattDeviceRegisters] = []
    for slot in range(1, count + 1):
        base = time_slot_register(slot)
        registers.extend(
            (
                GrowattDeviceRegisters(name=f"tou_slot_{slot}_word1", register=base, value_type=int),
                GrowattDeviceRegisters(name=f"tou_slot_{slot}_word2", register=base + 1, value_type=int),
            )
        )
    return tuple(registers)


def build_battery_module_registers(count: int) -> tuple[GrowattDeviceRegisters, ...]:
    """Generate per-module serial-number registers for `count` battery modules.

    Surfacing the serial lets each physical module be tracked over time even
    though the protocol has no per-module live telemetry.
    """
    registers: list[GrowattDeviceRegisters] = []
    for module in range(1, count + 1):
        base = _MODULE_INFO_BASE + (module - 1) * _MODULE_INFO_STRIDE
        registers.extend(
            (
                GrowattDeviceRegisters(
                    name=f"battery_module_{module}_serial_number",
                    register=base,  # 5400: serial number (8 words)
                    value_type=custom_function,
                    length=_MODULE_SERIAL_LENGTH,
                    function=decode_ascii,
                ),
                GrowattDeviceRegisters(
                    name=f"battery_module_{module}_dsp_firmware",
                    register=base + 8,  # 5408-5409 code + 5410 version
                    value_type=custom_function,
                    length=3,
                    function=firmware_code_version,
                ),
                GrowattDeviceRegisters(
                    name=f"battery_module_{module}_mcu_firmware",
                    register=base + 11,  # 5411-5412 code + 5413 version
                    value_type=custom_function,
                    length=3,
                    function=firmware_code_version,
                ),
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

# Battery derating mode (input register 3165), per V1.39 "Table 2".
_BDC_DERATING_MODES = {
    0: "Normal, unrestricted",
    1: "System fault",
    2: "System warning",
    3: "Maximum charging current of battery (charge)",
    4: "Battery high temperature (charge)",
    5: "Reserved (charge)",
    6: "SOC setting limits (charge)",
    7: "Battery low temperature (charge)",
    8: "High bus voltage (charge)",
    9: "Full charged (charge)",
    10: "Reserved (charge)",
    11: "System warning, no charging (charge)",
    12: "User-set charging current (charge)",
    13: "BM charge current limited (charge)",
    14: "Reserved (charge)",
    15: "Reserved (charge)",
    16: "Reserved (charge)",
    17: "Maximum battery current limit (discharge)",
    18: "Battery discharge enable (discharge)",
    19: "High bus discharge derating (discharge)",
    20: "High temperature discharge derating (discharge)",
    21: "System warning, no discharge (discharge)",
    22: "User-set discharging current (discharge)",
    23: "BM discharge current limited (discharge)",
}


# Several codes share the "Reserved (...)" label, so dedupe while preserving order.
# Codes 24-32 add "Reserved (discharge)", which is not a dict value.
BDC_DERATING_OPTIONS = [
    *dict.fromkeys(_BDC_DERATING_MODES.values()),
    "Reserved (discharge)",
    "Unknown",
]


def bdc_derating_mode(register) -> str:
    if 24 <= register <= 32:
        return "Reserved (discharge)"
    return _BDC_DERATING_MODES.get(register, "Unknown")



def netto_meter_energy(registers) -> float:
    production = (registers[0] * 65536.0 + registers[1])* 0.1
    consumption = (registers[2] * 65536.0 + registers[3]) * 0.1 

    return production - consumption


STORAGE_HOLDING_REGISTERS_120: tuple[GrowattDeviceRegisters, ...] = (
    FIRMWARE_REGISTER,
    SERIAL_NUMBER_REGISTER,
    # --- Additional firmware readouts ---
    GrowattDeviceRegisters(
        name=ATTR_CONTROL_FIRMWARE, register=12, value_type=custom_function,
        length=3, function=decode_ascii
    ),
    GrowattDeviceRegisters(
        name=ATTR_BDC_FIRMWARE, register=3099, value_type=custom_function,
        length=3, function=firmware_code_version  # 3099-3100 code + 3101 version
    ),
    GrowattDeviceRegisters(
        name=ATTR_BMS_FIRMWARE, register=3105, value_type=int
    ),
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
    # Nameplate / rated values (read-only).
    GrowattDeviceRegisters(
        name=ATTR_INVERTER_RATED_POWER,  # holding 6-7 PmaxH/PmaxL, 0.1VA
        register=6,
        value_type=float,
        length=2,
        scale=10,
    ),
    GrowattDeviceRegisters(
        name=ATTR_RATED_CELL_CAPACITY,  # holding 3119, 1Ah
        register=3119,
        value_type=int,
    ),
    GrowattDeviceRegisters(
        name=ATTR_RATED_BATTERY_CAPACITY,  # holding 3121, APX only, raw
        register=3121,
        value_type=int,
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
    GrowattDeviceRegisters(
        name=ATTR_EXPORT_LIMIT_MODE, register=122, value_type=int
    ),
    GrowattDeviceRegisters(
        name=ATTR_EXPORT_LIMIT_RATE, register=123, value_type=float, scale=10, signed=True
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
        name=ATTR_BATTERY_CURRENT, register=3170, value_type=float, signed=True
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