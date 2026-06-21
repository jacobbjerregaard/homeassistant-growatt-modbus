"""Select Entity Description for the Growatt integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.select import SelectEntityDescription


@dataclass(frozen=True, kw_only=True)
class GrowattSelectRequiredKeysMixin:
    """Mixin for required keys."""

    key: str
    # Maps the displayed option label to the raw register value to write.
    options_map: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class GrowattSelectEntityDescription(
    SelectEntityDescription, GrowattSelectRequiredKeysMixin
):
    """Describes a writable Growatt holding-register select entity."""
