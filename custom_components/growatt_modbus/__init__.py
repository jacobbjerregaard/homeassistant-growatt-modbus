"""The Growatt server PV inverter sensor integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from pymodbus.exceptions import ConnectionException

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .API.const import DeviceTypes
from .API.client import GrowattModbusBase, GrowattSerial, GrowattNetwork
from .API.device import GrowattDevice
from .coordinator import (
    GrowattConfigEntry,
    GrowattLocalCoordinator,
    GrowattRuntimeData,
)
from .services import async_setup_services
from .optimizer import async_setup_optimizer
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
    CONF_SERIAL_NUMBER,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


# This integration is configured exclusively through config entries (the UI
# config flow); it has no YAML configuration. async_setup only registers
# integration-level services.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Register integration-level services once."""
    async_setup_services(hass)
    return True


async def _async_migrate_module_unique_ids(
    hass: HomeAssistant, entry: "GrowattConfigEntry", serials: dict[int, str]
) -> None:
    """Rename slot-based per-module entity unique_ids to serial-based ones.

    Pre-0.12 per-module entities were ``..._battery_module_<slot>_<field>``.
    Now that each module is identified by its serial, migrate the registry so
    the existing entities (and their history) are kept rather than orphaned.
    """
    inverter_serial = entry.data[CONF_SERIAL_NUMBER]
    old_prefix = f"{DOMAIN}_{inverter_serial}_battery_module_"

    @callback
    def _migrate(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        uid = entity_entry.unique_id
        if not uid.startswith(old_prefix):
            return None
        slot_str, sep, field = uid[len(old_prefix):].partition("_")
        if not sep or not slot_str.isdigit():
            return None
        serial = serials.get(int(slot_str))
        if not serial:
            return None
        new_uid = f"{DOMAIN}_{inverter_serial}_module_{serial}_{field}"
        if new_uid == uid:
            return None
        return {"new_unique_id": new_uid}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)


async def async_setup_entry(
    hass: HomeAssistant, entry: GrowattConfigEntry
) -> bool:
    """Load the saved entities."""

    device_layer: GrowattModbusBase
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

    try:
        await device.connect()
    except (ConnectionException, asyncio.TimeoutError, OSError) as err:
        # The inverter is unreachable right now (power-cycle, RS485 glitch).
        # Tell HA to retry setup with its normal backoff instead of failing.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

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
    # per-module device with a stable, serial-based identity. Retry a couple of
    # times so a transient read failure does not drop every module back to
    # slot-based naming for the whole session.
    battery_module_serials: dict[int, str] = {}
    if device.battery_modules and device_type in (
        DeviceTypes.HYBRID_120,
        DeviceTypes.STORAGE_120,
    ):
        for _attempt in range(3):
            battery_module_serials = await device.read_battery_module_serials()
            if battery_module_serials:
                break
        # Rename any existing slot-based per-module entities to the new
        # serial-based identity so their history survives the upgrade.
        if battery_module_serials:
            await _async_migrate_module_unique_ids(hass, entry, battery_module_serials)

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

    # Optional EMHASS optimizer: only wired up when an EMHASS URL is configured.
    # Phase 1 reads the published plan; it never drives the battery yet.
    optimizer = await async_setup_optimizer(hass, entry, main_coordinator)

    entry.runtime_data = GrowattRuntimeData(
        device=device,
        main_coordinator=main_coordinator,
        power_coordinator=power_coordinator,
        battery_module_serials=battery_module_serials,
        optimizer=optimizer,
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
