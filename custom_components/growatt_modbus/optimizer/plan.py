"""The EMHASS optimisation plan, as published into Home Assistant.

Pure reading: this module turns the EMHASS sensors into an OptimizationPlan
snapshot. It knows nothing about the inverter and never writes anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

# Default entity ids EMHASS publishes its results to. These are the EMHASS
# defaults; making them user-overridable can come later if needed.
EMHASS_SENSOR_BATT_POWER = "sensor.p_batt_forecast"
EMHASS_SENSOR_BATT_SOC = "sensor.soc_batt_forecast"
EMHASS_SENSOR_PV = "sensor.p_pv_forecast"
EMHASS_SENSOR_LOAD = "sensor.p_load_forecast"
EMHASS_SENSOR_UNIT_COST = "sensor.unit_load_cost"
EMHASS_SENSOR_GRID = "sensor.p_grid_forecast"
EMHASS_SENSOR_STATUS = "sensor.optim_status"


@dataclass
class EmhassEntities:
    """Entity ids of the EMHASS-published sensors the optimizer reads.

    Defaults to the EMHASS defaults; the control-relevant ones can be overridden
    in the options for instances that publish under different names.
    """

    batt_power: str = EMHASS_SENSOR_BATT_POWER
    batt_soc: str = EMHASS_SENSOR_BATT_SOC
    pv: str = EMHASS_SENSOR_PV
    load: str = EMHASS_SENSOR_LOAD
    unit_cost: str = EMHASS_SENSOR_UNIT_COST
    grid: str = EMHASS_SENSOR_GRID
    status: str = EMHASS_SENSOR_STATUS


@dataclass
class OptimizationPlan:
    """A snapshot of the plan EMHASS has published, as read from HA states."""

    status: str | None = None
    battery_power: float | None = None  # W, negative = charging
    battery_soc: float | None = None  # %
    pv_power: float | None = None  # W
    load_power: float | None = None  # W
    unit_cost: float | None = None  # price / kWh
    battery_power_forecast: Any | None = None
    battery_soc_forecast: Any | None = None
    updated: datetime | None = None


def _read_float(hass: HomeAssistant, entity_id: str) -> tuple[float | None, Any | None]:
    """Return ``(value, forecasts)`` for a published EMHASS sensor.

    ``None`` is returned for the value when the sensor is missing, unavailable
    or non-numeric. The EMHASS time series, when present, lives in the
    ``forecasts`` state attribute and is passed through untouched.
    """
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None, None
    forecasts = state.attributes.get("forecasts")
    try:
        return float(state.state), forecasts
    except (ValueError, TypeError):
        return None, forecasts


def _read_text(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    return state.state


def read_plan(
    hass: HomeAssistant, entities: EmhassEntities | None = None
) -> OptimizationPlan:
    """Build an OptimizationPlan from EMHASS's published sensors."""
    entities = entities or EmhassEntities()
    battery_power, battery_power_forecast = _read_float(hass, entities.batt_power)
    battery_soc, battery_soc_forecast = _read_float(hass, entities.batt_soc)
    pv_power, _ = _read_float(hass, entities.pv)
    load_power, _ = _read_float(hass, entities.load)
    unit_cost, _ = _read_float(hass, entities.unit_cost)

    return OptimizationPlan(
        status=_read_text(hass, entities.status),
        battery_power=battery_power,
        battery_soc=battery_soc,
        pv_power=pv_power,
        load_power=load_power,
        unit_cost=unit_cost,
        battery_power_forecast=battery_power_forecast,
        battery_soc_forecast=battery_soc_forecast,
        updated=dt_util.utcnow(),
    )
