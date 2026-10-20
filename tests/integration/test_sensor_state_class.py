"""Sensor state classes: every numeric reading must record long-term statistics.

A sensor without a ``state_class`` gets no long-term statistics, and one that
loses it raises a "no longer has a state class" repair in Home Assistant.
"""

import pytest
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus.const import DOMAIN
from custom_components.growatt_modbus.entity_descriptions.inverter import (
    INVERTER_SENSOR_TYPES,
)
from custom_components.growatt_modbus.entity_descriptions.storage import (
    STORAGE_SENSOR_TYPES,
    build_battery_module_sensor_types,
)

ALL_SENSORS = (
    INVERTER_SENSOR_TYPES + STORAGE_SENSOR_TYPES + build_battery_module_sensor_types(2)
)

# Instantaneous readings: statistics record mean/min/max.
MEASUREMENT_CLASSES = {
    SensorDeviceClass.APPARENT_POWER: UnitOfApparentPower.VOLT_AMPERE,
    SensorDeviceClass.BATTERY: PERCENTAGE,
    SensorDeviceClass.CURRENT: UnitOfElectricCurrent.AMPERE,
    SensorDeviceClass.FREQUENCY: UnitOfFrequency.HERTZ,
    SensorDeviceClass.POWER: UnitOfPower.WATT,
    SensorDeviceClass.REACTIVE_POWER: UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    SensorDeviceClass.TEMPERATURE: UnitOfTemperature.CELSIUS,
    SensorDeviceClass.VOLTAGE: UnitOfElectricPotential.VOLT,
}

# Fixed nameplate values: a constant has nothing to chart, so no statistics.
NAMEPLATE_KEYS = {"inverter_rated_power"}


def _key(description):
    return description.key


@pytest.mark.parametrize(
    "description",
    [
        d
        for d in ALL_SENSORS
        if d.device_class in MEASUREMENT_CLASSES and d.key not in NAMEPLATE_KEYS
    ],
    ids=_key,
)
def test_instantaneous_sensors_are_measurements(description):
    assert description.state_class == SensorStateClass.MEASUREMENT
    assert (
        description.native_unit_of_measurement
        == MEASUREMENT_CLASSES[description.device_class]
    )


@pytest.mark.parametrize(
    "description",
    [d for d in ALL_SENSORS if d.device_class == SensorDeviceClass.ENERGY],
    ids=_key,
)
def test_energy_counters_are_total_increasing(description):
    # Both lifetime totals and the daily counters the inverter resets at
    # midnight: TOTAL_INCREASING treats a drop as a new cycle.
    assert description.state_class == SensorStateClass.TOTAL_INCREASING
    assert description.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR


@pytest.mark.parametrize(
    "description",
    [
        d
        for d in ALL_SENSORS
        if d.device_class == SensorDeviceClass.ENUM
        or (d.native_unit_of_measurement is None and d.state_class is None)
    ],
    ids=_key,
)
def test_text_and_enum_sensors_have_no_state_class(description):
    # Home Assistant rejects a state class on an ENUM sensor outright.
    assert description.state_class is None


@pytest.mark.parametrize("key", sorted(NAMEPLATE_KEYS))
def test_nameplate_sensors_have_no_state_class(key):
    (description,) = (d for d in ALL_SENSORS if d.key == key)
    assert description.state_class is None


def test_operation_hours_is_total_increasing():
    (hours,) = (d for d in INVERTER_SENSOR_TYPES if d.key == "operation_hours")
    assert hours.device_class == SensorDeviceClass.DURATION
    assert hours.native_unit_of_measurement == UnitOfTime.HOURS
    assert hours.state_class == SensorStateClass.TOTAL_INCREASING


@pytest.mark.parametrize("key", ["bms_cycle_count", "battery_module_1_cycle_count"])
def test_cycle_counts_are_total_increasing(key):
    (description,) = (d for d in ALL_SENSORS if d.key == key)
    assert description.state_class == SensorStateClass.TOTAL_INCREASING


@pytest.mark.parametrize(
    "key",
    [
        "input_1_power",
        "input_2_power",
        "output_power",
        "input_power",
        "charge_power",
        "discharge_power",
    ],
)
def test_reported_power_sensors_are_measurements(key):
    """The sensors from the original "no longer has a state class" report."""
    (description,) = (d for d in ALL_SENSORS if d.key == key)
    assert description.state_class == SensorStateClass.MEASUREMENT


async def test_state_class_reaches_entity_state(hass, setup_hybrid):
    entry, _fake = setup_hybrid
    registry = er.async_get(hass)
    by_uid = {
        e.unique_id: e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    def state_class(key: str):
        entity = by_uid[f"{DOMAIN}_{entry.unique_id}_{key}"]
        return hass.states.get(entity.entity_id).attributes.get(ATTR_STATE_CLASS)

    assert state_class("charge_power") == SensorStateClass.MEASUREMENT
    assert state_class("output_power") == SensorStateClass.MEASUREMENT
    assert state_class("output_energy_total") == SensorStateClass.TOTAL_INCREASING
    assert state_class("inverter_status") is None
