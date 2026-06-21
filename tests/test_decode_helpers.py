"""Direct tests for the pure register-decode helper functions."""
from growatt_api.device_type import base
from growatt_api.device_type.base import (
    ATTR_DERATING_MODE,
    ATTR_FAULT_CODE,
    ATTR_STATUS_CODE,
    INVERTER_DERATINGMODES,
)
from growatt_api.device_type import storage_120 as storage


def test_base_device_type_and_trackers():
    # 10000 < reg <= 10004 uses the direct code; otherwise the high byte.
    assert isinstance(base.device_type(10001), str)
    assert isinstance(base.device_type(0x0100), str)
    assert isinstance(base.device_type(0xABCD), str)
    assert base.trackers_and_phases(0x0203) == (2, 3)


def test_base_inverter_status_variants():
    assert base.inverter_status({}) is None
    assert base.inverter_status({ATTR_STATUS_CODE: 0}) == "Waiting"
    assert base.inverter_status({ATTR_STATUS_CODE: 1}) == "Normal"

    derating = next(k for k in INVERTER_DERATINGMODES if k != 0)
    out = base.inverter_status({ATTR_STATUS_CODE: 1, ATTR_DERATING_MODE: derating})
    assert out.startswith("Normal - ")

    fault = base.inverter_status({ATTR_STATUS_CODE: 3, ATTR_FAULT_CODE: 1})
    assert fault.startswith("Fault - ")


def test_storage_firmware_code_version():
    # [0x4142, 0x4300, 5] -> "ABC" + version 5
    assert storage.firmware_code_version([0x4142, 0x4300, 5]) == "ABC-5"
    assert storage.firmware_code_version([0x4142, None]) == "AB"


def test_storage_model_is_formatted():
    out = storage.model([0x1234, 0x5678])
    assert out.startswith("A1 B2 D3 T4")


def test_storage_inverter_status_mode_flag():
    assert storage.inverter_status(0) == "Standby"
    assert storage.inverter_status(1) == "Normal"
    assert storage.inverter_status(3) == "Fault"
    assert storage.inverter_status(4) == "Flash"

    assert storage.inverter_mode(0) == "Load"
    assert storage.inverter_mode(1) == "Battery"
    assert storage.inverter_mode(2) == "Grid"
    assert storage.inverter_mode(9).startswith("Unknown")

    assert storage.bdc_data_flag(0) == "No need"
    assert storage.bdc_data_flag(1) == "Need"
    assert storage.bdc_data_flag(9).startswith("Unknown")
