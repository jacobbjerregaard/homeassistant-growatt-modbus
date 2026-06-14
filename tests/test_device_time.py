"""Tests for the device clock read/write in API/client.py.

These pin the pymodbus param fixes: read_device_time must use device_id (not the
removed `slave`) and registers (not register), and write_device_time must pass
device_id for every write.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("pymodbus", reason="client.py imports pymodbus")

from growatt_api.client import GrowattModbusBase  # noqa: E402


async def test_read_device_time_uses_device_id_and_registers():
    base = GrowattModbusBase()
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = [24, 6, 14, 12, 30, 0]
    base.client = MagicMock()
    base.client.read_holding_registers = AsyncMock(return_value=resp)

    result = await base.read_device_time(5)

    assert result == datetime(2024, 6, 14, 12, 30, 0)
    kwargs = base.client.read_holding_registers.await_args.kwargs
    assert kwargs.get("device_id") == 5
    assert "slave" not in kwargs


async def test_write_device_time_passes_device_id_for_each_register():
    base = GrowattModbusBase()
    base.client = MagicMock()
    base.client.write_register = AsyncMock()

    await base.write_device_time(2024, 6, 14, 12, 30, 0, 7)

    assert base.client.write_register.await_count == 6
    first = base.client.write_register.await_args_list[0]
    assert first.args[0] == 45  # SysYear register
    assert first.args[1] == 24  # 2024 - 2000
    assert first.kwargs.get("device_id") == 7
