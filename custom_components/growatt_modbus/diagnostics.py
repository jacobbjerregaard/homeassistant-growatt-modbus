"""Diagnostics support for the Growatt Modbus integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .api.device_type.attrs import ATTR_SERIAL_NUMBER
from .const import CONF_EMHASS_TOKEN, CONF_EMHASS_URL, CONF_SERIAL_NUMBER
from .coordinator import GrowattConfigEntry

# Diagnostics are routinely attached to public GitHub issues: redact anything
# that identifies the installation or grants access to another service.
TO_REDACT = {
    CONF_SERIAL_NUMBER,
    CONF_IP_ADDRESS,
    CONF_EMHASS_TOKEN,
    CONF_EMHASS_URL,
    ATTR_SERIAL_NUMBER,
}


def _redact_register_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact the inverter and per-module serials from polled register data.

    Module serials are keyed ``battery_module_<n>_serial_number``, so they are
    matched by suffix rather than listed in TO_REDACT.
    """
    redacted = async_redact_data(data, TO_REDACT)
    return {
        key: REDACTED if key.endswith("_serial_number") else value
        for key, value in redacted.items()
    }


def _coordinator_diagnostics(coordinator) -> dict[str, Any] | None:
    if coordinator is None:
        return None
    return {
        "update_interval": str(coordinator.update_interval),
        "last_update_success": coordinator.last_update_success,
        "data": _redact_register_data(dict(coordinator.data or {})),
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
