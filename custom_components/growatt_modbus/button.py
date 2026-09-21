"""Button platform for the Growatt Modbus integration.

Exposes device-level actions; currently a "Sync device time" button that writes
Home Assistant's local time to the inverter (holding registers 45-50).
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import (
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from pymodbus.exceptions import ConnectionException

from .api.exception import ModbusException
from .const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from .coordinator import GrowattConfigEntry
from .entity import growatt_device_info

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
        self._attr_device_info = growatt_device_info(entry)

    async def async_press(self) -> None:
        """Sync the device clock to Home Assistant's local time."""
        try:
            drift = await self._device.sync_time(dt_util.now())
        except (ModbusException, ConnectionException, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err
        _LOGGER.info("Synced Growatt device time; drift before sync was %s", drift)
