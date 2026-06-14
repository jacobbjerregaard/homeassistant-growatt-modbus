"""Time platform: start/end times for the battery time-of-use slots."""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GrowattConfigEntry
from .tou import read_slot_fields, slot_device_info, slot_unique_id, write_slot_field

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the time-of-use start/end time entities."""
    coordinator = config_entry.runtime_data.main_coordinator
    slots = config_entry.runtime_data.device.tou_slots

    entities: list[GrowattSlotTime] = []
    for slot in range(1, slots + 1):
        coordinator.get_keys_by_name({f"tou_slot_{slot}_word1", f"tou_slot_{slot}_word2"}, True)
        entities.append(GrowattSlotTime(coordinator, config_entry, slot, "start"))
        entities.append(GrowattSlotTime(coordinator, config_entry, slot, "end"))

    async_add_entities(entities, True)


class GrowattSlotTime(CoordinatorEntity, TimeEntity):
    """Start or end time of a battery time-of-use slot."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, slot: int, edge: str):
        super().__init__(coordinator, f"tou_slot_{slot}_word1")
        self._entry = entry
        self._slot = slot
        self._edge = edge  # "start" or "end"
        self._attr_name = f"Slot {slot} {edge.capitalize()} Time"
        self._attr_unique_id = slot_unique_id(entry, slot, f"{edge}_time")
        self._attr_device_info = slot_device_info(entry)

    @property
    def native_value(self) -> dt_time | None:
        fields = read_slot_fields(self.coordinator, self._slot)
        return dt_time(
            hour=fields[f"{self._edge}_hour"], minute=fields[f"{self._edge}_minute"]
        )

    async def async_set_value(self, value: dt_time) -> None:
        await write_slot_field(
            self.coordinator,
            self._slot,
            **{f"{self._edge}_hour": value.hour, f"{self._edge}_minute": value.minute},
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
