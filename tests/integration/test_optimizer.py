"""Tests for the EMHASS optimizer bridge (read-only Phase 1).

The Modbus wire is faked (via the shared ``setup_storage`` fixture, which keeps
the fake transport patched across the options reload) and the EMHASS HTTP wire
is faked via ``aioclient_mock``; the plan parsing, entity wiring and service are
all real.
"""
from datetime import timedelta

import aiohttp

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.growatt_modbus.API.device_type.base import ATTR_AC_CHARGE_ENABLED
from custom_components.growatt_modbus.API.device_type.storage_120 import (
    encode_time_slot,
    time_slot_register,
)
from custom_components.growatt_modbus.const import (
    CONF_BATTERY_MODULES,
    CONF_EMHASS_URL,
    CONF_OPTIMIZER_ENABLED,
    CONF_OPTIMIZER_INTERVAL,
    CONF_POWER_SCAN_ENABLED,
    CONF_POWER_SCAN_INTERVAL,
    CONF_TOU_SLOTS,
    DOMAIN,
)
from custom_components.growatt_modbus.optimizer import read_plan

TEST_SERIAL = "TESTSERIAL0001"
EMHASS_URL = "http://emhass.local:5000"


def _publish_hourly_batt_forecast(hass, hourly_values, grid_values=None) -> None:
    """Publish a regular 24-step hourly EMHASS battery (and grid) forecast."""
    base = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def _series(values):
        return [
            {
                "date": (base + timedelta(hours=h)).isoformat(),
                "value": values[h],
            }
            for h in range(len(values))
        ]

    hass.states.async_set(
        "sensor.p_batt_forecast",
        str(hourly_values[0]),
        {"forecasts": _series(hourly_values)},
    )
    if grid_values is not None:
        hass.states.async_set(
            "sensor.p_grid_forecast",
            str(grid_values[0]),
            {"forecasts": _series(grid_values)},
        )


def _slot_registers(reg, fake):
    return [(r, v) for r, v in fake.writes if r == reg]


def _publish_emhass_sensors(hass) -> None:
    """Simulate the sensors a running EMHASS instance publishes into HA."""
    hass.states.async_set(
        "sensor.p_batt_forecast",
        "-1500",
        {
            "unit_of_measurement": "W",
            "forecasts": [
                {"date": "2026-06-16T10:00:00", "p_batt_forecast": -1500},
                {"date": "2026-06-16T11:00:00", "p_batt_forecast": 0},
            ],
        },
    )
    hass.states.async_set("sensor.soc_batt_forecast", "65")
    hass.states.async_set("sensor.p_pv_forecast", "3200")
    hass.states.async_set("sensor.p_load_forecast", "800")
    hass.states.async_set("sensor.unit_load_cost", "1.42")
    hass.states.async_set("sensor.optim_status", "Optimal")


async def _enable_emhass(hass, entry, **extra_options) -> None:
    """Turn on the optimizer by updating options; triggers an entry reload."""
    hass.config_entries.async_update_entry(
        entry, options={CONF_EMHASS_URL: EMHASS_URL, **extra_options}
    )
    await hass.async_block_till_done()


def _state_for(hass, key):
    eid = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_{TEST_SERIAL}_{key}"
    )
    return hass.states.get(eid) if eid else None


# --- pure plan reading -----------------------------------------------------


def test_read_plan_parses_published_sensors(hass):
    _publish_emhass_sensors(hass)

    plan = read_plan(hass)

    assert plan.status == "Optimal"
    assert plan.battery_power == -1500.0
    assert plan.battery_soc == 65.0
    assert plan.pv_power == 3200.0
    assert plan.load_power == 800.0
    assert plan.unit_cost == 1.42
    assert plan.battery_power_forecast is not None
    assert plan.updated is not None


def test_read_plan_handles_missing_and_unavailable(hass):
    hass.states.async_set("sensor.optim_status", STATE_UNAVAILABLE)
    # p_batt_forecast not published at all.

    plan = read_plan(hass)

    assert plan.status is None
    assert plan.battery_power is None
    assert plan.battery_soc is None


def test_read_plan_ignores_non_numeric_value(hass):
    hass.states.async_set("sensor.p_batt_forecast", "not-a-number")

    plan = read_plan(hass)

    assert plan.battery_power is None


# --- diagnostic sensors ----------------------------------------------------


async def test_diagnostic_sensors_created_and_populated(hass, setup_storage):
    entry, _fake = setup_storage
    _publish_emhass_sensors(hass)
    await _enable_emhass(hass, entry)

    assert _state_for(hass, "optimizer_status").state == "Optimal"
    assert float(_state_for(hass, "optimizer_battery_power_target").state) == -1500.0
    assert float(_state_for(hass, "optimizer_battery_soc_target").state) == 65.0
    assert _state_for(hass, "optimizer_battery_power_target").attributes.get("forecast")
    assert _state_for(hass, "optimizer_plan_updated").state not in (None, "unknown")


async def test_no_optimizer_sensors_without_emhass_url(hass, setup_storage):
    # setup_storage is configured without an EMHASS URL.
    assert _state_for(hass, "optimizer_status") is None


# --- run_optimization service ---------------------------------------------


async def test_run_optimization_service_triggers_emhass(
    hass, setup_storage, aioclient_mock
):
    entry, _fake = setup_storage
    aioclient_mock.post(f"{EMHASS_URL}/action/dayahead-optim", text="ok")
    aioclient_mock.post(f"{EMHASS_URL}/action/publish-data", text="ok")
    await _enable_emhass(hass, entry)

    await hass.services.async_call(DOMAIN, "run_optimization", {}, blocking=True)
    await hass.async_block_till_done()

    posted = [str(url) for _m, url, _d, _h in aioclient_mock.mock_calls]
    assert f"{EMHASS_URL}/action/dayahead-optim" in posted
    assert f"{EMHASS_URL}/action/publish-data" in posted


# --- options flow EMHASS connection check ---------------------------------


def _options_input(**overrides) -> dict:
    data = {
        CONF_SCAN_INTERVAL: 60,
        CONF_POWER_SCAN_ENABLED: False,
        CONF_POWER_SCAN_INTERVAL: 5,
        CONF_BATTERY_MODULES: 0,
        CONF_TOU_SLOTS: 0,
        CONF_OPTIMIZER_INTERVAL: 300,
    }
    data.update(overrides)
    return data


async def test_options_flow_rejects_unreachable_emhass(
    hass, setup_storage, aioclient_mock
):
    entry, _fake = setup_storage
    aioclient_mock.get(EMHASS_URL, exc=aiohttp.ClientError("refused"))

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=_options_input(emhass_url=EMHASS_URL)
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "emhass_connection"}


async def test_options_flow_accepts_reachable_emhass(
    hass, setup_storage, aioclient_mock
):
    entry, _fake = setup_storage
    aioclient_mock.get(EMHASS_URL, text="<html>EMHASS</html>")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=_options_input(emhass_url=EMHASS_URL)
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"][CONF_EMHASS_URL] == EMHASS_URL


# --- Phase 2: day-ahead TOU compile (actuation) ---------------------------


async def test_compile_writes_tou_slots_when_enabled(hass, setup_storage):
    entry, fake = setup_storage
    values = [0] * 24
    values[2] = values[3] = -2000  # charge 02:00-04:00 -> Battery First
    values[18] = values[19] = 1500  # self-consume discharge -> Load First (dropped)
    _publish_hourly_batt_forecast(hass, values)

    await _enable_emhass(hass, entry, **{CONF_OPTIMIZER_ENABLED: True})

    # Slot 1 = 02:00-04:00 Battery First, enabled.
    base = time_slot_register(1)
    reg1, reg2 = encode_time_slot(2, 0, 4, 0, 1, True)
    assert (base, reg1) in fake.writes
    assert (base + 1, reg2) in fake.writes

    # Unused slot 2 is written disabled so a stale window can't linger.
    base2 = time_slot_register(2)
    d1, d2 = encode_time_slot(0, 0, 0, 0, 0, False)
    assert (base2, d1) in fake.writes
    assert (base2 + 1, d2) in fake.writes

    # AC charge enabled because the plan charges from grid.
    ac_reg = entry.runtime_data.main_coordinator.get_holding_register_by_name(
        ATTR_AC_CHARGE_ENABLED
    )
    assert ac_reg is not None
    assert (ac_reg.register, 1) in fake.writes


async def test_export_window_maps_to_grid_first(hass, setup_storage):
    entry, fake = setup_storage
    values = [0] * 24
    grid = [0] * 24
    values[19] = values[20] = 2500  # discharging 19:00-21:00
    grid[19] = grid[20] = -2500  # ...and exporting -> Grid First
    _publish_hourly_batt_forecast(hass, values, grid_values=grid)

    await _enable_emhass(hass, entry, **{CONF_OPTIMIZER_ENABLED: True})

    base = time_slot_register(1)
    reg1, reg2 = encode_time_slot(19, 0, 21, 0, 2, True)  # priority 2 = Grid First
    assert (base, reg1) in fake.writes
    assert (base + 1, reg2) in fake.writes


async def test_no_tou_writes_when_optimizer_disabled(hass, setup_storage):
    entry, fake = setup_storage
    values = [0] * 24
    values[2] = -2000
    _publish_hourly_batt_forecast(hass, values)

    await _enable_emhass(hass, entry)  # URL set, actuation left off

    assert _slot_registers(time_slot_register(1), fake) == []


async def test_compile_without_plan_leaves_slots_untouched(hass, setup_storage):
    entry, fake = setup_storage
    # No forecast published at all.

    await _enable_emhass(hass, entry, **{CONF_OPTIMIZER_ENABLED: True})

    assert _slot_registers(time_slot_register(1), fake) == []


async def test_run_optimization_compiles_when_enabled(
    hass, setup_storage, aioclient_mock
):
    entry, fake = setup_storage
    aioclient_mock.post(f"{EMHASS_URL}/action/dayahead-optim", text="ok")
    aioclient_mock.post(f"{EMHASS_URL}/action/publish-data", text="ok")
    values = [0] * 24
    values[2] = values[3] = -2000
    _publish_hourly_batt_forecast(hass, values)
    await _enable_emhass(hass, entry, **{CONF_OPTIMIZER_ENABLED: True})

    fake.writes.clear()
    await hass.services.async_call(DOMAIN, "run_optimization", {}, blocking=True)
    await hass.async_block_till_done()

    assert _slot_registers(time_slot_register(1), fake)
