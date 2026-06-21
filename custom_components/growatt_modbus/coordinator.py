"""Data update coordinator and runtime data for the Growatt Modbus integration."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pymodbus.exceptions import ConnectionException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .API.device_type.base import GrowattDeviceRegisters
from .API.utils import RegisterKeys

if TYPE_CHECKING:
    from .API.device import GrowattDevice
    from .optimizer import EmhassOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class GrowattRuntimeData:
    """Runtime objects shared between the platforms of one config entry."""

    device: GrowattDevice
    main_coordinator: GrowattLocalCoordinator
    power_coordinator: GrowattLocalCoordinator | None = None
    # {slot: serial} for battery modules that report a serial number.
    battery_module_serials: dict[int, str] = field(default_factory=dict)
    # Present only when the EMHASS optimizer is configured for this entry.
    optimizer: EmhassOptimizerCoordinator | None = None


class GrowattLocalCoordinator(DataUpdateCoordinator):
    """Polls one set of Growatt registers at a fixed interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        growatt_api: GrowattDevice,
        update_interval: timedelta,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=update_interval,
        )
        self.data = {}
        self.growatt_api = growatt_api
        self._failed_update_count = 0
        self.keys = RegisterKeys()
        self._midnight_listeners: dict[
            CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]
        ] = {}

        # Unsub handle for the daily midnight-reset tracker. Created lazily when
        # the first midnight listener subscribes and cancelled when the last one
        # is removed, so it does not leak across reloads.
        self._midnight_unsub: CALLBACK_TYPE | None = None

    async def _async_update_data(self):
        """Fetch this coordinator's register set from the device."""
        try:
            data = await self.growatt_api.update(self.keys)
            self._failed_update_count = 0
        except ConnectionException as err:
            # Periodically attempt a reconnect while the link is down.
            if self._failed_update_count % 60 == 0:
                _LOGGER.warning(
                    "Modbus connection got interrupted, retrying to reconnect",
                    exc_info=True,
                )
                try:
                    await self.growatt_api.connect()
                except Exception:  # noqa: BLE001 - reconnect is best-effort
                    pass
            self._failed_update_count += 1
            # Surface the outage to HA so the entities go unavailable instead
            # of silently keeping their last (now stale) values.
            raise UpdateFailed("Modbus connection interrupted") from err
        except asyncio.TimeoutError as err:
            self._failed_update_count += 1
            raise UpdateFailed("No response from the Growatt device") from err

        status = self.growatt_api.status(data)
        if status:
            data["status"] = status

        return data

    @callback
    def midnight(self, datetime=None):
        for update_callback, context in set(self._midnight_listeners.values()):
            self.data.update({context: 0})
            update_callback()

    @callback
    def async_add_midnight_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listeners for midnight update."""
        schedule_refresh = not self._midnight_listeners

        @callback
        def remove_midnight_listener() -> None:
            """Remove midnight listener."""
            self._midnight_listeners.pop(remove_midnight_listener, None)
            # Cancel the daily tracker once the last listener is gone.
            if not self._midnight_listeners and self._midnight_unsub is not None:
                self._midnight_unsub()
                self._midnight_unsub = None

        self._midnight_listeners[remove_midnight_listener] = (update_callback, context)

        # First listener: set up the daily midnight tracker and keep its unsub.
        if schedule_refresh:
            self._midnight_unsub = async_track_time_change(
                self.hass, self.midnight, 0, 0, 0
            )

        return remove_midnight_listener

    @callback
    def get_keys_by_name(
        self, names: Collection[str], update_keys: bool = False
    ) -> RegisterKeys:
        """
        Loopup modbus register values based on name.
        Setting update_keys automaticly extends the list of keys to request.
        """
        keys = self.growatt_api.get_keys_by_name(names)
        if update_keys:
            self.keys.update(keys)

        return keys

    def get_input_register_by_name(self, name) -> GrowattDeviceRegisters | None:
        return self.growatt_api.get_input_register_by_name(name)
    def get_holding_register_by_name(self, name) -> GrowattDeviceRegisters | None:
        return self.growatt_api.get_holding_register_by_name(name)
    async def write_register(self, register, payload):
        await self.growatt_api.write_register(register, payload)
    async def write_register_value(self, register, value):
        await self.growatt_api.write_register_value(register, value)


# Config entry whose runtime_data holds the device and its coordinators.
type GrowattConfigEntry = ConfigEntry[GrowattRuntimeData]
