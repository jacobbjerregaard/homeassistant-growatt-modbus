"""Select platform for the Growatt Modbus integration.

Exposes writable enumerated holding registers (battery type, UPS output,
generator force) as select entities.
"""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.select import SelectEntity
from homeassistant.const import (
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GrowattConfigEntry
from .const import (
    CONF_FIRMWARE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from .sensor_types.select_entity_description import GrowattSelectEntityDescription
from .sensor_types.storage import STORAGE_SELECT_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt select entities for this config entry."""
    coordinator = config_entry.runtime_data.main_coordinator
    supported_key_names = config_entry.runtime_data.device.get_register_names()

    descriptions = [
        description
        for description in STORAGE_SELECT_TYPES
        if description.key in supported_key_names
    ]

    coordinator.get_keys_by_name({description.key for description in descriptions}, True)

    async_add_entities(
        (
            GrowattSelect(coordinator, description=description, entry=config_entry)
            for description in descriptions
        ),
        True,
    )


class GrowattSelect(CoordinatorEntity, SelectEntity):
    """A writable Growatt enumerated holding-register select."""

    def __init__(self, coordinator, description, entry):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, description.key)
        self.entity_description: GrowattSelectEntityDescription = description
        self._config_entry = entry
        self._attr_options = list(description.options_map)
        # Reverse map: raw register value -> option label.
        self._value_to_option = {v: k for k, v in description.options_map.items()}

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_SERIAL_NUMBER])},
            manufacturer="Growatt",
            model=entry.data[CONF_MODEL],
            sw_version=entry.data[CONF_FIRMWARE],
            name=entry.data[CONF_NAME],
        )

    @property
    def name(self) -> str:
        return f"{self._config_entry.data[CONF_NAME]} {self.entity_description.name}"

    @property
    def unique_id(self) -> Optional[str]:
        return (
            f"{DOMAIN}_{self._config_entry.data[CONF_SERIAL_NUMBER]}_"
            f"{self.entity_description.key}"
        )

    @property
    def current_option(self) -> str | None:
        raw = self.coordinator.data.get(self.entity_description.key)
        if raw is None:
            return None
        return self._value_to_option.get(int(raw))

    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the backing holding register."""
        if option not in self.entity_description.options_map:
            _LOGGER.error("Unknown option %s for %s", option, self.entity_description.key)
            return

        register = self.coordinator.get_holding_register_by_name(
            self.entity_description.key
        )
        if register is None:
            _LOGGER.error(
                "No holding register found for %s", self.entity_description.key
            )
            return

        await self.coordinator.write_register(
            register.register, self.entity_description.options_map[option]
        )
        self._attr_current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (raw := self.coordinator.data.get(self.entity_description.key)) is None:
            return
        self._attr_current_option = self._value_to_option.get(int(raw))
        self.async_write_ha_state()
