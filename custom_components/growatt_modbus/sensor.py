from datetime import timedelta

import logging
import re

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import (
    CONF_MODEL,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)


from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .API.const import DeviceTypes
from .API.device_type.base import (
    ATTR_INPUT_POWER,
    ATTR_OUTPUT_POWER,
    ATTR_SOC_PERCENTAGE,
    ATTR_DISCHARGE_POWER,
    ATTR_CHARGE_POWER
)

from . import GrowattConfigEntry
from .optimizer import build_optimizer_sensors
from .sensor_types.sensor_entity_description import GrowattSensorEntityDescription
from .sensor_types.inverter import INVERTER_SENSOR_TYPES
from .sensor_types.storage import (
    STORAGE_SENSOR_TYPES,
    build_battery_module_sensor_types,
)
from .const import (
    CONF_AC_PHASES,
    CONF_DC_STRING,
    CONF_FIRMWARE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

# Per-module sensor keys look like ``battery_module_<slot>_<field>``.
_MODULE_KEY_RE = re.compile(r"battery_module_(\d+)_")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    runtime = config_entry.runtime_data
    main_coordinator = runtime.main_coordinator
    power_coordinator = runtime.power_coordinator
    device = runtime.device

    sensor_descriptions: list[GrowattSensorEntityDescription] = []
    supported_key_names = device.get_register_names()

    device_type = DeviceTypes(config_entry.data[CONF_TYPE])

    if device_type in (DeviceTypes.INVERTER, DeviceTypes.INVERTER_315, DeviceTypes.INVERTER_120, DeviceTypes.HYBRID_120):
        for sensor in INVERTER_SENSOR_TYPES:
            if sensor.key not in supported_key_names:
                continue

            if re.match(r"input_\d+", sensor.key) and not re.match(
                f"input_[1-{config_entry.data[CONF_DC_STRING]}]", sensor.key
            ):
                continue
            elif re.match(r"output_\d+", sensor.key) and not re.match(
                f"output_[1-{config_entry.data[CONF_AC_PHASES]}]", sensor.key
            ):
                continue

            sensor_descriptions.append(sensor)

    module_descriptions: list[GrowattSensorEntityDescription] = []
    if device_type in (DeviceTypes.HYBRID_120, DeviceTypes.STORAGE_120):
        for sensor in STORAGE_SENSOR_TYPES:
            if sensor.key not in supported_key_names:
                continue

            sensor_descriptions.append(sensor)

        # Per-module sensors (count auto-detected or set in options) are grouped
        # under their own per-module device, so they are built separately below.
        for sensor in build_battery_module_sensor_types(device.battery_modules):
            if sensor.key in supported_key_names:
                module_descriptions.append(sensor)

    if device_type in (DeviceTypes.INVERTER, DeviceTypes.INVERTER_315, DeviceTypes.INVERTER_120):
        power_sensor = (ATTR_INPUT_POWER, ATTR_OUTPUT_POWER)
    elif device_type in (DeviceTypes.HYBRID_120,):
        power_sensor = (ATTR_INPUT_POWER, ATTR_OUTPUT_POWER, ATTR_SOC_PERCENTAGE, ATTR_DISCHARGE_POWER, ATTR_CHARGE_POWER)
    elif device_type in (DeviceTypes.STORAGE_120,):
        power_sensor = (ATTR_SOC_PERCENTAGE, ATTR_DISCHARGE_POWER, ATTR_CHARGE_POWER)
    else:
        power_sensor = tuple()
        _LOGGER.debug(
            "Device type %s was found but is not supported right now",
            config_entry.data[CONF_TYPE],
        )

    # Power sensors poll on the fast power coordinator when it exists; every
    # other sensor polls on the main coordinator.
    power_names = set(power_sensor) if power_coordinator is not None else set()

    entities = []
    for coordinator, descriptions in (
        (main_coordinator, [d for d in sensor_descriptions if d.key not in power_names]),
        (power_coordinator, [d for d in sensor_descriptions if d.key in power_names]),
    ):
        if coordinator is None or not descriptions:
            continue

        coordinator.get_keys_by_name({d.key for d in descriptions}, True)
        entities.extend(
            GrowattDeviceEntity(coordinator, description=description, entry=config_entry)
            for description in descriptions
        )

    # Per-module sensors poll on the main coordinator and are grouped under a
    # per-module device keyed by the module serial (read at setup).
    module_serials = runtime.battery_module_serials
    if module_descriptions:
        main_coordinator.get_keys_by_name({d.key for d in module_descriptions}, True)
        for description in module_descriptions:
            match = _MODULE_KEY_RE.match(description.key)
            slot = int(match.group(1)) if match else None
            entities.append(
                GrowattDeviceEntity(
                    main_coordinator,
                    description=description,
                    entry=config_entry,
                    module_slot=slot,
                    module_serial=module_serials.get(slot),
                )
            )

    # Diagnostic sensors mirroring the EMHASS optimisation plan (read-only).
    if runtime.optimizer is not None:
        entities.extend(build_optimizer_sensors(runtime.optimizer, config_entry))

    async_add_entities(entities, True)


class GrowattDeviceEntity(CoordinatorEntity, RestoreEntity, SensorEntity):
    """An entity using CoordinatorEntity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description, entry, module_slot=None, module_serial=None):
        """Pass coordinator to CoordinatorEntity.

        When ``module_serial`` is given the entity belongs to a battery module:
        it is grouped under a per-module device and identified by the module
        serial (so its identity and history follow the physical module if the
        slot order changes), while still reading its slot-based data key.
        """
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._config_entry = entry
        inverter_serial = entry.data[CONF_SERIAL_NUMBER]

        if module_serial:
            field = description.key.split(f"battery_module_{module_slot}_", 1)[-1]
            self._attr_unique_id = (
                f"{DOMAIN}_{inverter_serial}_module_{module_serial}_{field}"
            )
            # The per-module device supplies the module context, so the entity
            # name drops the "Module N" prefix (e.g. "Module 1 SOC" -> "SOC").
            name_match = re.match(r"Module \d+ (.+)", description.name or "")
            self._attr_name = name_match.group(1) if name_match else description.name
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{inverter_serial}_battery_module_{module_serial}")},
                manufacturer="Growatt",
                model="Battery Module",
                name=f"Module {module_serial}",
                via_device=(DOMAIN, inverter_serial),
            )
        else:
            self._attr_unique_id = f"{DOMAIN}_{inverter_serial}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, inverter_serial)},
                manufacturer="Growatt",
                model=entry.data[CONF_MODEL],
                sw_version=entry.data[CONF_FIRMWARE],
                name=entry.data[CONF_NAME],
            )

    async def async_added_to_hass(self) -> None:
        """Call when entity is about to be added to Home Assistant."""
        await super().async_added_to_hass()

        if self.entity_description.midnight_reset:
            self.async_on_remove(
                self.coordinator.async_add_midnight_listener(
                    self._handle_midnight_update, self.coordinator_context
                )
            )

        if (state := await self.async_get_last_state()) is None:
            return
        
        if self._numeric_state_expected and state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._attr_native_value = state.state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only refresh the value when this poll actually returned it (a missing
        # key keeps the last value), but always write state so the entity's
        # availability tracks the coordinator - on a failed update it must go
        # unavailable instead of holding the stale value.
        state = self.coordinator.data.get(self.entity_description.key)
        if state is not None:
            self._attr_native_value = state
        self.async_write_ha_state()

    @callback
    def _handle_midnight_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (state := self.coordinator.data.get(self.entity_description.key)) is None:
            return
        self._attr_native_value = state
        self.async_write_ha_state()
