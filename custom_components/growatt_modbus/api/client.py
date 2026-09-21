"""
Modbus transport layer for Growatt inverters.

Provides the connection/transaction primitives (serial RS232/RTU and
TCP/UDP) shared by the higher-level device abstraction.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from pymodbus import FramerType
from pymodbus.client import ModbusBaseClient
from pymodbus.client.serial import AsyncModbusSerialClient
from pymodbus.client.tcp import AsyncModbusTcpClient
from pymodbus.client.udp import AsyncModbusUdpClient

from .device_type.base import (
    ATTR_DEVICE_TYPE_CODE,
    ATTR_FIRMWARE,
    ATTR_INVERTER_MODEL,
    ATTR_MODBUS_VERSION,
    ATTR_NUMBER_OF_TRACKERS_AND_PHASES,
    ATTR_SERIAL_NUMBER,
    GrowattDeviceInfo,
    GrowattDeviceRegisters,
)
from .exception import ModbusException, ModbusPortException
from .utils import (
    get_keys_from_register,
    keys_sequences,
    process_registers,
)

_LOGGER = logging.getLogger(__name__)


def _raise_on_error(result, register: int) -> None:
    """Raise when pymodbus reports a write was rejected by the device.

    pymodbus returns an exception *response* rather than raising, so an
    unchecked write looks like it succeeded.
    """
    if result is not None and result.isError():
        raise ModbusException(f"Modbus error writing register {register}: {result}")


def _year_from_register(value: int) -> int:
    """Decode SysYear (holding 45), which devices store in one of two ways.

    Most store the year minus 2000 (26); some - a 3-phase hybrid with firmware
    DN1.0 was verified - store the full year (2026).
    """
    return value if value >= 2000 else value + 2000


class GrowattModbusBase:
    client: ModbusBaseClient

    def __init__(self):
        # Modbus is a single request/response link and is not safe for
        # overlapping transactions. Serialise every read/write through this
        # lock so coordinator polling and entity writes cannot interleave and
        # corrupt each other's frames.
        self._lock = asyncio.Lock()

    async def connect(self):
        """Connecting the modbus device."""
        await self.client.connect()

    def connected(self):
        return self.client.connected

    def close(self):
        """Closing the modbus device connection."""
        self.client.close()

    async def get_device_info(
        self,
        register: dict[int, GrowattDeviceRegisters]
        | tuple[GrowattDeviceRegisters, ...],
        max_length: int,
        unit: int,
    ) -> GrowattDeviceInfo:
        """
        Read Growatt device information.
        """

        if isinstance(register, tuple):
            register = {item.register: item for item in register}

        key_sequences = keys_sequences(get_keys_from_register(register), max_length)

        register_values = {}

        for item in key_sequences:
            register_values.update(
                await self.read_holding_registers(
                    start_index=item[0], length=item[1], unit=unit
                )
            )

        results = process_registers(register, register_values)

        device_info = GrowattDeviceInfo(
            serial_number=results[ATTR_SERIAL_NUMBER].replace("\x00", "").strip(),
            model=results[ATTR_INVERTER_MODEL],
            firmware=results[ATTR_FIRMWARE].replace("\x00", ""),
            mppt_trackers=results[ATTR_NUMBER_OF_TRACKERS_AND_PHASES][0],
            grid_phases=results[ATTR_NUMBER_OF_TRACKERS_AND_PHASES][1],
            modbus_version=results[ATTR_MODBUS_VERSION],
            device_type=results[ATTR_DEVICE_TYPE_CODE],
        )

        return device_info

    async def read_device_time(self, unit: int):
        """Read the device clock from holding registers 45-50 (SysYear..SysSec)."""
        async with self._lock:
            rhr = await self.client.read_holding_registers(
                address=45, count=6, device_id=unit
            )
        if rhr.isError():
            _LOGGER.debug("Modbus read failed for rhr")
            raise ModbusException("Modbus read failed for rhr.")

        try:
            return datetime(
                _year_from_register(rhr.registers[0]),
                rhr.registers[1],
                rhr.registers[2],
                rhr.registers[3],
                rhr.registers[4],
                rhr.registers[5],
            )
        except (ValueError, IndexError) as err:
            # An unset clock reads as zeros (month 0), which is not a date.
            raise ModbusException(
                f"Device clock holds an invalid date: {list(rhr.registers)}"
            ) from err

    async def write_device_time(
        self,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        unit: int,
    ):
        """Write current date/time to the device (holding registers 45-50).

        SysYear is written in the format the device already uses, read back
        first: a full year (2026) or the year minus 2000 (26). The V1.39 spec's
        "Year offset is 0" is ambiguous; a 3-phase hybrid (firmware DN1.0) was
        verified to store the full year.

        Not every device accepts a clock write: that hybrid rejected register
        45 with both a single-register write (exception 1, illegal function)
        and a multi-register write, so there the caller gets a
        ModbusException.
        """
        async with self._lock:
            current = await self.client.read_holding_registers(
                address=45, count=1, device_id=unit
            )
            if current.isError():
                raise ModbusException(f"Modbus error reading register 45: {current}")
            year_value = year if current.registers[0] >= 2000 else year - 2000
            for offset, value in enumerate(
                (year_value, month, day, hour, minute, second)
            ):
                result = await self.client.write_register(
                    45 + offset, value, device_id=unit
                )
                _raise_on_error(result, 45 + offset)

    async def write_register(self, register, payload, unit):
        """Write a single holding register. Signed values are sent as two's
        complement (e.g. -10 -> 0xFFF6)."""
        async with self._lock:
            result = await self.client.write_register(
                register, int(payload) & 0xFFFF, device_id=unit
            )
        _raise_on_error(result, register)
        return result

    async def write_register_value(self, register, value, unit):
        """Write a raw unsigned 16-bit value (0-65535) to a holding register.

        Carries bit-packed values such as the time-slot registers (enable bit
        15) which exceed the signed-int16 range. The encoding is the same as
        :meth:`write_register`; the separate name documents the intent.
        """
        return await self.write_register(register, value, unit)

    async def read_holding_registers(self, start_index, length, unit) -> dict[int, int]:
        async with self._lock:
            data = await self.client.read_holding_registers(
                address=start_index, count=length, device_id=unit
            )
        return self._registers_from(data, start_index, length, "holding")

    async def read_input_registers(self, start_index, length, unit) -> dict[int, int]:
        async with self._lock:
            data = await self.client.read_input_registers(
                address=start_index, count=length, device_id=unit
            )
        return self._registers_from(data, start_index, length, "input")

    @staticmethod
    def _registers_from(
        data, start_index: int, length: int, kind: str
    ) -> dict[int, int]:
        """Map a pymodbus read response onto {address: value}.

        A Modbus exception response (illegal address, device busy, ...) is not
        raised by pymodbus and carries an *empty* ``registers`` list, so
        without this check the batch would silently decode to nothing: the
        poll would look successful while every sensor in it kept its previous
        value forever. Raise instead, so the coordinator can mark the entities
        unavailable.
        """
        if data.isError():
            raise ModbusException(
                f"Modbus error reading {length} {kind} register(s) "
                f"at {start_index}: {data}"
            )
        registers = {c: v for c, v in enumerate(data.registers, start_index)}
        if len(registers) != length:
            raise ModbusException(
                f"Short Modbus read of {kind} registers at {start_index}: "
                f"asked for {length}, got {len(registers)}"
            )
        return registers


class GrowattNetwork(GrowattModbusBase):
    def __init__(
        self,
        network_type: str,
        host: str,
        port: int = 502,
        frame: str = "",
        timeout: int = 5,
        retries: int = 5,
    ) -> None:
        """Initialize Network Growatt."""
        super().__init__()

        if network_type.lower() == "tcp":
            if frame.lower() == "rtu":
                self.client = AsyncModbusTcpClient(
                    host,
                    port=port,
                    framer=FramerType.RTU,
                    timeout=timeout,
                    retries=retries,
                )
            else:
                self.client = AsyncModbusTcpClient(
                    host,
                    port=port,
                    framer=FramerType.SOCKET,
                    timeout=timeout,
                    retries=retries,
                )

        elif network_type.lower() == "udp":
            if frame.lower() == "rtu":
                self.client = AsyncModbusUdpClient(
                    host,
                    port=port,
                    framer=FramerType.RTU,
                    timeout=timeout,
                    retries=retries,
                )
            else:
                self.client = AsyncModbusUdpClient(
                    host,
                    port=port,
                    framer=FramerType.SOCKET,
                    timeout=timeout,
                    retries=retries,
                )
        else:
            raise ModbusPortException("Unsuported network type defined")


class GrowattSerial(GrowattModbusBase):
    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        stopbits: int = 1,
        parity: str = "N",
        bytesize: int = 8,
        timeout: int = 3,
    ) -> None:
        """Initialize Serial Growatt."""
        super().__init__()

        if sys.platform.startswith("win"):
            if not port.startswith("COM"):
                _LOGGER.debug(
                    "Port %s is not available on windows platform, it should "
                    "always start with 'COM'",
                    port,
                )
                raise ModbusPortException(
                    f"Port {port} is not available on windows platform, it "
                    "should always start with 'COM'"
                )
        else:
            if not os.path.exists(port):
                _LOGGER.debug("Port %s is not available", port)
                raise ModbusPortException(f"USB port {port} is not available")

        self.client = AsyncModbusSerialClient(
            port=port,
            framer=FramerType.RTU,
            baudrate=baudrate,
            stopbits=stopbits,
            parity=parity[:1],
            bytesize=bytesize,
            timeout=timeout,
        )
