"""Repair config entries that were set up with an empty inverter serial.

Up to 0.22, the config flow read the serial from holding register 23 for every
v1.24-family device. On the storage/hybrid types that register is empty - the
serial lives at holding 3001 - so those entries were created with ``""`` as
their serial and unique_id. Every identity derived from it was then built
around an empty string:

- the entry's unique_id (so a second such inverter could not be added),
- entity unique_ids: ``growatt_modbus__<key>`` instead of
  ``growatt_modbus_<serial>_<key>``,
- the inverter device: ``(growatt_modbus, "")``,
- battery-module devices: ``(growatt_modbus, "_battery_module_<module>")``.

The repair runs during setup, once the inverter is connected, rather than as a
config-entry version migration: a version migration runs before any connection
exists, and an unreachable inverter would leave the entry failed. It is also
idempotent - each run renames whatever still carries the empty-serial form -
so an interrupted run is completed on the next setup.

Entity renames go through the entity registry, which keeps each entity_id, so
history, long-term statistics, dashboards and automations are unaffected.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .api.device import GrowattDevice
from .api.device_type.attrs import ATTR_SERIAL_NUMBER
from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Unique_id prefix of entities created while the entry's serial was empty.
_EMPTY_SERIAL_PREFIX = f"{DOMAIN}__"
# Identifier prefix of battery-module devices created with an empty serial.
_EMPTY_SERIAL_MODULE_PREFIX = "_battery_module_"


async def _async_read_serial(device: GrowattDevice) -> str:
    """Read the inverter serial through the device's own register map."""
    try:
        data = await device.update(device.get_keys_by_name({ATTR_SERIAL_NUMBER}))
    except Exception as err:  # noqa: BLE001 - retried on the next setup
        _LOGGER.debug("Could not read the inverter serial: %s", err)
        return ""
    serial = data.get(ATTR_SERIAL_NUMBER)
    return serial.replace("\x00", "").strip() if isinstance(serial, str) else ""


async def async_repair_empty_serial(
    hass: HomeAssistant, entry, device: GrowattDevice
) -> None:
    """Give an entry set up with an empty serial its real one.

    Must run before the platforms are set up, so the entities they create
    use the repaired identities rather than creating duplicates.
    """
    serial = entry.data.get(CONF_SERIAL_NUMBER) or ""

    if not serial:
        serial = await _async_read_serial(device)
        if not serial:
            _LOGGER.warning(
                "This Growatt entry has no serial number and the inverter did "
                "not report one; it keeps working, and the repair is retried "
                "on the next restart"
            )
            return

        other = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, serial)
        if other is not None and other.entry_id != entry.entry_id:
            _LOGGER.warning(
                "Not repairing the empty serial number: another Growatt entry "
                "(%s) already uses serial %s",
                other.title,
                serial,
            )
            return

        _LOGGER.info("Repairing the empty serial number; the inverter is %s", serial)
        hass.config_entries.async_update_entry(
            entry, unique_id=serial, data={**entry.data, CONF_SERIAL_NUMBER: serial}
        )

    await _async_migrate_entities(hass, entry, serial)
    _migrate_devices(hass, entry, serial)


async def _async_migrate_entities(hass: HomeAssistant, entry, serial: str) -> None:
    registry = er.async_get(hass)
    new_prefix = f"{DOMAIN}_{serial}_"

    @callback
    def _migrate(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        uid = entity_entry.unique_id
        if not uid.startswith(_EMPTY_SERIAL_PREFIX):
            return None
        new_uid = new_prefix + uid[len(_EMPTY_SERIAL_PREFIX) :]
        if registry.async_get_entity_id(entity_entry.domain, DOMAIN, new_uid):
            # An entity with the repaired id already exists (e.g. both were
            # created at some point); renaming would collide. Leave the old
            # one for the user to remove rather than failing setup.
            _LOGGER.warning(
                "Not renaming %s: %s already exists", entity_entry.entity_id, new_uid
            )
            return None
        return {"new_unique_id": new_uid}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)


def _migrate_devices(hass: HomeAssistant, entry, serial: str) -> None:
    registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(registry, entry.entry_id):
        new_identifiers = set()
        changed = False
        for domain, identifier in device_entry.identifiers:
            if domain == DOMAIN and identifier == "":
                identifier, changed = serial, True
            elif domain == DOMAIN and identifier.startswith(
                _EMPTY_SERIAL_MODULE_PREFIX
            ):
                identifier, changed = f"{serial}{identifier}", True
            new_identifiers.add((domain, identifier))
        if not changed:
            continue
        if any(
            registry.async_get_device(identifiers={ident})
            for ident in new_identifiers - device_entry.identifiers
        ):
            _LOGGER.warning(
                "Not updating device %s: a device with the repaired identifier "
                "already exists",
                device_entry.name,
            )
            continue
        registry.async_update_device(device_entry.id, new_identifiers=new_identifiers)
