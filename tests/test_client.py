"""Tests for the Modbus transport layer (API/client.py).

Only the pymodbus client object is faked; the GrowattModbusBase request/response
plumbing, value masking and constructor wiring are exercised for real.
"""
import asyncio
from datetime import datetime

import pytest

pytest.importorskip("pymodbus", reason="client.py imports pymodbus")

from growatt_api.client import GrowattModbusBase, GrowattNetwork, GrowattSerial
from growatt_api.exception import ModbusException, ModbusPortException
from growatt_api.device_type.inverter_120 import (
    HOLDING_REGISTERS_120,
    MAXIMUM_DATA_LENGTH_120,
)


class _Resp:
    def __init__(self, registers):
        self.registers = registers

    def isError(self):
        return False


class _ErrResp:
    registers: list = []

    def isError(self):
        return True


class _FakeClient:
    """Minimal stand-in for a pymodbus async client."""

    def __init__(self, holding=None, value=0):
        self.connected = False
        self.writes: list = []
        self._holding = holding or {}
        self._value = value

    async def connect(self):
        self.connected = True

    def close(self):
        self.connected = False

    async def read_holding_registers(self, address, count, device_id):
        if address in self._holding:
            return _Resp(list(self._holding[address]))
        return _Resp([self._value] * count)

    async def read_input_registers(self, address, count, device_id):
        return _Resp([self._value + i for i in range(count)])

    async def write_register(self, register, value, device_id):
        self.writes.append((register, value, device_id))
        return _Resp([])


def _base(client):
    base = GrowattModbusBase()
    base.client = client
    return base


def test_connect_close_and_register_reads():
    client = _FakeClient(value=7)
    base = _base(client)
    asyncio.run(base.connect())
    assert base.connected() is True

    holding = asyncio.run(base.read_holding_registers(10, 3, 1))
    assert holding == {10: 7, 11: 7, 12: 7}
    inputs = asyncio.run(base.read_input_registers(0, 2, 1))
    assert inputs == {0: 7, 1: 8}

    base.close()
    assert base.connected() is False


def test_write_register_masks_signed_and_raw():
    client = _FakeClient()
    base = _base(client)
    asyncio.run(base.write_register(951, -10, 1))
    assert client.writes[-1] == (951, 0xFFF6, 1)  # two's complement
    asyncio.run(base.write_register_value(3000, 70000, 1))
    assert client.writes[-1][1] == 70000 & 0xFFFF


def test_device_time_round_trip():
    client = _FakeClient(holding={45: [24, 6, 15, 10, 30, 0]})
    base = _base(client)
    assert asyncio.run(base.read_device_time(1)) == datetime(2024, 6, 15, 10, 30, 0)

    asyncio.run(base.write_device_time(2024, 6, 15, 10, 30, 0, 1))
    # SysYear stored as year - 2000.
    assert client.writes[0] == (45, 24, 1)
    assert client.writes[-1] == (50, 0, 1)


def test_read_device_time_raises_on_error():
    class _ErrClient(_FakeClient):
        async def read_holding_registers(self, address, count, device_id):
            return _ErrResp()

    base = _base(_ErrClient())
    with pytest.raises(ModbusException):
        asyncio.run(base.read_device_time(1))


def test_get_device_info_builds_struct():
    base = _base(_FakeClient(value=0))
    info = asyncio.run(
        base.get_device_info(HOLDING_REGISTERS_120, MAXIMUM_DATA_LENGTH_120, 1)
    )
    # All-zero registers still produce a well-formed struct (no crash / KeyError).
    assert info.serial_number == ""
    assert isinstance(info.modbus_version, (int, float))


@pytest.mark.parametrize(
    "net_type, frame",
    [("tcp", "rtu"), ("tcp", "socket"), ("udp", "rtu"), ("udp", "socket")],
)
def test_network_constructors(net_type, frame, monkeypatch):
    # Mock the pymodbus client classes so no real socket/serial stack is needed;
    # the GrowattNetwork framer/transport wiring still runs.
    monkeypatch.setattr("growatt_api.client.AsyncModbusTcpClient", lambda *a, **k: object())
    monkeypatch.setattr("growatt_api.client.AsyncModbusUdpClient", lambda *a, **k: object())
    dev = GrowattNetwork(net_type, "10.0.0.2", 502, frame)
    assert dev.client is not None


def test_network_invalid_type_raises():
    with pytest.raises(ModbusPortException):
        GrowattNetwork("bluetooth", "10.0.0.2")


def test_serial_missing_port_raises(monkeypatch):
    monkeypatch.setattr("growatt_api.client.sys.platform", "linux")
    monkeypatch.setattr("growatt_api.client.os.path.exists", lambda _p: False)
    with pytest.raises(ModbusPortException):
        GrowattSerial("/dev/does-not-exist")


def test_serial_constructs_when_port_exists(monkeypatch):
    monkeypatch.setattr("growatt_api.client.sys.platform", "linux")
    monkeypatch.setattr("growatt_api.client.os.path.exists", lambda _p: True)
    monkeypatch.setattr("growatt_api.client.AsyncModbusSerialClient", lambda *a, **k: object())
    dev = GrowattSerial("/dev/ttyUSB0", 9600, 1, "N", 8)
    assert dev.client is not None


def test_serial_windows_requires_com_port(monkeypatch):
    monkeypatch.setattr("growatt_api.client.sys.platform", "win32")
    with pytest.raises(ModbusPortException):
        GrowattSerial("/dev/ttyUSB0")
