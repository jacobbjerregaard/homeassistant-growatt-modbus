"""Diagnostics support for the Growatt Modbus integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from . import GrowattConfigEntry
from .const import CONF_SERIAL_NUMBER

TO_REDACT = {CONF_SERIAL_NUMBER, CONF_IP_ADDRESS, "serial_number"}


def _coordinator_diagnostics(coordinator) -> dict[str, Any] | None:
    if coordinator is None:
        return None
    return {
        "update_interval": str(coordinator.update_interval),
        "last_update_success": coordinator.last_update_success,
        "data": dict(coordinator.data or {}),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GrowattConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinators": {
            "main": _coordinator_diagnostics(runtime.main_coordinator),
            "power": _coordinator_diagnostics(runtime.power_coordinator),
        },
    }
