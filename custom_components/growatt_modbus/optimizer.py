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

from .API.device_type.base import (
    ATTR_AC_CHARGE_ENABLED,
    ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST,
    ATTR_BATTERY_CHARGE_STOP_SOC,
    ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST,
    ATTR_BMS_MAX_SOC,
    ATTR_BMS_MIN_SOC,
    ATTR_ON_GRID_DISCHARGE_STOP_SOC,
)
from .API.device_type.storage_120 import encode_time_slot, time_slot_register
from .API.tou_planner import (
    BATTERY_FIRST,
    DEFAULT_CHARGE_THRESHOLD,
    DEFAULT_DISCHARGE_THRESHOLD,
    LOAD_FIRST,
    clamp_soc,
    compile_tou_slots,
    minutes_to_hm,
    power_to_rate,
    priority_for_step,
)
from .API.utils import to_register_value
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


class EmhassOptimizerCoordinator(DataUpdateCoordinator[OptimizationPlan]):
    """Reads the EMHASS-published plan on an interval and triggers re-optims."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EmhassClient,
        update_interval: timedelta,
        device_coordinator=None,
        enabled: bool = False,
        soc_sensor: str | None = None,
        entities: EmhassEntities | None = None,
        battery_max_power: float = 0.0,
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
        self._soc_sensor = soc_sensor
        self._entities = entities or EmhassEntities()
        self._battery_max_power = battery_max_power

    async def _async_update_data(self) -> OptimizationPlan:
        # Reading published states never fails; missing sensors just read as
        # None so the diagnostics show "unknown" until EMHASS publishes.
        return read_plan(self.hass, self._entities)

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
            self._forecast_series(self._entities.batt_power), key=lambda item: item[0]
        )
        if not battery:
            return []
        grid = {dt: value for dt, value in self._forecast_series(self._entities.grid)}

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

    # --- intraday model-predictive corrections -----------------------------

    def _live_soc(self) -> float | None:
        """Current battery SOC (%) from the configured sensor, for EMHASS."""
        if not self._soc_sensor:
            return None
        state = self.hass.states.get(self._soc_sensor)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _bms_soc_limits(self) -> tuple[float, float]:
        """BMS-reported safe SOC window, falling back to 0..100.

        A missing or degenerate reading (e.g. an unsupported model reporting 0)
        must not clamp the target down to 0 and strand charging, so anything that
        isn't a sane ``0 <= low < high <= 100`` window falls back to no limit.
        """
        data = getattr(self._device_coordinator, "data", None) or {}
        try:
            low = float(data.get(ATTR_BMS_MIN_SOC))
        except (TypeError, ValueError):
            low = 0.0
        try:
            high = float(data.get(ATTR_BMS_MAX_SOC))
        except (TypeError, ValueError):
            high = 100.0
        if not 0 <= low < 100:
            low = 0.0
        if not 0 < high <= 100:
            high = 100.0
        if low >= high:
            low, high = 0.0, 100.0
        return low, high

    @staticmethod
    def _plan_is_actionable(plan: OptimizationPlan) -> bool:
        """Only act on a fresh, feasible plan (the core MPC fail-safe)."""
        if plan is None or plan.battery_power is None:
            return False
        if plan.status is None or plan.status.lower() != "optimal":
            return False
        return True

    async def async_mpc_step(self) -> None:
        """Re-run EMHASS naive-MPC with the live SOC and correct current controls.

        This nudges the AC-charge switch and the relevant stop-SOC for *now*
        without rewriting the day-ahead TOU slots, so the schedule adapts to SOC
        drift and forecast error between daily compiles.
        """
        if not self.enabled or self._device_coordinator is None:
            return

        params: dict = {}
        soc = self._live_soc()
        if soc is not None:
            # EMHASS expects the initial SOC as a 0..1 fraction.
            params["soc_init"] = round(soc / 100.0, 4)
        try:
            await self.client.async_naive_mpc_optim(params)
            await self.client.async_publish_data()
        except EmhassError as err:
            # Act on whatever is currently published rather than failing.
            _LOGGER.warning("optimizer MPC: EMHASS request failed: %s", err)

        await self.async_request_refresh()
        plan = self.data
        if not self._plan_is_actionable(plan):
            _LOGGER.debug("optimizer MPC: plan not actionable; leaving controls")
            return
        await self._apply_mpc_corrections(plan)

    async def _apply_mpc_corrections(self, plan: OptimizationPlan) -> None:
        coordinator = self._device_coordinator
        charging = plan.battery_power < -DEFAULT_CHARGE_THRESHOLD
        discharging = plan.battery_power > DEFAULT_DISCHARGE_THRESHOLD

        # AC charge tracks whether we should be charging from grid right now.
        await self._set_ac_charge(charging)

        # Track the plan's SOC target via the matching stop-SOC, clamped to the
        # BMS safe window so a bad plan value can never push past it.
        if plan.battery_soc is not None:
            low, high = self._bms_soc_limits()
            target = clamp_soc(plan.battery_soc, low, high)
            if charging:
                await self._write_number(ATTR_BATTERY_CHARGE_STOP_SOC, target)
            elif discharging:
                await self._write_number(ATTR_ON_GRID_DISCHARGE_STOP_SOC, target)

        # Set the charge/discharge rate from the planned power, when a battery
        # max power is configured (otherwise leave the inverter's rate as-is).
        rate = power_to_rate(plan.battery_power, self._battery_max_power)
        if rate is not None:
            if charging:
                await self._write_number(ATTR_BATTERY_CHARGE_RATE_WHEN_FIRST, rate)
            elif discharging:
                await self._write_number(
                    ATTR_BATTERY_DISCHARGE_RATE_WHEN_GRID_FIRST, rate
                )

        await coordinator.async_request_refresh()

    async def _write_number(self, key: str, value: float) -> None:
        """Write a scaled value to a named holding register (number control)."""
        coordinator = self._device_coordinator
        register = coordinator.get_holding_register_by_name(key)
        if register is None:
            _LOGGER.debug("optimizer: register %s not available on this model", key)
            return
        await coordinator.write_register(register.register, to_register_value(register, value))


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
