"""Result-key names for every decoded register value.

These are the keys the decoder writes into its result dict, and the keys the
entity descriptions look up. Split out of base.py so that importing the
register dataclass does not drag in 150 name constants.
"""
# Attribute names for values in the holding register
ATTR_FIRMWARE = "firmware"
ATTR_SERIAL_NUMBER = "serial number"
ATTR_INVERTER_MODEL = "Inverter model"

ATTR_DEVICE_TYPE_CODE = "device type code"
ATTR_NUMBER_OF_TRACKERS_AND_PHASES = "number of trackers and phases"

ATTR_MODBUS_VERSION = "modbus version"
ATTR_BATTERY_NUMBER_OF_MODULES = "battery_number_of_modules"

# Additional firmware versions (Storage holding registers)
ATTR_CONTROL_FIRMWARE = "control_firmware"  # holding 12-14
ATTR_BDC_FIRMWARE = "bdc_firmware"  # holding 3099-3101 (code + version)
ATTR_BMS_FIRMWARE = "bms_firmware"  # holding 3105

# Attribute names for values in the holding register (Storage)
ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST = "battery_discharge_rate_when_grid_first"
ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST = "battery_charge_rate_when_first"
ATTR_BATTERY_CHARGE_STOP_SOC = "battery_charge_stop_soc"
ATTR_INVERTER_ENABLED = "inverter_enabled"
ATTR_AC_CHARGE_ENABLED = "ac_charge_enabled"

# Writable command registers added in Protocol II V1.39 (Storage)
# Generic (non-mode-specific) battery charge/discharge stop SOC. The siblings
# above (3037/3048/3067) are mode-specific (Grid-First / Battery-First); these
# two carry no mode qualifier in the spec.
ATTR_BATTERY_GLOBAL_CHARGE_STOP_SOC = "battery_global_charge_stop_soc"  # holding 951 uwBatChargeStopSoc
ATTR_BATTERY_GLOBAL_DISCHARGE_STOP_SOC = "battery_global_discharge_stop_soc"  # holding 952 uwBatDisChargeStopSoc
ATTR_GRID_FIRST_STOP_SOC = "grid_first_stop_soc"  # holding 3037
ATTR_ON_GRID_DISCHARGE_STOP_SOC = "on_grid_discharge_stop_soc"  # holding 3067
ATTR_BATTERY_TYPE = "battery_type"  # holding 3070
ATTR_PRE_PTO_ENABLED = "pre_pto_enabled"  # holding 3072
ATTR_GENERATOR_CHARGE_ENABLED = "generator_charge_enabled"  # holding 3073
ATTR_GENERATOR_FORCE = "generator_force"  # holding 3074
ATTR_UPS_FUNCTION_ENABLED = "ups_function_enabled"  # holding 3079
ATTR_UPS_OUTPUT_VOLTAGE = "ups_output_voltage"  # holding 3080
ATTR_UPS_OUTPUT_FREQUENCY = "ups_output_frequency"  # holding 3081
ATTR_DRY_CONTACT_ENABLED = "dry_contact_enabled"  # holding 3016
ATTR_EXPORT_LIMIT_MODE = "export_limit_mode"  # holding 122
ATTR_EXPORT_LIMIT_RATE = "export_limit_rate"  # holding 123, 0.1% signed

# Peak shaving (holding 3306-3310). When SOC is above the reserved SOC the
# system runs in its originally-set mode; below it, the battery only supplies
# the load while the import limit is exceeded (see README).
ATTR_PEAK_SHAVING_MODE = "peak_shaving_mode"  # holding 3306, 0/1
ATTR_PEAK_SHAVING_IMPORT_LIMIT = "peak_shaving_import_limit"  # holding 3307, 0.1kW
ATTR_PEAK_SHAVING_EXPORT_LIMIT = "peak_shaving_export_limit"  # holding 3308, 0.1kW signed
ATTR_RESERVED_SOC_FOR_PEAK_SHAVING_ENABLE = "reserved_soc_for_peak_shaving_enable"  # holding 3309, 0/1
ATTR_RESERVED_SOC_FOR_PEAK_SHAVING = "reserved_soc_for_peak_shaving"  # holding 3310, % 0-100

# Nameplate / rated values (read-only config registers).
ATTR_INVERTER_RATED_POWER = "inverter_rated_power"  # holding 6-7 (Pmax), 0.1VA
ATTR_RATED_CELL_CAPACITY = "rated_cell_capacity"  # holding 3119, 1Ah
# Holding 3121, APX only; the spec documents no unit, so the raw value is shown.
ATTR_RATED_BATTERY_CAPACITY = "rated_battery_capacity"

# Telemetry registers added in Protocol II V1.39 (Storage input)
ATTR_BATTERY_VOLTAGE = "battery_voltage"  # input 3169, 0.01V
ATTR_BATTERY_CURRENT = "battery_current"  # input 3170, 0.1A
ATTR_SELF_CONSUMPTION_POWER = "self_consumption_power"  # input 3121, 0.1W
ATTR_SYSTEM_ENERGY_TODAY = "system_energy_today"  # input 3123, 0.1kWh
ATTR_SYSTEM_ENERGY_TOTAL = "system_energy_total"  # input 3137, 0.1kWh
ATTR_SELF_CONSUMPTION_ENERGY_TODAY = "self_consumption_energy_today"  # input 3139
ATTR_SELF_CONSUMPTION_ENERGY_TOTAL = "self_consumption_energy_total"  # input 3141
ATTR_BMS_MAX_SOC = "bms_max_soc"  # input 3196, %
ATTR_BMS_MIN_SOC = "bms_min_soc"  # input 3197, %
ATTR_PARALLEL_BATTERY_NUM = "parallel_battery_num"  # input 3198

# Battery / BMS detail and fault registers (Storage input, 3165-3233 block)
ATTR_STORAGE_FAULT_CODE = "storage_fault_code"  # input 3167
ATTR_STORAGE_WARNING_CODE = "storage_warning_code"  # input 3168
ATTR_BMS_DERATE_REASON = "bms_derate_reason"  # input 3199
ATTR_BMS_STATUS = "bms_status"  # input 3212
ATTR_BMS_SOC = "bms_soc"  # input 3215, %
ATTR_BMS_MAX_CHARGE_CURRENT = "bms_max_charge_current"  # input 3219, 0.01A
ATTR_BMS_MAX_DISCHARGE_CURRENT = "bms_max_discharge_current"  # input 3220, 0.01A
ATTR_BMS_CYCLE_COUNT = "bms_cycle_count"  # input 3221
ATTR_BMS_SOH = "bms_soh"  # input 3222, %
ATTR_BMS_CELL_VOLTAGE_MAX = "bms_cell_voltage_max"  # input 3230, 0.001V
ATTR_BMS_CELL_VOLTAGE_MIN = "bms_cell_voltage_min"  # input 3231, 0.001V

# Attribute names for values in the input register

ATTR_STATUS = "status"
ATTR_STATUS_CODE = "status_code"
ATTR_DERATING_MODE = "derating_mode"
ATTR_FAULT_CODE = "fault_code"
ATTR_WARNING_CODE = "warning_code"
ATTR_WARNING_VALUE = "warning_value"

ATTR_INPUT_POWER = "input_power"  # W
ATTR_INPUT_ENERGY_TOTAL = "input_energy_total"  # kWh

ATTR_INPUT_1_VOLTAGE = "input_1_voltage"  # V
ATTR_INPUT_1_AMPERAGE = "input_1_amperage"  # A
ATTR_INPUT_1_POWER = "input_1_power"  # W
ATTR_INPUT_1_ENERGY_TODAY = "input_1_energy_today"  # kWh
ATTR_INPUT_1_ENERGY_TOTAL = "input_1_energy_total"  # kWh

ATTR_INPUT_2_VOLTAGE = "input_2_voltage"  # V
ATTR_INPUT_2_AMPERAGE = "input_2_amperage"  # A
ATTR_INPUT_2_POWER = "input_2_power"  # W
ATTR_INPUT_2_ENERGY_TODAY = "input_2_energy_today"  # kWh
ATTR_INPUT_2_ENERGY_TOTAL = "input_2_energy_total"  # kWh

ATTR_INPUT_3_VOLTAGE = "input_3_voltage"  # V
ATTR_INPUT_3_AMPERAGE = "input_3_amperage"  # A
ATTR_INPUT_3_POWER = "input_3_power"  # W
ATTR_INPUT_3_ENERGY_TODAY = "input_3_energy_today"  # kWh
ATTR_INPUT_3_ENERGY_TOTAL = "input_3_energy_total"  # kWh

ATTR_INPUT_4_VOLTAGE = "input_4_voltage"  # V
ATTR_INPUT_4_AMPERAGE = "input_4_amperage"  # A
ATTR_INPUT_4_POWER = "input_4_power"  # W
ATTR_INPUT_4_ENERGY_TODAY = "input_4_energy_today"  # kWh
ATTR_INPUT_4_ENERGY_TOTAL = "input_4_energy_total"  # kWh

ATTR_INPUT_5_VOLTAGE = "input_5_voltage"  # V
ATTR_INPUT_5_AMPERAGE = "input_5_amperage"  # A
ATTR_INPUT_5_POWER = "input_5_power"  # W
ATTR_INPUT_5_ENERGY_TODAY = "input_5_energy_today"  # kWh
ATTR_INPUT_5_ENERGY_TOTAL = "input_5_energy_total"  # kWh

ATTR_INPUT_6_VOLTAGE = "input_6_voltage"  # V
ATTR_INPUT_6_AMPERAGE = "input_6_amperage"  # A
ATTR_INPUT_6_POWER = "input_6_power"  # W
ATTR_INPUT_6_ENERGY_TODAY = "input_6_energy_today"  # kWh
ATTR_INPUT_6_ENERGY_TOTAL = "input_6_energy_total"  # kWh

ATTR_INPUT_7_VOLTAGE = "input_7_voltage"  # V
ATTR_INPUT_7_AMPERAGE = "input_7_amperage"  # A
ATTR_INPUT_7_POWER = "input_7_power"  # W
ATTR_INPUT_7_ENERGY_TODAY = "input_7_energy_today"  # kWh
ATTR_INPUT_7_ENERGY_TOTAL = "input_7_energy_total"  # kWh

ATTR_INPUT_8_VOLTAGE = "input_8_voltage"  # V
ATTR_INPUT_8_AMPERAGE = "input_8_amperage"  # A
ATTR_INPUT_8_POWER = "input_8_power"  # W
ATTR_INPUT_8_ENERGY_TODAY = "input_8_energy_today"  # kWh
ATTR_INPUT_8_ENERGY_TOTAL = "input_8_energy_total"  # kWh

ATTR_OUTPUT_POWER = "output_power"  # W
ATTR_OUTPUT_ENERGY_TODAY = "output_energy_today"  # kWh
ATTR_OUTPUT_ENERGY_TOTAL = "output_energy_total"  # kWh

ATTR_OUTPUT_REACTIVE_POWER = "output_reactive_power"  # Var
ATTR_OUTPUT_REACTIVE_ENERGY_TODAY = "output_reactive_energy_today"  # kVarh
ATTR_OUTPUT_REACTIVE_ENERGY_TOTAL = "output_reactive_energy_total"  # kVarh

ATTR_OUTPUT_1_VOLTAGE = "output_1_voltage"  # V
ATTR_OUTPUT_1_AMPERAGE = "output_1_amperage"  # A
ATTR_OUTPUT_1_POWER = "output_1_power"  # W

ATTR_OUTPUT_2_VOLTAGE = "output_2_voltage"  # V
ATTR_OUTPUT_2_AMPERAGE = "output_2_amperage"  # A
ATTR_OUTPUT_2_POWER = "output_2_power"  # W

ATTR_OUTPUT_3_VOLTAGE = "output_3_voltage"  # V
ATTR_OUTPUT_3_AMPERAGE = "output_3_amperage"  # A
ATTR_OUTPUT_3_POWER = "output_3_power"  # W

ATTR_OPERATION_HOURS = "operation_hours"  # s

ATTR_FREQUENCY = "frequency"  # Hz

ATTR_TEMPERATURE = "inverter_temperature"  # C
ATTR_IPM_TEMPERATURE = "ipm_temperature"  # C
ATTR_BOOST_TEMPERATURE = "boost_temperature"  # C

ATTR_P_BUS_VOLTAGE = "p_bus_voltage"  # V
ATTR_N_BUS_VOLTAGE = "n_bus_voltage"  # V

ATTR_OUTPUT_PERCENTAGE = "real_output_power_percent"  # %

ATTR_AC_CHARGE_ENERGY_TODAY = "battery_ac_charge_energy_today" # kWh
ATTR_AC_CHARGE_ENERGY_TOTAL = "battery_AC_charge_energy_total"  # kWh

# Attribute names for values in the input register Storage
ATTR_INVERTER_STATUS = "inverter_status"
ATTR_INVERTER_MODE = "inverter mode"
ATTR_BDC_DATA_FLAG= "bdc_data_flag"
ATTR_BDC_DERATING_MODE = "bdc_derating_mode"
ATTR_SOC_PERCENTAGE = "soc"  # %
ATTR_DISCHARGE_POWER = "discharge_power"  # W
ATTR_CHARGE_POWER = "charge_power"  # W
ATTR_ENERGY_TO_USER_TODAY = "energy_to_user_today"  # kWh
ATTR_ENERGY_TO_USER_TOTAL = "energy_to_user_total"  # kWh
ATTR_ENERGY_TO_GRID_TODAY = "energy_to_grid_today"  # kWh
ATTR_ENERGY_TO_GRID_TOTAL = "energy_to_grid_total"  # kWh
ATTR_DISCHARGE_ENERGY_TODAY = "discharge_energy_today"  # kWh
ATTR_DISCHARGE_ENERGY_TOTAL = "discharge_energy_total"  # kWh
ATTR_CHARGE_ENERGY_TODAY = "charge_energy_today"  # kWh
ATTR_CHARGE_ENERGY_TOTAL = "charge_energy_total"  # kWh
ATTR_METER_POWER_NETTO = "meter_power_netto" # W
ATTR_BATTERY_PACK_NUMBER = "battery_pack_number"
ATTR_BMS_TEMPERATURE_A = "bms_temperature_a" # C
ATTR_BMS_TEMPERATURE_B = "bms_temperature_b" # C


__all__ = [
    "ATTR_AC_CHARGE_ENABLED",
    "ATTR_AC_CHARGE_ENERGY_TODAY",
    "ATTR_AC_CHARGE_ENERGY_TOTAL",
    "ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST",
    "ATTR_BATTERY_CHARGE_STOP_SOC",
    "ATTR_BATTERY_CURRENT",
    "ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST",
    "ATTR_BATTERY_GLOBAL_CHARGE_STOP_SOC",
    "ATTR_BATTERY_GLOBAL_DISCHARGE_STOP_SOC",
    "ATTR_BATTERY_NUMBER_OF_MODULES",
    "ATTR_BATTERY_PACK_NUMBER",
    "ATTR_BATTERY_TYPE",
    "ATTR_BATTERY_VOLTAGE",
    "ATTR_BDC_DATA_FLAG",
    "ATTR_BDC_DERATING_MODE",
    "ATTR_BDC_FIRMWARE",
    "ATTR_BMS_CELL_VOLTAGE_MAX",
    "ATTR_BMS_CELL_VOLTAGE_MIN",
    "ATTR_BMS_CYCLE_COUNT",
    "ATTR_BMS_DERATE_REASON",
    "ATTR_BMS_FIRMWARE",
    "ATTR_BMS_MAX_CHARGE_CURRENT",
    "ATTR_BMS_MAX_DISCHARGE_CURRENT",
    "ATTR_BMS_MAX_SOC",
    "ATTR_BMS_MIN_SOC",
    "ATTR_BMS_SOC",
    "ATTR_BMS_SOH",
    "ATTR_BMS_STATUS",
    "ATTR_BMS_TEMPERATURE_A",
    "ATTR_BMS_TEMPERATURE_B",
    "ATTR_BOOST_TEMPERATURE",
    "ATTR_CHARGE_ENERGY_TODAY",
    "ATTR_CHARGE_ENERGY_TOTAL",
    "ATTR_CHARGE_POWER",
    "ATTR_CONTROL_FIRMWARE",
    "ATTR_DERATING_MODE",
    "ATTR_DEVICE_TYPE_CODE",
    "ATTR_DISCHARGE_ENERGY_TODAY",
    "ATTR_DISCHARGE_ENERGY_TOTAL",
    "ATTR_DISCHARGE_POWER",
    "ATTR_DRY_CONTACT_ENABLED",
    "ATTR_ENERGY_TO_GRID_TODAY",
    "ATTR_ENERGY_TO_GRID_TOTAL",
    "ATTR_ENERGY_TO_USER_TODAY",
    "ATTR_ENERGY_TO_USER_TOTAL",
    "ATTR_EXPORT_LIMIT_MODE",
    "ATTR_EXPORT_LIMIT_RATE",
    "ATTR_FAULT_CODE",
    "ATTR_FIRMWARE",
    "ATTR_FREQUENCY",
    "ATTR_GENERATOR_CHARGE_ENABLED",
    "ATTR_GENERATOR_FORCE",
    "ATTR_GRID_FIRST_STOP_SOC",
    "ATTR_INPUT_1_AMPERAGE",
    "ATTR_INPUT_1_ENERGY_TODAY",
    "ATTR_INPUT_1_ENERGY_TOTAL",
    "ATTR_INPUT_1_POWER",
    "ATTR_INPUT_1_VOLTAGE",
    "ATTR_INPUT_2_AMPERAGE",
    "ATTR_INPUT_2_ENERGY_TODAY",
    "ATTR_INPUT_2_ENERGY_TOTAL",
    "ATTR_INPUT_2_POWER",
    "ATTR_INPUT_2_VOLTAGE",
    "ATTR_INPUT_3_AMPERAGE",
    "ATTR_INPUT_3_ENERGY_TODAY",
    "ATTR_INPUT_3_ENERGY_TOTAL",
    "ATTR_INPUT_3_POWER",
    "ATTR_INPUT_3_VOLTAGE",
    "ATTR_INPUT_4_AMPERAGE",
    "ATTR_INPUT_4_ENERGY_TODAY",
    "ATTR_INPUT_4_ENERGY_TOTAL",
    "ATTR_INPUT_4_POWER",
    "ATTR_INPUT_4_VOLTAGE",
    "ATTR_INPUT_5_AMPERAGE",
    "ATTR_INPUT_5_ENERGY_TODAY",
    "ATTR_INPUT_5_ENERGY_TOTAL",
    "ATTR_INPUT_5_POWER",
    "ATTR_INPUT_5_VOLTAGE",
    "ATTR_INPUT_6_AMPERAGE",
    "ATTR_INPUT_6_ENERGY_TODAY",
    "ATTR_INPUT_6_ENERGY_TOTAL",
    "ATTR_INPUT_6_POWER",
    "ATTR_INPUT_6_VOLTAGE",
    "ATTR_INPUT_7_AMPERAGE",
    "ATTR_INPUT_7_ENERGY_TODAY",
    "ATTR_INPUT_7_ENERGY_TOTAL",
    "ATTR_INPUT_7_POWER",
    "ATTR_INPUT_7_VOLTAGE",
    "ATTR_INPUT_8_AMPERAGE",
    "ATTR_INPUT_8_ENERGY_TODAY",
    "ATTR_INPUT_8_ENERGY_TOTAL",
    "ATTR_INPUT_8_POWER",
    "ATTR_INPUT_8_VOLTAGE",
    "ATTR_INPUT_ENERGY_TOTAL",
    "ATTR_INPUT_POWER",
    "ATTR_INVERTER_ENABLED",
    "ATTR_INVERTER_MODE",
    "ATTR_INVERTER_MODEL",
    "ATTR_INVERTER_RATED_POWER",
    "ATTR_INVERTER_STATUS",
    "ATTR_IPM_TEMPERATURE",
    "ATTR_METER_POWER_NETTO",
    "ATTR_MODBUS_VERSION",
    "ATTR_NUMBER_OF_TRACKERS_AND_PHASES",
    "ATTR_N_BUS_VOLTAGE",
    "ATTR_ON_GRID_DISCHARGE_STOP_SOC",
    "ATTR_OPERATION_HOURS",
    "ATTR_OUTPUT_1_AMPERAGE",
    "ATTR_OUTPUT_1_POWER",
    "ATTR_OUTPUT_1_VOLTAGE",
    "ATTR_OUTPUT_2_AMPERAGE",
    "ATTR_OUTPUT_2_POWER",
    "ATTR_OUTPUT_2_VOLTAGE",
    "ATTR_OUTPUT_3_AMPERAGE",
    "ATTR_OUTPUT_3_POWER",
    "ATTR_OUTPUT_3_VOLTAGE",
    "ATTR_OUTPUT_ENERGY_TODAY",
    "ATTR_OUTPUT_ENERGY_TOTAL",
    "ATTR_OUTPUT_PERCENTAGE",
    "ATTR_OUTPUT_POWER",
    "ATTR_OUTPUT_REACTIVE_ENERGY_TODAY",
    "ATTR_OUTPUT_REACTIVE_ENERGY_TOTAL",
    "ATTR_OUTPUT_REACTIVE_POWER",
    "ATTR_PARALLEL_BATTERY_NUM",
    "ATTR_PEAK_SHAVING_EXPORT_LIMIT",
    "ATTR_PEAK_SHAVING_IMPORT_LIMIT",
    "ATTR_PEAK_SHAVING_MODE",
    "ATTR_PRE_PTO_ENABLED",
    "ATTR_P_BUS_VOLTAGE",
    "ATTR_RATED_BATTERY_CAPACITY",
    "ATTR_RATED_CELL_CAPACITY",
    "ATTR_RESERVED_SOC_FOR_PEAK_SHAVING",
    "ATTR_RESERVED_SOC_FOR_PEAK_SHAVING_ENABLE",
    "ATTR_SELF_CONSUMPTION_ENERGY_TODAY",
    "ATTR_SELF_CONSUMPTION_ENERGY_TOTAL",
    "ATTR_SELF_CONSUMPTION_POWER",
    "ATTR_SERIAL_NUMBER",
    "ATTR_SOC_PERCENTAGE",
    "ATTR_STATUS",
    "ATTR_STATUS_CODE",
    "ATTR_STORAGE_FAULT_CODE",
    "ATTR_STORAGE_WARNING_CODE",
    "ATTR_SYSTEM_ENERGY_TODAY",
    "ATTR_SYSTEM_ENERGY_TOTAL",
    "ATTR_TEMPERATURE",
    "ATTR_UPS_FUNCTION_ENABLED",
    "ATTR_UPS_OUTPUT_FREQUENCY",
    "ATTR_UPS_OUTPUT_VOLTAGE",
    "ATTR_WARNING_CODE",
    "ATTR_WARNING_VALUE",
]
