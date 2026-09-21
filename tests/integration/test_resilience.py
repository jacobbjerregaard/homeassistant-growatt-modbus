"""Tests for connection resilience and the per-module unique_id migration."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.growatt_modbus import _async_migrate_module_unique_ids
from custom_components.growatt_modbus.api.exception import (
    ModbusException,
    ModbusPortException,
)
from custom_components.growatt_modbus.const import CONF_SERIAL_NUMBER, DOMAIN


def _any_sensor_entity_id(hass, entry):
    registry = er.async_get(hass)
    for e in er.async_entries_for_config_entry(registry, entry.entry_id):
        if e.domain == "sensor":
            return e.entity_id
    raise AssertionError("no sensor entity found")


async def test_entities_unavailable_on_connection_loss(hass, setup_storage):
    entry, _fake = setup_storage
    entity_id = _any_sensor_entity_id(hass, entry)
    assert hass.states.get(entity_id).state != "unavailable"

    # A dropped Modbus link must surface as UpdateFailed so the entities go
    # unavailable instead of silently keeping their last value.
    with patch.object(
        entry.runtime_data.device,
        "update",
        new=AsyncMock(side_effect=ConnectionException("lost")),
    ):
        await entry.runtime_data.main_coordinator.async_refresh()
        await hass.async_block_till_done()

    assert entry.runtime_data.main_coordinator.last_update_success is False
    assert hass.states.get(entity_id).state == "unavailable"


async def test_entities_unavailable_when_device_rejects_read(hass, setup_storage):
    """A Modbus exception response must not pass for a successful poll.

    pymodbus does not raise for an exception response - it returns one whose
    ``registers`` list is empty. Before the transport checked ``isError()``,
    such a batch decoded to nothing: the coordinator saw a successful update
    with the keys simply missing, and every affected sensor kept its last
    value indefinitely while still reporting as available.
    """
    entry, _fake = setup_storage
    entity_id = _any_sensor_entity_id(hass, entry)
    assert hass.states.get(entity_id).state != "unavailable"

    with patch.object(
        entry.runtime_data.device,
        "update",
        new=AsyncMock(side_effect=ModbusException("illegal data address")),
    ):
        await entry.runtime_data.main_coordinator.async_refresh()
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.main_coordinator
    assert coordinator.last_update_success is False
    assert hass.states.get(entity_id).state == "unavailable"
    # Handled explicitly, not swallowed by the coordinator's catch-all: an
    # unhandled ModbusException still marks the update failed, but logs a
    # traceback as an "Unexpected error" on every single poll.
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "rejected a Modbus request" in str(coordinator.last_exception)


async def test_setup_retries_when_device_unreachable(setup_unreachable):
    # ConfigEntryNotReady -> HA schedules a retry rather than failing outright.
    assert setup_unreachable.state is ConfigEntryState.SETUP_RETRY


async def test_migrates_slot_unique_ids_to_serial(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_NUMBER: "INV1"},
        unique_id="INV1",
        title="Growatt Test",
    )
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    # A pre-0.12 slot-based per-module entity...
    old = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_INV1_battery_module_1_soc", config_entry=entry
    )
    # ...and an unrelated entity that must be left untouched.
    other = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_INV1_battery_voltage", config_entry=entry
    )

    await _async_migrate_module_unique_ids(hass, entry, {1: "MODONE", 2: "MODTWO"})

    assert (
        registry.async_get(old.entity_id).unique_id
        == f"{DOMAIN}_INV1_module_MODONE_soc"
    )
    assert (
        registry.async_get(other.entity_id).unique_id
        == f"{DOMAIN}_INV1_battery_voltage"
    )


async def test_setup_retries_when_connect_returns_false(
    setup_with_transport, fake_modbus_class
):
    # pymodbus signals a refused/unreachable connection by returning False
    # from connect(), not by raising.
    class _NotConnected(fake_modbus_class):
        closed = False

        def connected(self):
            return False

        def close(self):
            self.closed = True

    transport = _NotConnected()
    entry = await setup_with_transport(return_value=transport)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert transport.closed


async def test_setup_retries_when_serial_port_missing(setup_with_transport):
    # A USB adapter that has not enumerated yet must not fail setup for good.
    entry = await setup_with_transport(
        side_effect=ModbusPortException("USB port /dev/ttyUSB0 is not available")
    )

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_closed_when_setup_fails_after_connect(
    setup_with_transport, fake_modbus_class
):
    class _Tracking(fake_modbus_class):
        closed = False

        def close(self):
            self.closed = True

    transport = _Tracking()
    with patch(
        "custom_components.growatt_modbus.async_setup_optimizer",
        side_effect=RuntimeError("boom"),
    ):
        entry = await setup_with_transport(return_value=transport)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert transport.closed


async def test_failed_entity_write_raises_a_user_facing_error(hass, setup_storage):
    """A rejected write surfaces as HomeAssistantError, not a raw traceback."""
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    entry, fake = setup_storage
    switch_id = next(
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.domain == "switch" and e.unique_id.endswith("_ac_charge_enabled")
    )

    async def _reject(register, payload, unit):
        raise ModbusException("illegal data value")

    fake.write_register = _reject
    with pytest.raises(HomeAssistantError, match="illegal data value"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch_id}, blocking=True
        )


async def test_reconnect_is_attempted_promptly_and_rate_limited(hass, setup_storage):
    """The link is retried on the first failure, then at most once a minute.

    It used to retry only on every 60th failed poll: at the default 60 s scan
    interval, one reconnect attempt an hour.
    """
    entry, fake = setup_storage
    coordinator = entry.runtime_data.main_coordinator
    connect = AsyncMock()
    fake.connect = connect

    with (
        patch.object(
            entry.runtime_data.device,
            "update",
            new=AsyncMock(side_effect=ConnectionException("lost")),
        ),
        patch(
            "custom_components.growatt_modbus.coordinator.time.monotonic"
        ) as monotonic,
    ):
        for now in (1000.0, 1010.0, 1030.0, 1061.0):
            monotonic.return_value = now
            await coordinator.async_refresh()

    # 1000 (first failure), then 1061 (>= 60 s later); 1010/1030 rate-limited.
    assert connect.await_count == 2
