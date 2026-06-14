"""Growatt Sensor definitions for the Inverter type."""
from __future__ import annotations
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    EntityCategory,
    PERCENTAGE,
)
from .sensor_entity_description import GrowattSensorEntityDescription
from .switch_entity_description import GrowattSwitchEntityDescription
from .number_entity_description import GrowattNumberEntityDescription
from .select_entity_description import GrowattSelectEntityDescription
from ..API.device_type.base import (
    ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST,
    ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST,
    ATTR_BATTERY_CHARGE_STOP_SOC,
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
    ATTR_METER_POWER_NETTO,
    ATTR_INVERTER_STATUS,
    ATTR_INVERTER_MODE,
    ATTR_BDC_DATA_FLAG,
    ATTR_BDC_DERATING_MODE,
    ATTR_BMS_TEMPERATURE_A,
    ATTR_BMS_TEMPERATURE_B,
    ATTR_BATTERY_PACK_NUMBER,
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
    ATTR_FIRMWARE,
    ATTR_CONTROL_FIRMWARE,
    ATTR_BDC_FIRMWARE,
    ATTR_BMS_FIRMWARE,
)
STORAGE_SWITCH_TYPES: tuple[GrowattSwitchEntityDescription, ...] = (
    GrowattSwitchEntityDescription(
        key=ATTR_AC_CHARGE_ENABLED,
        name="AC Charge"
    ),
    GrowattSwitchEntityDescription(
        key=ATTR_PRE_PTO_ENABLED,
        name="Pre-PTO",
    ),
    GrowattSwitchEntityDescription(
        key=ATTR_GENERATOR_CHARGE_ENABLED,
        name="Generator Charge",
    ),
    GrowattSwitchEntityDescription(
        key=ATTR_UPS_FUNCTION_ENABLED,
        name="UPS Function",
    ),
    GrowattSwitchEntityDescription(
        key=ATTR_DRY_CONTACT_ENABLED,
        name="Dry Contact",
    ),
)

STORAGE_NUMBER_TYPES: tuple[GrowattNumberEntityDescription, ...] = (
    GrowattNumberEntityDescription(
        key=ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST,
        name="Battery Discharge Rate when Grid First",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key=ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST,
        name="Battery Charge Rate when Battery First",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key=ATTR_BATTERY_CHARGE_STOP_SOC,
        name="Battery Stop Charge SOC when Battery First",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key=ATTR_GRID_FIRST_STOP_SOC,
        name="Stop Discharge SOC when Grid First",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattNumberEntityDescription(
        key=ATTR_ON_GRID_DISCHARGE_STOP_SOC,
        name="On-Grid Stop Discharge SOC",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

STORAGE_SELECT_TYPES: tuple[GrowattSelectEntityDescription, ...] = (
    GrowattSelectEntityDescription(
        key=ATTR_BATTERY_TYPE,
        name="Battery Type",
        options_map={"Lithium": 0, "Lead-acid": 1, "Other": 2},
    ),
    GrowattSelectEntityDescription(
        key=ATTR_GENERATOR_FORCE,
        name="Generator Force",
        options_map={"Not forced": 0, "Force on": 1, "Disable": 2},
    ),
    GrowattSelectEntityDescription(
        key=ATTR_UPS_OUTPUT_VOLTAGE,
        name="UPS Output Voltage",
        options_map={"230 V": 0, "208 V": 1, "240 V": 2},
    ),
    GrowattSelectEntityDescription(
        key=ATTR_UPS_OUTPUT_FREQUENCY,
        name="UPS Output Frequency",
        options_map={"50 Hz": 0, "60 Hz": 1},
    ),
)
STORAGE_SENSOR_TYPES: tuple[GrowattSensorEntityDescription, ...] = (
    GrowattSensorEntityDescription(
        key=ATTR_SOC_PERCENTAGE,
        name="SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY
    ),
    GrowattSensorEntityDescription(
        key=ATTR_DISCHARGE_POWER,
        name="Discharge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER
    ),
    GrowattSensorEntityDescription(
        key=ATTR_CHARGE_POWER,
        name="Charge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER
    ),
    GrowattSensorEntityDescription(
        key=ATTR_ENERGY_TO_GRID_TOTAL,
        name="Energy To Grid (Total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_ENERGY_TO_GRID_TODAY,
        name="Energy To Grid (Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        midnight_reset=True
    ),
    GrowattSensorEntityDescription(
        key=ATTR_ENERGY_TO_USER_TOTAL,
        name="Energy To User (Total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_ENERGY_TO_USER_TODAY,
        name="Energy To User (Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        midnight_reset=True
    ),
    GrowattSensorEntityDescription(
        key=ATTR_AC_CHARGE_ENABLED,
        name="AC Charge Enabled"
    ),
    GrowattSensorEntityDescription(
        key=ATTR_DISCHARGE_ENERGY_TODAY,
        name="Battery Discharged (Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        midnight_reset=True
    ),
    GrowattSensorEntityDescription(
        key=ATTR_DISCHARGE_ENERGY_TOTAL,
        name="Battery Discharged (Total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_CHARGE_ENERGY_TODAY,
        name="Battery Charged (Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        midnight_reset=True
    ),
    GrowattSensorEntityDescription(
        key=ATTR_CHARGE_ENERGY_TOTAL,
        name="Battery Charged (Total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_METER_POWER_NETTO,
        name="Meter",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_INVERTER_STATUS,
        name="Inverter Status",
    ),
    GrowattSensorEntityDescription(
        key=ATTR_INVERTER_MODE,
        name="Inverter Mode",
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BDC_DATA_FLAG,
        name="BDC Data Flag",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BDC_DERATING_MODE,
        name="BDC Derating Mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_TEMPERATURE_A,
        name="BMS temperature A",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_TEMPERATURE_B,
        name="BMS temperature B",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BATTERY_PACK_NUMBER,
        name="Battery pack number ",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Telemetry added in Protocol II V1.39 ---
    GrowattSensorEntityDescription(
        key=ATTR_BATTERY_VOLTAGE,
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BATTERY_CURRENT,
        name="Battery Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_SELF_CONSUMPTION_POWER,
        name="Self Consumption Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_SYSTEM_ENERGY_TODAY,
        name="System Output (Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        midnight_reset=True,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_SYSTEM_ENERGY_TOTAL,
        name="System Output (Total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_SELF_CONSUMPTION_ENERGY_TODAY,
        name="Self Consumption (Today)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        midnight_reset=True,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_SELF_CONSUMPTION_ENERGY_TOTAL,
        name="Self Consumption (Total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_MAX_SOC,
        name="BMS Max SOC",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_MIN_SOC,
        name="BMS Min SOC",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_PARALLEL_BATTERY_NUM,
        name="Parallel Battery Count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Battery / BMS detail and fault sensors (3165-3233 block) ---
    GrowattSensorEntityDescription(
        key=ATTR_BMS_SOH,
        name="Battery Health (SOH)",
        native_unit_of_measurement=PERCENTAGE,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_STATUS,
        name="BMS Status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_SOC,
        name="BMS SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_CYCLE_COUNT,
        name="BMS Cycle Count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_CELL_VOLTAGE_MAX,
        name="BMS Cell Voltage Max",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_CELL_VOLTAGE_MIN,
        name="BMS Cell Voltage Min",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_MAX_CHARGE_CURRENT,
        name="BMS Max Charge Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_MAX_DISCHARGE_CURRENT,
        name="BMS Max Discharge Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_STORAGE_FAULT_CODE,
        name="Storage Fault Code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_STORAGE_WARNING_CODE,
        name="Storage Warning Code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_DERATE_REASON,
        name="BMS Derate Reason",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Firmware readouts ---
    GrowattSensorEntityDescription(
        key=ATTR_FIRMWARE,
        name="Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_CONTROL_FIRMWARE,
        name="Control Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BDC_FIRMWARE,
        name="BDC Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    GrowattSensorEntityDescription(
        key=ATTR_BMS_FIRMWARE,
        name="BMS Firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def build_battery_module_sensor_types(
    count: int,
) -> tuple[GrowattSensorEntityDescription, ...]:
    """Per-module serial-number sensors; keys match build_battery_module_registers.

    The protocol exposes per-module identity (serial) but no per-module live
    telemetry, so each module gets a serial-number sensor for tracking.
    """
    types: list[GrowattSensorEntityDescription] = []
    for n in range(1, count + 1):
        types.extend(
            (
                GrowattSensorEntityDescription(
                    key=f"battery_module_{n}_serial_number",
                    name=f"Module {n} Serial Number",
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
                GrowattSensorEntityDescription(
                    key=f"battery_module_{n}_dsp_firmware",
                    name=f"Module {n} DSP Firmware",
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
                GrowattSensorEntityDescription(
                    key=f"battery_module_{n}_mcu_firmware",
                    name=f"Module {n} MCU Firmware",
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            )
        )
    return tuple(types)