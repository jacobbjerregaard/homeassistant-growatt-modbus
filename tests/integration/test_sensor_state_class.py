"""Sensor state classes: every numeric reading must record long-term statistics.

A sensor without a ``state_class`` gets no long-term statistics. Every sensor
with a unit must have one unless it is a fixed nameplate or limit value, and
sensors without a unit (status, enum, codes, flags) must not, apart from the
unitless counters listed below.
"""

import pytest
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNKNOWN,
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
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import mock_restore_cache

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

# Fixed nameplate values, BMS limits and counts: nothing worth charting, so
# deliberately no statistics.
NO_STATISTICS_KEYS = {
    "inverter_rated_power",
    "rated_cell_capacity",
    "rated_battery_capacity",
    "bms_max_soc",
    "bms_min_soc",
    "battery_number_of_modules",
    "parallel_battery_num",
    "battery_pack_number",
}

# Unitless sensors that are still numeric readings. MEASUREMENT rather than
# TOTAL_INCREASING: a single bad poll reading 0 would otherwise count as a
# meter reset and add the whole count to the sum again.
UNITLESS_COUNTER_KEYS = {"bms_cycle_count"} | {
    f"battery_module_{n}_cycle_count" for n in (1, 2)
}


def _key(description):
    return description.key


def _description(key):
    (description,) = (d for d in ALL_SENSORS if d.key == key)
    return description


def test_allowlists_name_real_sensors():
    keys = {d.key for d in ALL_SENSORS}
    assert NO_STATISTICS_KEYS <= keys
    assert UNITLESS_COUNTER_KEYS <= keys


@pytest.mark.parametrize(
    "description",
    [
        d
        for d in ALL_SENSORS
        if d.native_unit_of_measurement is not None and d.key not in NO_STATISTICS_KEYS
    ],
    ids=_key,
)
def test_sensors_with_a_unit_record_statistics(description):
    assert description.state_class is not None


@pytest.mark.parametrize(
    "description",
    [
        d
        for d in ALL_SENSORS
        if d.device_class in MEASUREMENT_CLASSES and d.key not in NO_STATISTICS_KEYS
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
        if d.native_unit_of_measurement is None and d.key not in UNITLESS_COUNTER_KEYS
    ],
    ids=_key,
)
def test_unitless_sensors_have_no_state_class(description):
    # Status, enum, code and flag sensors. Home Assistant rejects a state class
    # on an ENUM sensor outright.
    assert description.state_class is None


@pytest.mark.parametrize("key", sorted(NO_STATISTICS_KEYS))
def test_nameplate_and_limit_sensors_have_no_state_class(key):
    assert _description(key).state_class is None


@pytest.mark.parametrize("key", sorted(UNITLESS_COUNTER_KEYS))
def test_cycle_counts_are_measurements(key):
    assert _description(key).state_class == SensorStateClass.MEASUREMENT


def test_operation_hours_is_total_increasing():
    hours = _description("operation_hours")
    assert hours.device_class == SensorDeviceClass.DURATION
    assert hours.native_unit_of_measurement == UnitOfTime.HOURS
    assert hours.state_class == SensorStateClass.TOTAL_INCREASING


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
    """The sensors from the original report."""
    assert _description(key).state_class == SensorStateClass.MEASUREMENT


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


async def test_restart_does_not_restore_measurements(
    hass, fake_modbus, setup_with_transport
):
    """A stale pre-restart reading must not be written as current.

    The first state after a restart is written before the coordinator listener
    is registered; for a MEASUREMENT sensor a restored value would go straight
    into the long-term statistics.
    """
    mock_restore_cache(
        hass,
        [
            State("sensor.growatt_test_charge_power", "4000"),
            State("sensor.growatt_test_energy_to_grid_total", "1234.5"),
        ],
    )
    entry = await setup_with_transport(return_value=fake_modbus)

    registry = er.async_get(hass)
    by_uid = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    charge = by_uid[f"{DOMAIN}_{entry.unique_id}_charge_power"]
    energy = by_uid[f"{DOMAIN}_{entry.unique_id}_energy_to_grid_total"]
    # Guard: the restore cache must have targeted the real entity IDs.
    assert charge == "sensor.growatt_test_charge_power"
    assert energy == "sensor.growatt_test_energy_to_grid_total"

    assert hass.states.get(charge).state == STATE_UNKNOWN
    # Cumulative counters still restore, so the graph doesn't drop to zero.
    assert hass.states.get(energy).state == "1234.5"
