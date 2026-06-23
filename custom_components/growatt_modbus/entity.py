"""Shared entity base and device helpers for the Growatt Modbus integration."""
from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FIRMWARE, CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import GrowattConfigEntry, GrowattLocalCoordinator


def growatt_device_info(entry: GrowattConfigEntry) -> DeviceInfo:
    """Device-registry info for the main inverter device of a config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_SERIAL_NUMBER])},
        manufacturer="Growatt",
        model=entry.data[CONF_MODEL],
        sw_version=entry.data[CONF_FIRMWARE],
        name=entry.data[CONF_NAME],
    )


def entity_translation_key(key: str) -> str:
    """Slugify a register name into a valid entity translation_key.

    Register names are used verbatim as entity ``key``s; a few contain spaces or
    upper-case (e.g. ``"inverter mode"``), which are not valid translation keys.
    """
    return key.lower().replace(" ", "_")


class GrowattEntity(CoordinatorEntity[GrowattLocalCoordinator]):
    """Base for entities backed by the device coordinator.

    Centralises the per-platform boilerplate: ``has_entity_name``, storing the
    config entry, and grouping the entity under the main inverter device.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GrowattLocalCoordinator,
        entry: GrowattConfigEntry,
        context: Any = None,
    ) -> None:
        """Store the entry and attach the shared device info."""
        super().__init__(coordinator, context)
        self._config_entry = entry
        self._attr_device_info = growatt_device_info(entry)
