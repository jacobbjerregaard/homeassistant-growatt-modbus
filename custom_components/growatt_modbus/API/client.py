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

from pymodbus.client import ModbusBaseClient
from pymodbus.client.serial import AsyncModbusSerialClient
from pymodbus.client.tcp import AsyncModbusTcpClient
from pymodbus.client.udp import AsyncModbusUdpClient
from pymodbus import FramerType

from .device_type.base import (
    GrowattDeviceRegisters,
    GrowattDeviceInfo,
    ATTR_DEVICE_TYPE_CODE,
    ATTR_FIRMWARE,
    ATTR_INVERTER_MODEL,
    ATTR_MODBUS_VERSION,
    ATTR_NUMBER_OF_TRACKERS_AND_PHASES,
    ATTR_SERIAL_NUMBER,
)
from .exception import ModbusException, ModbusPortException
from .utils import (
    get_keys_from_register,
    keys_sequences,
    process_registers,
)

_LOGGER = logging.getLogger(__name__)


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
            register: dict[int, GrowattDeviceRegisters] | tuple[GrowattDeviceRegisters, ...],
            max_length: int,
            unit: int
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
                await self.read_holding_registers(start_index=item[0], length=item[1], unit=unit)
            )

        results = process_registers(register, register_values)

        device_info = GrowattDeviceInfo(
            serial_number=results[ATTR_SERIAL_NUMBER].replace("\x00", ""),
            model=results[ATTR_INVERTER_MODEL],
             firmware=results[ATTR_FIRMWARE].replace("\x00", ""),
            mppt_trackers=results[ATTR_NUMBER_OF_TRACKERS_AND_PHASES][0],
            grid_phases=results[ATTR_NUMBER_OF_TRACKERS_AND_PHASES][1],
            modbus_version=results[ATTR_MODBUS_VERSION],
            device_type=results[ATTR_DEVICE_TYPE_CODE]
        )

        return device_info

    async def read_device_time(self, unit: int):
        """
        Read Growatt device time.
        """
        # TODO: update with dynamic register values
        async with self._lock:
            rhr = await self.client.read_holding_registers(address=45, count=6, slave=unit)
        if rhr.isError():
            _LOGGER.debug("Modbus read failed for rhr")
            raise ModbusException("Modbus read failed for rhr.")

        return datetime(
            rhr.register[0] + 2000,
            rhr.register[1],
            rhr.register[2],
            rhr.register[3],
            rhr.register[4],
            rhr.register[5],
        )

    async def write_device_time(
        self, year: int, month: int, day: int, hour: int, minute: int, second: int
    ):
        """Writing current date/time to device."""
        # TODO: test if it works with current asyc libary
        # TODO: update with dynamic register values
        async with self._lock:
            await self.client.write_register(45, year - 2000)
            await self.client.write_register(46, month)
            await self.client.write_register(47, day)
            await self.client.write_register(48, hour)
            await self.client.write_register(49, minute)
            await self.client.write_register(50, second)

    async def write_register(self, register, payload, unit) :
        registers = self.client.convert_to_registers(
            payload,
            data_type="int16",
            wordorder="big",
            byteorder="big"
        )
        async with self._lock:
            return await self.client.write_register(register, registers, unit)

    async def read_holding_registers(self, start_index, length, unit) -> dict[int, int]:
        async with self._lock:
            data = await self.client.read_holding_registers(address=start_index, count=length, device_id=unit)
        registers = {c: v for c, v in enumerate(data.registers, start_index)}
        return registers

    async def read_input_registers(self, start_index, length, unit) -> dict[int, int]:
        async with self._lock:
            data = await self.client.read_input_registers(address=start_index, count=length, device_id=unit)
        registers = {c: v for c, v in enumerate(data.registers, start_index)}
        return registers


class GrowattNetwork(GrowattModbusBase):
    def __init__(
        self,
        network_type: str,
        host: str,
        port: int = 502,
        frame: str = '',
        timeout: int = 5,
        retries: int = 5,
    ) -> None:
        """Initialize Network Growatt."""
        super().__init__()

        if network_type.lower() == "tcp":
            if frame.lower() == 'rtu':
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
            if frame.lower() == 'rtu':
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
                    "Port %s is not available on windows platfrom should always start with 'COM'",
                    port,
                )
                raise ModbusPortException(
                    f"Port {port} is not available on windows platfrom should always start with 'COM'"
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
