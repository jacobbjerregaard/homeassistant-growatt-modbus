"""EMHASS optimizer bridge.

Phase 1 is **read-only**: it reads the optimisation plan EMHASS publishes into
Home Assistant (``sensor.p_batt_forecast`` etc.) and surfaces it as diagnostic
sensors grouped under the Growatt inverter, plus a service to trigger a fresh
optimisation on demand. No battery actuation happens here yet - mapping the plan
onto the inverter's TOU slots / charge controls arrives in later phases.

Keeping this phase read-only means the plan can be verified against a real
EMHASS instance and real hardware without any risk of mis-driving the battery.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_MODEL,
    CONF_NAME,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .API.device_type.base import ATTR_AC_CHARGE_ENABLED
from .API.device_type.storage_120 import encode_time_slot, time_slot_register
from .API.tou_planner import (
    BATTERY_FIRST,
    LOAD_FIRST,
    compile_tou_slots,
    minutes_to_hm,
    priority_for_step,
)
from .const import CONF_FIRMWARE, CONF_SERIAL_NUMBER, DOMAIN
from .emhass_client import EmhassClient, EmhassError

_LOGGER = logging.getLogger(__name__)

# Default entity ids EMHASS publishes its results to. These are the EMHASS
# defaults; making them user-overridable can come later if needed.
EMHASS_SENSOR_BATT_POWER = "sensor.p_batt_forecast"
EMHASS_SENSOR_BATT_SOC = "sensor.soc_batt_forecast"
EMHASS_SENSOR_PV = "sensor.p_pv_forecast"
EMHASS_SENSOR_LOAD = "sensor.p_load_forecast"
EMHASS_SENSOR_UNIT_COST = "sensor.unit_load_cost"
EMHASS_SENSOR_GRID = "sensor.p_grid_forecast"
EMHASS_SENSOR_STATUS = "sensor.optim_status"

# The inverter has 9 hardware time-of-use slots.
MAX_TOU_SLOTS = 9


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


def read_plan(hass: HomeAssistant) -> OptimizationPlan:
    """Build an OptimizationPlan from EMHASS's published sensors."""
    battery_power, battery_power_forecast = _read_float(hass, EMHASS_SENSOR_BATT_POWER)
    battery_soc, battery_soc_forecast = _read_float(hass, EMHASS_SENSOR_BATT_SOC)
    pv_power, _ = _read_float(hass, EMHASS_SENSOR_PV)
    load_power, _ = _read_float(hass, EMHASS_SENSOR_LOAD)
    unit_cost, _ = _read_float(hass, EMHASS_SENSOR_UNIT_COST)

    return OptimizationPlan(
        status=_read_text(hass, EMHASS_SENSOR_STATUS),
        battery_power=battery_power,
        battery_soc=battery_soc,
        pv_power=pv_power,
        load_power=load_power,
        unit_cost=unit_cost,
        battery_power_forecast=battery_power_forecast,
        battery_soc_forecast=battery_soc_forecast,
        updated=dt_util.utcnow(),
    )


class EmhassOptimizerCoordinator(DataUpdateCoordinator[OptimizationPlan]):
    """Reads the EMHASS-published plan on an interval and triggers re-optims."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EmhassClient,
        update_interval: timedelta,
        device_coordinator=None,
        enabled: bool = False,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_optimizer",
            update_interval=update_interval,
        )
        self.client = client
        # Handle used to write the inverter's registers (the main register
        # coordinator). When ``enabled`` is False the optimizer stays read-only.
        self._device_coordinator = device_coordinator
        self.enabled = enabled

    async def _async_update_data(self) -> OptimizationPlan:
        # Reading published states never fails; missing sensors just read as
        # None so the diagnostics show "unknown" until EMHASS publishes.
        return read_plan(self.hass)

    async def async_run_optimization(self) -> None:
        """Trigger a day-ahead optimisation + publish, then re-read the plan.

        When actuation is enabled the freshly published plan is also compiled
        onto the inverter's time-of-use slots.
        """
        try:
            await self.client.async_dayahead_optim()
            await self.client.async_publish_data()
        except EmhassError as err:
            raise HomeAssistantError(str(err)) from err
        await self.async_request_refresh()
        if self.enabled:
            await self.async_compile_tou()

    # --- day-ahead TOU compile (actuation) ---------------------------------

    def _forecast_series(self, entity_id: str) -> list[tuple[datetime, float | None]]:
        """Parse a published EMHASS sensor's ``forecasts`` attribute.

        Returns ``(datetime, value)`` pairs, tolerating whatever value column
        name EMHASS used (the first non-``date`` field per entry).
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            return []
        forecasts = state.attributes.get("forecasts")
        if not forecasts:
            return []

        series: list[tuple[datetime, float | None]] = []
        for entry in forecasts:
            if not isinstance(entry, dict):
                continue
            raw_date = entry.get("date")
            parsed = dt_util.parse_datetime(raw_date) if raw_date else None
            if parsed is None:
                continue
            value: float | None = None
            for key, raw in entry.items():
                if key == "date":
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    value = None
                break
            series.append((parsed, value))
        return series

    def _plan_steps(self) -> list[tuple[int, int, int]]:
        """Build ``(start_min, end_min, priority)`` steps from the published plan.

        Only the first forecast day is used; time-of-use slots repeat daily, so a
        multi-day horizon cannot be mapped to them unambiguously.
        """
        battery = sorted(
            self._forecast_series(EMHASS_SENSOR_BATT_POWER), key=lambda item: item[0]
        )
        if not battery:
            return []
        grid = {dt: value for dt, value in self._forecast_series(EMHASS_SENSOR_GRID)}

        intervals = [
            (battery[i + 1][0] - battery[i][0]).total_seconds() / 60
            for i in range(len(battery) - 1)
        ]
        default_interval = intervals[0] if intervals else 60.0
        day = dt_util.as_local(battery[0][0]).date()

        steps: list[tuple[int, int, int]] = []
        for index, (when, p_batt) in enumerate(battery):
            local = dt_util.as_local(when)
            if local.date() != day:
                break
            start_min = local.hour * 60 + local.minute
            interval = intervals[index] if index < len(intervals) else default_interval
            end_min = start_min + int(round(interval))
            priority = priority_for_step(p_batt, grid.get(when))
            steps.append((start_min, end_min, priority))
        return steps

    async def async_compile_tou(self) -> None:
        """Compile the published day-ahead plan onto the inverter's TOU slots."""
        if not self.enabled or self._device_coordinator is None:
            return
        steps = self._plan_steps()
        if not steps:
            # Fail safe: with no plan, leave the existing slots untouched rather
            # than stranding the battery.
            _LOGGER.warning(
                "optimizer: no EMHASS plan forecast available; TOU slots unchanged"
            )
            return
        slots = compile_tou_slots(steps, MAX_TOU_SLOTS)
        await self._write_tou_slots(slots)

    async def _write_tou_slots(self, slots: list[tuple[int, int, int]]) -> None:
        coordinator = self._device_coordinator
        for slot_num in range(1, MAX_TOU_SLOTS + 1):
            base = time_slot_register(slot_num)
            if slot_num <= len(slots):
                start_min, end_min, priority = slots[slot_num - 1]
                start_hour, start_minute = minutes_to_hm(start_min)
                end_hour, end_minute = minutes_to_hm(end_min)
                reg1, reg2 = encode_time_slot(
                    start_hour, start_minute, end_hour, end_minute, priority, True
                )
            else:
                # Disable unused slots so a stale window doesn't linger.
                reg1, reg2 = encode_time_slot(0, 0, 0, 0, LOAD_FIRST, False)
            await coordinator.write_register_value(base, reg1)
            await coordinator.write_register_value(base + 1, reg2)

        # Grid charging only happens in a Battery-First slot when AC charge is on.
        await self._set_ac_charge(
            any(priority == BATTERY_FIRST for _start, _end, priority in slots)
        )
        await coordinator.async_request_refresh()

    async def _set_ac_charge(self, enable: bool) -> None:
        coordinator = self._device_coordinator
        register = coordinator.get_holding_register_by_name(ATTR_AC_CHARGE_ENABLED)
        if register is None:
            _LOGGER.debug("optimizer: AC charge register not available on this model")
            return
        await coordinator.write_register(register.register, 1 if enable else 0)


@dataclass(frozen=True, kw_only=True)
class OptimizerSensorEntityDescription(SensorEntityDescription):
    """Describes a diagnostic sensor backed by the optimisation plan."""

    value_fn: Callable[[OptimizationPlan], StateType | datetime]
    forecast_fn: Callable[[OptimizationPlan], Any] | None = None


OPTIMIZER_SENSOR_TYPES: tuple[OptimizerSensorEntityDescription, ...] = (
    OptimizerSensorEntityDescription(
        key="optimizer_status",
        name="Optimizer Status",
        icon="mdi:flash",
        value_fn=lambda plan: plan.status,
    ),
    OptimizerSensorEntityDescription(
        key="optimizer_battery_power_target",
        name="Optimizer Battery Power Target",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plan: plan.battery_power,
        forecast_fn=lambda plan: plan.battery_power_forecast,
    ),
    OptimizerSensorEntityDescription(
        key="optimizer_battery_soc_target",
        name="Optimizer Battery SOC Target",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda plan: plan.battery_soc,
        forecast_fn=lambda plan: plan.battery_soc_forecast,
    ),
    OptimizerSensorEntityDescription(
        key="optimizer_plan_updated",
        name="Optimizer Plan Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda plan: plan.updated,
    ),
)


class OptimizerSensor(CoordinatorEntity[EmhassOptimizerCoordinator], SensorEntity):
    """A diagnostic sensor reflecting one field of the optimisation plan."""

    _attr_has_entity_name = True
    entity_description: OptimizerSensorEntityDescription

    def __init__(self, coordinator, description, entry):
        super().__init__(coordinator)
        self.entity_description = description
        serial = entry.data[CONF_SERIAL_NUMBER]
        self._attr_unique_id = f"{DOMAIN}_{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Growatt",
            model=entry.data[CONF_MODEL],
            sw_version=entry.data[CONF_FIRMWARE],
            name=entry.data[CONF_NAME],
        )

    @property
    def native_value(self) -> StateType | datetime:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (
            self.entity_description.forecast_fn is None
            or self.coordinator.data is None
        ):
            return None
        forecast = self.entity_description.forecast_fn(self.coordinator.data)
        if forecast is None:
            return None
        return {"forecast": forecast}


def build_optimizer_sensors(coordinator, entry) -> list[OptimizerSensor]:
    """Build the diagnostic sensors for the optimizer."""
    return [
        OptimizerSensor(coordinator, description, entry)
        for description in OPTIMIZER_SENSOR_TYPES
    ]
