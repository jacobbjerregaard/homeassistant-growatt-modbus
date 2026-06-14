"""
High-level Growatt device abstraction.

Wraps a :class:`GrowattModbusBase` transport and maps the protocol register
layout for a given device type to named values.
"""

import logging

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Optional

from .client import GrowattModbusBase
from .const import DeviceTypes
from .device_type.base import (
    GrowattDeviceRegisters,
    GrowattDeviceInfo,
    ATTR_STATUS,
    ATTR_DERATING_MODE,
    ATTR_FAULT_CODE,
    ATTR_STATUS_CODE,
    inverter_status,
)
from .device_type.inverter_120 import (
    MAXIMUM_DATA_LENGTH_120,
    HOLDING_REGISTERS_120,
    INPUT_REGISTERS_120,
)
from .device_type.storage_120 import (
    STORAGE_HOLDING_REGISTERS_120,
    STORAGE_INPUT_REGISTERS_120,
    build_battery_module_registers,
)

_STORAGE_TYPES = (DeviceTypes.HYBRID_120, DeviceTypes.STORAGE_120)
from .device_type.inverter_315 import (
    MAXIMUM_DATA_LENGTH_315,
    HOLDING_REGISTERS_315,
    INPUT_REGISTERS_315,
)
from .utils import (
    RegisterKeys,
    DeviceRegisters,
    get_keys_from_register,
    register_sequences,
    keys_sequences,
    process_registers,
    LRUCache,
)

_LOGGER = logging.getLogger(__name__)


# Maps a device type to its register layout: (holding registers, one or more
# input-register sets applied in order, maximum contiguous read length).
_REGISTER_SETS: dict[
    DeviceTypes,
    tuple[
        tuple[GrowattDeviceRegisters, ...],
        tuple[tuple[GrowattDeviceRegisters, ...], ...],
        int,
    ],
] = {
    DeviceTypes.INVERTER: (HOLDING_REGISTERS_315, (INPUT_REGISTERS_315,), MAXIMUM_DATA_LENGTH_315),
    DeviceTypes.INVERTER_315: (HOLDING_REGISTERS_315, (INPUT_REGISTERS_315,), MAXIMUM_DATA_LENGTH_315),
    DeviceTypes.INVERTER_120: (HOLDING_REGISTERS_120, (INPUT_REGISTERS_120,), MAXIMUM_DATA_LENGTH_120),
    DeviceTypes.HYBRID_120: (
        STORAGE_HOLDING_REGISTERS_120,
        (INPUT_REGISTERS_120, STORAGE_INPUT_REGISTERS_120),
        MAXIMUM_DATA_LENGTH_120,
    ),
    DeviceTypes.STORAGE_120: (
        STORAGE_HOLDING_REGISTERS_120,
        (STORAGE_INPUT_REGISTERS_120,),
        MAXIMUM_DATA_LENGTH_120,
    ),
}


def get_register_information(
    device_type: DeviceTypes, battery_modules: int = 0
) -> DeviceRegisters:
    """Build the holding/input register maps for the given device type.

    When ``battery_modules`` > 0 (storage/hybrid only) per-module telemetry
    registers are appended for that many parallel battery modules.
    """
    try:
        holding_registers, input_register_sets, max_length = _REGISTER_SETS[device_type]
    except KeyError:
        raise TypeError("Unsupported Growatt device type")

    holding_register = {obj.register: obj for obj in holding_registers}

    input_register: dict[int, GrowattDeviceRegisters] = {}
    for register_set in input_register_sets:
        input_register.update({obj.register: obj for obj in register_set})

    if battery_modules and device_type in _STORAGE_TYPES:
        for obj in build_battery_module_registers(battery_modules):
            input_register[obj.register] = obj

    return DeviceRegisters(holding_register, input_register, max_length)


class GrowattDevice:
    holding_register: dict[int, GrowattDeviceRegisters] = {}
    input_register: dict[int, GrowattDeviceRegisters] = {}
    max_length: int = 20

    def __init__(
        self,
        GrowattModbusClient: GrowattModbusBase,
        GrowattDeviceType: DeviceTypes,
        unit: int,
        battery_modules: int = 0,
    ) -> None:
        self.modbus = GrowattModbusClient
        self.device = GrowattDeviceType
        self.battery_modules = battery_modules
        self._input_cache = LRUCache(10)

        self.device_registers = get_register_information(GrowattDeviceType, battery_modules)
        self.max_length = self.device_registers.max_length
        self.holding_register = self.device_registers.holding
        self.input_register = self.device_registers.input

        # Reverse name -> register indexes for O(1) lookups (the write path
        # resolves a register by name on every switch toggle).
        self._holding_by_name = {
            register.name: register for register in self.holding_register.values()
        }
        self._input_by_name = {
            register.name: register for register in self.input_register.values()
        }

        self.unit = unit

    async def connect(self):
        await self.modbus.connect()

    def connected(self):
        return self.modbus.connected()

    def close(self):
        self.modbus.close()

    async def get_device_info(self) -> GrowattDeviceInfo:
        return await self.modbus.get_device_info(self.holding_register, self.max_length, self.unit)

    async def sync_time(self) -> timedelta:
        device_time = await self.modbus.read_device_time(self.unit)
        time = datetime.now()
        await self.modbus.write_device_time(
            time.year, time.month, time.day, time.hour, time.minute, time.second, self.unit
        )

        return time - device_time

    async def update(self, keys: RegisterKeys) -> dict[str, Any]:
        """
        Based on the given keys it will generate one or multiple requests to get the corrisponding results
        from both holding and input registers from the device.

        returns a dictionary of register name and value
        """
        if len(keys) == 0:
            return {}

        if (key_hash := hash(keys)) not in self._input_cache:
            key_sequences = register_sequences(keys, self.device_registers)
            self._input_cache[key_hash] = key_sequences
        else:
            key_sequences = self._input_cache[key_hash]

        results = {}
        if key_sequences.holding:
            register_values = {}
            for item in key_sequences.holding:
                register_values.update(
                    await self.modbus.read_holding_registers(start_index=item[0], length=item[1], unit=self.unit)
                )
            results.update(process_registers(self.device_registers.holding, register_values))
        if key_sequences.input:
            register_values = {}
            for item in key_sequences.input:
                register_values.update(
                    await self.modbus.read_input_registers(start_index=item[0], length=item[1], unit=self.unit)
                )
            results.update(process_registers(self.device_registers.input, register_values))
        return results

    async def write_register(self, register, payload):
        _LOGGER.debug("Write register %d with payload %d and unit %d", register, payload, self.unit)
        return await self.modbus.write_register(register, payload, self.unit)


    async def read_holding_register(self, registers: tuple[GrowattDeviceRegisters, ...]) -> dict[str, Any]:
        register = {item.register: item for item in registers}
        key_sequences = keys_sequences(get_keys_from_register(register), self.max_length)

        register_values = {}

        for item in key_sequences:
            register_values.update(
               await self.modbus.read_holding_registers(start_index=item[0], length=item[1], unit=self.unit)
            )

        results = process_registers(register, register_values)
        _LOGGER.debug("Read holding register response %s", results)
        return results

    def get_keys_by_name(self, names: Sequence[str]) -> RegisterKeys:
        if ATTR_STATUS in names:
            names = (*names, ATTR_STATUS_CODE, ATTR_FAULT_CODE, ATTR_DERATING_MODE)

        return RegisterKeys(
            holding={
                key
                for key, register in self.device_registers.holding.items()
                if register.name in names
            },
            input={
                key
                for key, register in self.device_registers.input.items()
                if register.name in names
            }
        )

    def get_input_register_by_name(self, name: str) -> Optional[GrowattDeviceRegisters]:
        return self._input_by_name.get(name)

    def get_holding_register_by_name(self, name: str) -> Optional[GrowattDeviceRegisters]:
        return self._holding_by_name.get(name)

    def get_register_names(self) -> set[str]:
        names = {register.name for register in self.input_register.values()}
        names.update({register.name for register in self.holding_register.values()})

        names.add(ATTR_STATUS)

        return names

    def status(self, value: dict[str, Any]):
        """
        Based on the various register values the status of the device can be determined.
        """
        return inverter_status(value)
