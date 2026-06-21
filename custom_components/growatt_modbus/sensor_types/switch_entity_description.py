"""Sensor Entity Description for the Growatt integration."""
from __future__ import annotations
from dataclasses import dataclass
from homeassistant.components.switch import SwitchEntityDescription
@dataclass(frozen=True, kw_only=True)
class GrowattSwitchRequiredKeysMixin:
    """Mixin for required keys."""
    key: str
@dataclass(frozen=True, kw_only=True)
class GrowattSwitchEntityDescription(SwitchEntityDescription, GrowattSwitchRequiredKeysMixin):
    """Describes Growatt sensor entity."""
    