"""Shared helpers for the time-of-use slot entities.

A slot's start/end time, priority and enable flag are packed into two holding
registers. The entities below read the current register pair from the
coordinator data and rewrite it (read-modify-write) when a single field
changes.
"""
from __future__ import annotations

from homeassistant.const import CONF_MODEL, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo

from .API.device_type.storage_120 import (
    apply_time_slot_field,
    decode_time_slot,
    time_slot_register,
)
from .const import CONF_FIRMWARE, CONF_SERIAL_NUMBER, DOMAIN

TOU_PRIORITIES = {0: "Load First", 1: "Battery First", 2: "Grid First"}
TOU_PRIORITY_VALUES = {label: value for value, label in TOU_PRIORITIES.items()}


def slot_device_info(entry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_SERIAL_NUMBER])},
        manufacturer="Growatt",
        model=entry.data[CONF_MODEL],
        sw_version=entry.data[CONF_FIRMWARE],
        name=entry.data[CONF_NAME],
    )


def slot_unique_id(entry, slot: int, field: str) -> str:
    return f"{DOMAIN}_{entry.data[CONF_SERIAL_NUMBER]}_tou_slot_{slot}_{field}"


def read_slot_fields(coordinator, slot: int) -> dict:
    reg1 = int(coordinator.data.get(f"tou_slot_{slot}_word1") or 0)
    reg2 = int(coordinator.data.get(f"tou_slot_{slot}_word2") or 0)
    return decode_time_slot(reg1, reg2)


async def write_slot_field(coordinator, slot: int, **change) -> None:
    """Read-modify-write a single field of a time-of-use slot."""
    base = time_slot_register(slot)
    reg1 = int(coordinator.data.get(f"tou_slot_{slot}_word1") or 0)
    reg2 = int(coordinator.data.get(f"tou_slot_{slot}_word2") or 0)
    new1, new2 = apply_time_slot_field(reg1, reg2, **change)
    await coordinator.write_register_value(base, new1)
    await coordinator.write_register_value(base + 1, new2)
    await coordinator.async_request_refresh()
