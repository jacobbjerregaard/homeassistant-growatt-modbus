"""Entity description types for the Growatt integration.

Each platform's register-backed entities are declared as a table of these
descriptions (see inverter.py / storage.py). They extend the Home Assistant
description with the few extra fields this integration needs; ``key`` is
already required by ``EntityDescription`` itself and carries the Growatt
register name.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription


@dataclass(frozen=True, kw_only=True)
class GrowattSensorEntityDescription(SensorEntityDescription):
    """Describes a Growatt sensor entity."""

    # Daily totals that the inverter resets at midnight; the coordinator
    # zeroes them locally so the graph does not carry yesterday's value.
    midnight_reset: bool = False


@dataclass(frozen=True, kw_only=True)
class GrowattNumberEntityDescription(NumberEntityDescription):
    """Describes a writable Growatt holding-register number entity."""


@dataclass(frozen=True, kw_only=True)
class GrowattSelectEntityDescription(SelectEntityDescription):
    """Describes a writable Growatt holding-register select entity."""

    # Maps the displayed option label to the raw register value to write.
    options_map: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class GrowattSwitchEntityDescription(SwitchEntityDescription):
    """Describes a writable Growatt holding-register switch entity."""
