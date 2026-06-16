"""Switch platform for the Growatt Modbus integration.

Exposes writable holding registers (e.g. AC charge enable) as switches.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_MODEL,
    CONF_NAME,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GrowattConfigEntry
from .const import (
    CONF_FIRMWARE,
    CONF_OPTIMIZER_ENABLED,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from .sensor_types.storage import STORAGE_SWITCH_TYPES
from .sensor_types.switch_entity_description import GrowattSwitchEntityDescription
from .tou import read_slot_fields, slot_device_info, slot_unique_id, write_slot_field

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt switches for this config entry."""
    # Switches are config registers; they poll on the main coordinator.
    coordinator = config_entry.runtime_data.main_coordinator
    supported_key_names = config_entry.runtime_data.device.get_register_names()

    descriptions = [
        description
        for description in STORAGE_SWITCH_TYPES
        if description.key in supported_key_names
    ]

    # Make sure the backing registers are part of the polled key set.
    coordinator.get_keys_by_name({description.key for description in descriptions}, True)

    entities: list = [
        GrowattSwitch(coordinator, description=description, entry=config_entry)
        for description in descriptions
    ]

    for slot in range(1, config_entry.runtime_data.device.tou_slots + 1):
        coordinator.get_keys_by_name({f"tou_slot_{slot}_word1"}, True)
        entities.append(GrowattSlotEnable(coordinator, config_entry, slot))

    # Master switch for the EMHASS optimizer's battery control (only when an
    # EMHASS instance is configured).
    if config_entry.runtime_data.optimizer is not None:
        entities.append(GrowattOptimizerSwitch(config_entry))

    async_add_entities(entities, True)


class GrowattOptimizerSwitch(SwitchEntity):
    """Enables/disables the EMHASS optimizer's control of the battery.

    Off keeps the optimizer read-only (diagnostics only). The state is persisted
    in the config-entry options so it survives restarts; toggling reloads the
    entry, which (re)applies the day-ahead plan when turned on.
    """

    _attr_has_entity_name = True
    _attr_name = "Optimizer Control"
    _attr_icon = "mdi:auto-fix"

    def __init__(self, entry: GrowattConfigEntry) -> None:
        self._entry = entry
        serial = entry.data[CONF_SERIAL_NUMBER]
        self._attr_unique_id = f"{DOMAIN}_{serial}_optimizer_control"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Growatt",
            model=entry.data[CONF_MODEL],
            sw_version=entry.data[CONF_FIRMWARE],
            name=entry.data[CONF_NAME],
        )

    @property
    def is_on(self) -> bool:
        optimizer = self._entry.runtime_data.optimizer
        return bool(optimizer and optimizer.enabled)

    async def _async_set(self, value: bool) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_OPTIMIZER_ENABLED: value},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)


class GrowattSlotEnable(CoordinatorEntity, SwitchEntity):
    """Enable flag of a battery time-of-use slot."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, slot: int):
        super().__init__(coordinator, f"tou_slot_{slot}_word1")
        self._slot = slot
        self._attr_name = f"Slot {slot} Enabled"
        self._attr_unique_id = slot_unique_id(entry, slot, "enabled")
        self._attr_device_info = slot_device_info(entry)

    @property
    def is_on(self) -> bool:
        return read_slot_fields(self.coordinator, self._slot)["enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await write_slot_field(self.coordinator, self._slot, enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await write_slot_field(self.coordinator, self._slot, enabled=False)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class GrowattSwitch(CoordinatorEntity, RestoreEntity, SwitchEntity):
    """A writable Growatt holding-register switch."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, description, entry):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, description.key)
        self.entity_description: GrowattSwitchEntityDescription = description
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

    async def _async_write(self, value: int) -> None:
        """Write the backing holding register and reflect the new state."""
        register = self.coordinator.get_holding_register_by_name(
            self.entity_description.key
        )
        if register is None:
            _LOGGER.error(
                "No holding register found for %s", self.entity_description.key
            )
            return

        await self.coordinator.write_register(register.register, value)
        # Optimistically reflect the change, then re-read from the device.
        self._attr_is_on = bool(value)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_write(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_write(0)

    async def async_added_to_hass(self) -> None:
        """Restore the last known state."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_is_on = state.state == STATE_ON

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (state := self.coordinator.data.get(self.entity_description.key)) is None:
            return
        self._attr_is_on = int(state) == 1
        self.async_write_ha_state()
