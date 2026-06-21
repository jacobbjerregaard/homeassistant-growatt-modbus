"""Number Entity Description for the Growatt integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntityDescription


@dataclass(frozen=True, kw_only=True)
class GrowattNumberRequiredKeysMixin:
    """Mixin for required keys."""

    key: str


@dataclass(frozen=True, kw_only=True)
class GrowattNumberEntityDescription(
    NumberEntityDescription, GrowattNumberRequiredKeysMixin
):
    """Describes a writable Growatt holding-register number entity."""
