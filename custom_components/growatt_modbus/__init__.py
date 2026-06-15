"""The Growatt server PV inverter sensor integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from collections.abc import Callable, Sequence
from typing import Any

from pymodbus.exceptions import ConnectionException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_time_change,
)

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .API.device_type.base import GrowattDeviceRegisters
from .API.utils import RegisterKeys
from .API.const import DeviceTypes
from .API.client import GrowattSerial, GrowattNetwork
from .API.device import GrowattDevice
from .services import async_setup_services
from .const import (
    CONF_LAYER,
    CONF_SERIAL,
    CONF_TCP,
    CONF_UDP,
    CONF_FRAME,
    CONF_SERIAL_PORT,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_POWER_SCAN_ENABLED,
    CONF_POWER_SCAN_INTERVAL,
    CONF_BATTERY_MODULES,
    CONF_TOU_SLOTS,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Register integration-level services once."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GrowattConfigEntry
) -> bool:
    """Load the saved entities."""

    if entry.data[CONF_LAYER] == CONF_SERIAL:
        device_layer = GrowattSerial(
            entry.data[CONF_SERIAL_PORT],
            entry.data[CONF_BAUDRATE],
            entry.data[CONF_STOPBITS],
            entry.data[CONF_PARITY],
            entry.data[CONF_BYTESIZE],
        )
    elif entry.data[CONF_LAYER] in (CONF_TCP, CONF_UDP):
        device_layer = GrowattNetwork(
            entry.data[CONF_LAYER],
            entry.data[CONF_IP_ADDRESS],
            entry.data[CONF_PORT],
            entry.data[CONF_FRAME],
        )
    else:
        _LOGGER.warning(
            "Device layer %s is not supported right now",
            entry.data[CONF_LAYER],
        )
        return False

    device_type = DeviceTypes(entry.data[CONF_TYPE])
    battery_modules = int(
        entry.options.get(
            CONF_BATTERY_MODULES, entry.data.get(CONF_BATTERY_MODULES, 0)
        )
    )
    tou_slots = int(
        entry.options.get(CONF_TOU_SLOTS, entry.data.get(CONF_TOU_SLOTS, 0))
    )
    device = GrowattDevice(
        device_layer, device_type, entry.data[CONF_ADDRESS], battery_modules, tou_slots
    )

    await device.connect()

    # Auto-detect the battery module count (holding register 185) unless the
    # user pinned it via the options flow.
    if not battery_modules and device_type in (
        DeviceTypes.HYBRID_120,
        DeviceTypes.STORAGE_120,
    ):
        detected = await device.read_battery_module_count()
        if detected:
            device.set_battery_modules(detected)

    # Read each module's serial so its entities can be grouped under a
    # per-module device with a stable, serial-based identity.
    battery_module_serials: dict[int, str] = {}
    if device.battery_modules and device_type in (
        DeviceTypes.HYBRID_120,
        DeviceTypes.STORAGE_120,
    ):
        battery_module_serials = await device.read_battery_module_serials()

    # Options (set via the options flow) override the original setup data.
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data[CONF_SCAN_INTERVAL]
    )
    power_scan_enabled = entry.options.get(
        CONF_POWER_SCAN_ENABLED, entry.data[CONF_POWER_SCAN_ENABLED]
    )
    power_scan_interval = entry.options.get(
        CONF_POWER_SCAN_INTERVAL, entry.data[CONF_POWER_SCAN_INTERVAL]
    )

    # The main coordinator polls everything at the general interval. When the
    # faster power scan is enabled a second coordinator polls just the power
    # registers at the shorter interval; power entities subscribe to it.
    main_coordinator = GrowattLocalCoordinator(
        hass, device, timedelta(seconds=scan_interval), DOMAIN
    )
    power_coordinator: GrowattLocalCoordinator | None = None
    if power_scan_enabled:
        power_coordinator = GrowattLocalCoordinator(
            hass, device, timedelta(seconds=power_scan_interval), f"{DOMAIN}_power"
        )

    entry.runtime_data = GrowattRuntimeData(
        device=device,
        main_coordinator=main_coordinator,
        power_coordinator=power_coordinator,
        battery_module_serials=battery_module_serials,
    )

    # Reload the entry when the user changes options so new intervals apply.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: GrowattConfigEntry
) -> None:
    """Reload the integration when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GrowattConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry.runtime_data.device.close()

    return unload_ok


@dataclass
class GrowattRuntimeData:
    """Runtime objects shared between the platforms of one config entry."""

    device: GrowattDevice
    main_coordinator: "GrowattLocalCoordinator"
    power_coordinator: "GrowattLocalCoordinator | None" = None
    # {slot: serial} for battery modules that report a serial number.
    battery_module_serials: dict[int, str] = field(default_factory=dict)


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
        status = None
        data = {}

        try:
            data = await self.growatt_api.update(self.keys)
            self._failed_update_count = 0
        except ConnectionException:
            if self._failed_update_count % 60 == 0:
                _LOGGER.warning("Modbus connection got interupted retrying to reconnect", exc_info=True)
                await self.growatt_api.connect()
            self._failed_update_count += 1
            status = "not_connected"
        except asyncio.TimeoutError:
            self._failed_update_count += 1
            status = "no_response"

        if status is None:
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
        self, names: Sequence[str], update_keys: bool = False
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
