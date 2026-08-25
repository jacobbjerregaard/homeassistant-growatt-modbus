"""Diagnostic sensors reflecting the current optimisation plan."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
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
    EntityCategory,
    UnitOfPower,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from ..const import (
    CONF_FIRMWARE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from .coordinator import EmhassOptimizerCoordinator
from .plan import OptimizationPlan


@dataclass(frozen=True, kw_only=True)
class OptimizerSensorEntityDescription(SensorEntityDescription):
    """Describes a diagnostic sensor backed by the optimisation plan."""

    value_fn: Callable[[OptimizationPlan], StateType | datetime]
    forecast_fn: Callable[[OptimizationPlan], Any] | None = None


OPTIMIZER_SENSOR_TYPES: tuple[OptimizerSensorEntityDescription, ...] = (
    OptimizerSensorEntityDescription(
        key="optimizer_status",
        name="Optimizer Status",
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
        self._attr_translation_key = description.key
        serial = entry.data[CONF_SERIAL_NUMBER]
        self._attr_unique_id = f"{DOMAIN}_{serial}_{description.key}"
        # Inlined (not the shared entity.growatt_device_info helper) so this
        # module does not import entity/coordinator and stays cycle-free.
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
