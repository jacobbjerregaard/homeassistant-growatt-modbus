"""Options flow: the settings a user can change after setup.

Split out of config_flow.py, which was 798 lines covering three distinct
flows. This one only edits an existing entry - scan intervals, battery and
time-of-use slot counts, and the optional EMHASS optimizer.
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BATTERY_MAX_POWER,
    CONF_BATTERY_MODULES,
    CONF_EMHASS_SENSOR_BATT_POWER,
    CONF_EMHASS_SENSOR_BATT_SOC,
    CONF_EMHASS_SENSOR_GRID,
    CONF_EMHASS_SENSOR_STATUS,
    CONF_EMHASS_TOKEN,
    CONF_EMHASS_URL,
    CONF_OPTIMIZER_ENABLED,
    CONF_OPTIMIZER_INTERVAL,
    CONF_OPTIMIZER_SOC_SENSOR,
    CONF_POWER_SCAN_ENABLED,
    CONF_POWER_SCAN_INTERVAL,
    CONF_TOU_SLOTS,
    DEFAULT_OPTIMIZER_INTERVAL,
)
from .emhass_client import EmhassClient, EmhassError


class GrowattOptionsFlowHandler(config_entries.OptionsFlow):
    """Edit polling and EMHASS optimizer options, grouped into two sections."""

    def _current(self, user_input=None) -> dict:
        """Active values: setup data, overridden by options, then any input."""
        return {
            **self.config_entry.data,
            **self.config_entry.options,
            **(user_input or {}),
        }

    def _save(self, user_input: dict) -> ConfigFlowResult:
        """Persist one section, preserving the settings of the other section."""
        return self.async_create_entry(
            title="", data={**self.config_entry.options, **user_input}
        )

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Choose which group of options to edit."""
        return self.async_show_menu(
            step_id="init", menu_options=["general", "optimizer"]
        )

    async def async_step_general(self, user_input=None) -> ConfigFlowResult:
        """Polling and device options."""
        if user_input is not None:
            return self._save(user_input)

        current = self._current()
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, 60),
                ): int,
                vol.Required(
                    CONF_POWER_SCAN_ENABLED,
                    default=current.get(CONF_POWER_SCAN_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_POWER_SCAN_INTERVAL,
                    default=current.get(CONF_POWER_SCAN_INTERVAL, 5),
                ): int,
                vol.Required(
                    CONF_BATTERY_MODULES,
                    default=current.get(CONF_BATTERY_MODULES, 0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=10, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                vol.Required(
                    CONF_TOU_SLOTS,
                    default=current.get(CONF_TOU_SLOTS, 0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=9, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
            }
        )
        return self.async_show_form(step_id="general", data_schema=data_schema)

    async def async_step_optimizer(self, user_input=None) -> ConfigFlowResult:
        """EMHASS optimizer options (connection, control and source sensors)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = (user_input.get(CONF_EMHASS_URL) or "").strip()
            if url:
                client = EmhassClient(
                    async_get_clientsession(self.hass),
                    url,
                    user_input.get(CONF_EMHASS_TOKEN) or None,
                )
                try:
                    await client.async_test_connection()
                except EmhassError:
                    errors["base"] = "emhass_connection"
            if not errors:
                return self._save(user_input)

        current = self._current(user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EMHASS_URL,
                    description={"suggested_value": current.get(CONF_EMHASS_URL)},
                ): str,
                vol.Optional(
                    CONF_EMHASS_TOKEN,
                    description={"suggested_value": current.get(CONF_EMHASS_TOKEN)},
                ): str,
                vol.Required(
                    CONF_OPTIMIZER_ENABLED,
                    default=current.get(CONF_OPTIMIZER_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_OPTIMIZER_SOC_SENSOR,
                    description={
                        "suggested_value": current.get(CONF_OPTIMIZER_SOC_SENSOR)
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_OPTIMIZER_INTERVAL,
                    default=current.get(
                        CONF_OPTIMIZER_INTERVAL, DEFAULT_OPTIMIZER_INTERVAL
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=3600, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                vol.Optional(
                    CONF_BATTERY_MAX_POWER,
                    default=current.get(CONF_BATTERY_MAX_POWER, 0),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=50000,
                        step=100,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="W",
                    ),
                ),
                vol.Optional(
                    CONF_EMHASS_SENSOR_BATT_POWER,
                    description={
                        "suggested_value": current.get(CONF_EMHASS_SENSOR_BATT_POWER)
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_EMHASS_SENSOR_BATT_SOC,
                    description={
                        "suggested_value": current.get(CONF_EMHASS_SENSOR_BATT_SOC)
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_EMHASS_SENSOR_GRID,
                    description={
                        "suggested_value": current.get(CONF_EMHASS_SENSOR_GRID)
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_EMHASS_SENSOR_STATUS,
                    description={
                        "suggested_value": current.get(CONF_EMHASS_SENSOR_STATUS)
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="optimizer", data_schema=data_schema, errors=errors
        )
