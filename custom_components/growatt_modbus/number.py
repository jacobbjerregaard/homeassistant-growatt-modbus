"""Number platform for the Growatt Modbus integration.

Exposes writable holding registers (SOC limits, charge/discharge rates) as
number entities.
"""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.number import NumberEntity
from homeassistant.const import (
    CONF_MODEL,
    CONF_NAME,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GrowattConfigEntry
from .API.utils import to_register_value
from .const import (
    CONF_FIRMWARE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from .sensor_types.number_entity_description import GrowattNumberEntityDescription
from .sensor_types.storage import STORAGE_NUMBER_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt number entities for this config entry."""
    # Numbers are config registers; they poll on the main coordinator.
    coordinator = config_entry.runtime_data.main_coordinator
    supported_key_names = config_entry.runtime_data.device.get_register_names()

    descriptions = [
        description
        for description in STORAGE_NUMBER_TYPES
        if description.key in supported_key_names
    ]

    coordinator.get_keys_by_name({description.key for description in descriptions}, True)

    async_add_entities(
        (
            GrowattNumber(coordinator, description=description, entry=config_entry)
            for description in descriptions
        ),
        True,
    )


class GrowattNumber(CoordinatorEntity, NumberEntity):
    """A writable Growatt holding-register number."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, description, entry):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, description.key)
        self.entity_description: GrowattNumberEntityDescription = description
        self._config_entry = entry

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_SERIAL_NUMBER])},
            manufacturer="Growatt",
            model=entry.data[CONF_MODEL],
            sw_version=entry.data[CONF_FIRMWARE],
            name=entry.data[CONF_NAME],
        )

    @property
    def unique_id(self) -> Optional[str]:
        return (
            f"{DOMAIN}_{self._config_entry.data[CONF_SERIAL_NUMBER]}_"
            f"{self.entity_description.key}"
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Write the value to the backing holding register."""
        register = self.coordinator.get_holding_register_by_name(
            self.entity_description.key
        )
        if register is None:
            _LOGGER.error(
                "No holding register found for %s", self.entity_description.key
            )
            return

        # Inverse of the read-time scaling (see process_registers).
        raw = to_register_value(register, value)

        await self.coordinator.write_register(register.register, raw)
        self._attr_native_value = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (state := self.coordinator.data.get(self.entity_description.key)) is None:
            return
        self._attr_native_value = state
        self.async_write_ha_state()
