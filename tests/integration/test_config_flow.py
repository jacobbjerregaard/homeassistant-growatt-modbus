"""Config-flow and options-flow tests."""
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from pymodbus.exceptions import ConnectionException

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.data_entry_flow import FlowResultType

from custom_components.growatt_modbus.API.device_type.base import GrowattDeviceInfo
from custom_components.growatt_modbus.API.exception import ModbusPortException
from custom_components.growatt_modbus.const import (
    CONF_AC_PHASES,
    CONF_BATTERY_MODULES,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DC_STRING,
    CONF_FRAME,
    CONF_LAYER,
    CONF_PARITY,
    CONF_POWER_SCAN_ENABLED,
    CONF_POWER_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    CONF_TCP,
    CONF_TOU_SLOTS,
    DOMAIN,
)

_SERIAL_INPUT = {
    CONF_SERIAL_PORT: "/dev/ttyUSB1",
    CONF_BAUDRATE: 9600,
    CONF_STOPBITS: 1,
    CONF_PARITY: "None",
    CONF_BYTESIZE: 8,
    CONF_ADDRESS: 1,
}
_NETWORK_INPUT = {
    CONF_IP_ADDRESS: "10.0.0.5",
    CONF_PORT: 502,
    CONF_ADDRESS: 1,
    CONF_FRAME: "socket",
}

_DEVICE_INFO = GrowattDeviceInfo(
    serial_number="SNFLOW0001",
    model="SPH",
    firmware="FW1.0",
    mppt_trackers=2,
    grid_phases=1,
    modbus_version=1.24,
    device_type="hybrid_120",
)


class _FakeServer:
    async def connect(self):
        return None

    def connected(self):
        return True

    def close(self):
        return None


async def test_serial_config_flow_happy_path(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_SERIAL}
    )
    assert result["step_id"] == "serial"

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=_DEVICE_INFO),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                CONF_STOPBITS: 1,
                CONF_PARITY: "None",
                CONF_BYTESIZE: 8,
                CONF_ADDRESS: 1,
            },
        )
        assert result["step_id"] == "device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My Growatt",
                CONF_MODEL: "SPH",
                CONF_TYPE: "hybrid_120",
                CONF_DC_STRING: 2,
                CONF_AC_PHASES: 1,
                CONF_SCAN_INTERVAL: 60,
                CONF_POWER_SCAN_ENABLED: False,
                CONF_POWER_SCAN_INTERVAL: 5,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SERIAL_NUMBER] == "SNFLOW0001"
    assert result["data"][CONF_TYPE] == "hybrid_120"
    assert result["result"].unique_id == "SNFLOW0001"


async def test_serial_flow_shows_error_on_timeout(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_SERIAL}
    )

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                CONF_STOPBITS: 1,
                CONF_PARITY: "None",
                CONF_BYTESIZE: 8,
                CONF_ADDRESS: 9,
            },
        )

    # The form is shown again with an error rather than aborting the flow.
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"]["base"] == "device_timeout"


async def test_serial_flow_port_error(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_SERIAL}
    )

    class _BadPort(_FakeServer):
        async def connect(self):
            raise ModbusPortException("no port")

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_BadPort(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _SERIAL_INPUT
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"][CONF_SERIAL_PORT] == "serial_port"


async def test_network_config_flow_happy_path(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_TCP}
    )
    assert result["step_id"] == "network"

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=_DEVICE_INFO),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NETWORK_INPUT
        )
        assert result["step_id"] == "device"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Net Growatt",
                CONF_MODEL: "SPH",
                CONF_TYPE: "hybrid_120",
                CONF_DC_STRING: 2,
                CONF_AC_PHASES: 1,
                CONF_SCAN_INTERVAL: 60,
                CONF_POWER_SCAN_ENABLED: False,
                CONF_POWER_SCAN_INTERVAL: 5,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "SNFLOW0001"


async def test_network_flow_connection_error(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_TCP}
    )

    class _Unreachable(_FakeServer):
        def connected(self):
            return False

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_Unreachable(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _NETWORK_INPUT
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "network"
    assert result["errors"]["base"] == "network_connection"


async def test_reconfigure_serial_updates_connection(hass, setup_storage):
    entry, _fake = setup_storage
    matched = replace(_DEVICE_INFO, serial_number=entry.unique_id)

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_serial"

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=matched),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**_SERIAL_INPUT, CONF_SERIAL_PORT: "/dev/ttyUSB9"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB9"


async def test_reconfigure_aborts_on_wrong_device(hass, setup_storage):
    entry, _fake = setup_storage
    other = replace(_DEVICE_INFO, serial_number="SOMEOTHERUNIT")

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=other),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _SERIAL_INPUT
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_reconfigure_serial_shows_error_on_timeout(hass, setup_storage):
    entry, _fake = setup_storage
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _SERIAL_INPUT
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure_serial"
    assert result["errors"]["base"] == "device_timeout"


async def test_reconfigure_network_updates_connection(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="NETSERIAL1",
        title="Net Growatt",
        data={
            CONF_LAYER: CONF_TCP,
            CONF_IP_ADDRESS: "10.0.0.1",
            CONF_PORT: 502,
            CONF_ADDRESS: 1,
            CONF_FRAME: "socket",
            CONF_SERIAL_NUMBER: "NETSERIAL1",
        },
    )
    entry.add_to_hass(hass)
    matched = replace(_DEVICE_INFO, serial_number="NETSERIAL1")

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_network"

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=matched),
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**_NETWORK_INPUT, CONF_IP_ADDRESS: "10.0.0.99"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_IP_ADDRESS] == "10.0.0.99"


async def _to_serial_step(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_SERIAL}
    )


async def test_serial_flow_connection_error(hass):
    result = await _to_serial_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=ConnectionException("boom")),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _SERIAL_INPUT)
    assert result["step_id"] == "serial"
    assert result["errors"]["base"] == "device_disconnect"


async def test_serial_flow_no_device_info_shows_device_form(hass):
    result = await _to_serial_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _SERIAL_INPUT)
    assert result["step_id"] == "device"


async def test_network_flow_timeout(hass):
    import asyncio

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LAYER: CONF_TCP})

    class _SlowServer(_FakeServer):
        async def connect(self):
            raise asyncio.TimeoutError

    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_SlowServer(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _NETWORK_INPUT)
    assert result["step_id"] == "network"
    assert result["errors"]["base"] == "network_connection"


async def _to_network_step(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LAYER: CONF_TCP}
    )


async def test_network_flow_device_timeout(hass):
    result = await _to_network_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _NETWORK_INPUT)
    assert result["step_id"] == "network"
    assert result["errors"]["base"] == "device_timeout"


async def test_network_flow_device_disconnect(hass):
    result = await _to_network_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=ConnectionException("x")),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _NETWORK_INPUT)
    assert result["step_id"] == "network"
    assert result["errors"]["base"] == "device_disconnect"


async def test_network_flow_no_device_info_shows_device_form(hass):
    result = await _to_network_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _NETWORK_INPUT)
    assert result["step_id"] == "device"


async def _to_device_step(hass):
    """Drive the serial flow up to the device form."""
    result = await _to_serial_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattSerial",
        return_value=_FakeServer(),
    ), patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=_DEVICE_INFO),
    ):
        return await hass.config_entries.flow.async_configure(result["flow_id"], _SERIAL_INPUT)


_DEVICE_INPUT = {
    CONF_NAME: "G",
    CONF_MODEL: "SPH",
    CONF_TYPE: "hybrid_120",
    CONF_DC_STRING: 2,
    CONF_AC_PHASES: 1,
    CONF_SCAN_INTERVAL: 60,
    CONF_POWER_SCAN_ENABLED: False,
    CONF_POWER_SCAN_INTERVAL: 5,
}


async def test_device_step_timeout_reshows_form(hass):
    result = await _to_device_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _DEVICE_INPUT)
    assert result["step_id"] == "device"
    assert result["errors"]["base"] == "device_timeout"


async def test_device_step_connection_error_reshows_form(hass):
    result = await _to_device_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(side_effect=ConnectionException("x")),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _DEVICE_INPUT)
    assert result["step_id"] == "device"
    assert result["errors"]["base"] == "device_disconnect"


async def test_device_step_unknown_type_errors(hass):
    result = await _to_device_step(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.get_device_info",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _DEVICE_INPUT)
    assert result["step_id"] == "device"
    assert result["errors"]["base"] == "device_type"


async def test_reconfigure_network_shows_error(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="NETSERIAL2",
        data={
            CONF_LAYER: CONF_TCP,
            CONF_IP_ADDRESS: "10.0.0.1",
            CONF_PORT: 502,
            CONF_ADDRESS: 1,
            CONF_FRAME: "socket",
            CONF_SERIAL_NUMBER: "NETSERIAL2",
        },
    )
    entry.add_to_hass(hass)

    class _Unreachable(_FakeServer):
        def connected(self):
            return False

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.growatt_modbus.config_flow.GrowattNetwork",
        return_value=_Unreachable(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _NETWORK_INPUT)
    assert result["step_id"] == "reconfigure_network"
    assert result["errors"]["base"] == "network_connection"


async def test_options_flow_updates_settings(hass, setup_storage):
    entry, _fake = setup_storage

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "general"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "general"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 30,
            CONF_POWER_SCAN_ENABLED: False,
            CONF_POWER_SCAN_INTERVAL: 5,
            CONF_BATTERY_MODULES: 0,
            CONF_TOU_SLOTS: 0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 30
