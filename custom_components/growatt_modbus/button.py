"""Button platform for the Growatt Modbus integration.

Exposes device-level actions; currently a "Sync device time" button that writes
the Home Assistant host clock to the inverter (holding registers 45-50).
"""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import (
    CONF_MODEL,
    CONF_NAME,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GrowattConfigEntry
from .const import (
    CONF_FIRMWARE,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Writes go to the inverter over a single Modbus connection (serialized by the
# transport lock); be explicit and let Home Assistant issue them one at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GrowattConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Growatt button entities for this config entry."""
    device = config_entry.runtime_data.device
    async_add_entities([GrowattSyncTimeButton(device, config_entry)])


class GrowattSyncTimeButton(ButtonEntity):
    """Writes the current host time to the inverter clock when pressed."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Sync device time"

    def __init__(self, device, entry):
        self._device = device
        self._attr_unique_id = (
            f"{DOMAIN}_{entry.data[CONF_SERIAL_NUMBER]}_sync_device_time"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_SERIAL_NUMBER])},
            manufacturer="Growatt",
            model=entry.data[CONF_MODEL],
            sw_version=entry.data[CONF_FIRMWARE],
            name=entry.data[CONF_NAME],
        )

    async def async_press(self) -> None:
        """Sync the device clock to the host time."""
        drift = await self._device.sync_time()
        _LOGGER.info("Synced Growatt device time; drift before sync was %s", drift)
