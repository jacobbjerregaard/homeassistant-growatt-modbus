"""Services for the Growatt Modbus integration."""
from __future__ import annotations

import logging
from collections.abc import Iterator

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .API.device_type.storage_120 import (
    TIME_SLOT_PRIORITIES,
    encode_time_slot,
    time_slot_register,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TIME_SLOT = "set_time_slot"

SET_TIME_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=9)),
        vol.Required("start_time"): cv.time,
        vol.Required("end_time"): cv.time,
        vol.Required("priority"): vol.In(list(TIME_SLOT_PRIORITIES)),
        vol.Required("enabled"): cv.boolean,
    }
)


def _devices_for_call(hass: HomeAssistant, device_ids: list[str]) -> Iterator:
    registry = dr.async_get(hass)
    for device_id in device_ids:
        device_entry = registry.async_get(device_id)
        if device_entry is None:
            continue
        for entry_id in device_entry.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == DOMAIN and getattr(entry, "runtime_data", None):
                yield entry.runtime_data.device
                break


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-level services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_TIME_SLOT):
        return

    async def handle_set_time_slot(call: ServiceCall) -> None:
        start = call.data["start_time"]
        end = call.data["end_time"]
        priority = TIME_SLOT_PRIORITIES[call.data["priority"]]
        reg1, reg2 = encode_time_slot(
            start.hour, start.minute, end.hour, end.minute, priority, call.data["enabled"]
        )
        base = time_slot_register(call.data["slot"])

        devices = list(_devices_for_call(hass, call.data["device_id"]))
        if not devices:
            _LOGGER.warning("set_time_slot: no Growatt device matched the target")
            return

        for device in devices:
            await device.write_register_value(base, reg1)
            await device.write_register_value(base + 1, reg2)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TIME_SLOT, handle_set_time_slot, schema=SET_TIME_SLOT_SCHEMA
    )
