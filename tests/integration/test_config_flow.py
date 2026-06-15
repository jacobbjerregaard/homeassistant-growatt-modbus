"""Config-flow and options-flow tests."""
from unittest.mock import AsyncMock, patch

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.data_entry_flow import FlowResultType

from custom_components.growatt_modbus.API.device_type.base import GrowattDeviceInfo
from custom_components.growatt_modbus.const import (
    CONF_AC_PHASES,
    CONF_BATTERY_MODULES,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DC_STRING,
    CONF_LAYER,
    CONF_PARITY,
    CONF_POWER_SCAN_ENABLED,
    CONF_POWER_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_STOPBITS,
    CONF_TOU_SLOTS,
    DOMAIN,
)

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


async def test_options_flow_updates_settings(hass, setup_storage):
    entry, _fake = setup_storage

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

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
