"""Data update coordinator and runtime data for the Growatt Modbus integration."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from pymodbus.exceptions import ConnectionException

from .api.device_type.base import GrowattDeviceRegisters
from .api.exception import ModbusException
from .api.utils import RegisterKeys
from .const import DOMAIN

if TYPE_CHECKING:
    from .api.device import GrowattDevice
    from .optimizer import EmhassOptimizerCoordinator

_LOGGER = logging.getLogger(__name__)

# Minimum time between reconnect attempts while the Modbus link is down. A
# reconnect to an unreachable host blocks for the full connect timeout, so it
# is not retried on every poll of a fast (e.g. 5 s) power coordinator.
RECONNECT_INTERVAL = 60.0


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
        self._connection_lost = False
        self._last_reconnect: float | None = None
        # Serialises read-modify-write of the packed time-of-use slot
        # registers, so two field changes cannot interleave and undo each other.
        self.tou_lock = asyncio.Lock()
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
        except ConnectionException as err:
            if not self._connection_lost:
                self._connection_lost = True
                _LOGGER.warning(
                    "Modbus connection got interrupted, retrying to reconnect: %s",
                    err,
                )
            await self._async_try_reconnect()
            # Surface the outage to HA so the entities go unavailable instead
            # of silently keeping their last (now stale) values.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_interrupted",
            ) from err
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_response",
            ) from err
        except ModbusException as err:
            # The device answered, but rejected the read (illegal address,
            # busy, ...). Surface it rather than letting the affected sensors
            # silently keep their last value.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if self._connection_lost:
            self._connection_lost = False
            _LOGGER.info("Modbus connection restored")

        status = self.growatt_api.status(data)
        if status:
            data["status"] = status

        return data

    async def _async_try_reconnect(self) -> None:
        """Reconnect, at most once per RECONNECT_INTERVAL while the link is down.

        This used to retry only on every 60th failed poll, which at the default
        60 s scan interval meant one attempt an hour.
        """
        now = time.monotonic()
        if (
            self._last_reconnect is not None
            and now - self._last_reconnect < RECONNECT_INTERVAL
        ):
            return
        self._last_reconnect = now
        try:
            await self.growatt_api.connect()
        except Exception as err:  # noqa: BLE001 - reconnect is best-effort
            _LOGGER.debug("Modbus reconnect failed: %s", err)

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

    async def read_holding_words(self, start: int, count: int) -> list[int]:
        """Read ``count`` raw holding registers from the device, bypassing
        the polled data (used for read-modify-write of packed registers)."""
        try:
            values = await self.growatt_api.read_raw_holding_registers(start, count)
        except (ModbusException, ConnectionException, TimeoutError) as err:
            raise _write_failed(err) from err
        return [values[start + offset] for offset in range(count)]

    async def write_register(self, register, payload):
        try:
            await self.growatt_api.write_register(register, payload)
        except (ModbusException, ConnectionException, TimeoutError) as err:
            raise _write_failed(err) from err

    async def write_register_value(self, register, value):
        try:
            await self.growatt_api.write_register_value(register, value)
        except (ModbusException, ConnectionException, TimeoutError) as err:
            raise _write_failed(err) from err


def _write_failed(err: Exception) -> HomeAssistantError:
    """A user-facing error for a failed write, instead of a raw traceback."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="write_failed",
        translation_placeholders={"error": str(err) or type(err).__name__},
    )


# Config entry whose runtime_data holds the device and its coordinators.
type GrowattConfigEntry = ConfigEntry[GrowattRuntimeData]
