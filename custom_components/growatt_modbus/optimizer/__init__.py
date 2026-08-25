"""EMHASS optimizer bridge.

Reads the optimisation plan EMHASS publishes into Home Assistant
(``sensor.p_batt_forecast`` etc.), surfaces it as diagnostic sensors grouped
under the Growatt inverter, and - when the user enables actuation - compiles
the plan onto the inverter's time-of-use slots and charge controls.

Split across three modules: ``plan`` (reading the published plan, pure),
``coordinator`` (polling and actuation) and ``sensor`` (the entities).
"""

from .coordinator import (
    MAX_TOU_SLOTS,
    EmhassOptimizerCoordinator,
    async_setup_optimizer,
)
from .plan import EmhassEntities, OptimizationPlan, read_plan
from .sensor import (
    OPTIMIZER_SENSOR_TYPES,
    OptimizerSensor,
    OptimizerSensorEntityDescription,
    build_optimizer_sensors,
)

__all__ = [
    "OPTIMIZER_SENSOR_TYPES",
    "EmhassEntities",
    "EmhassOptimizerCoordinator",
    "MAX_TOU_SLOTS",
    "OptimizationPlan",
    "OptimizerSensor",
    "OptimizerSensorEntityDescription",
    "async_setup_optimizer",
    "build_optimizer_sensors",
    "read_plan",
]
