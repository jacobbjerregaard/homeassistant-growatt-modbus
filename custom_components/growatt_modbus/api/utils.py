"""
Utility functions.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any

from .device_type.base import (
    GrowattDeviceRegisters,
    custom_function,
)

__all__ = (
    "get_keys_from_register",
    "get_all_keys_from_register",
    "keys_sequences",
    "split_sequence",
    "process_registers",
    "to_signed",
    "to_register_value",
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceRegisters:
    holding: dict[int, GrowattDeviceRegisters]
    input: dict[int, GrowattDeviceRegisters]
    max_length: int


@dataclass
class RegisterKeys:
    holding: set[int] = field(default_factory=set)
    input: set[int] = field(default_factory=set)

    def __len__(self):
        return len(self.holding) + len(self.input)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RegisterKeys):
            return NotImplemented
        return self.holding == other.holding and self.input == other.input

    def __hash__(self) -> int:
        return hash((frozenset(self.holding), frozenset(self.input)))

    def update(self, register_keys: RegisterKeys) -> None:
        self.holding.update(register_keys.holding)
        self.input.update(register_keys.input)


@dataclass
class RegisterSequences:
    holding: set[tuple[int, int]] = field(default_factory=set)
    input: set[tuple[int, int]] = field(default_factory=set)

    def __len__(self):
        return len(self.holding) + len(self.input)


def continuation_keys(registers: dict[int, GrowattDeviceRegisters]) -> set[int]:
    """Addresses that are the second or later word of a multi-word register."""
    return {
        key + offset
        for key, register in registers.items()
        for offset in range(1, register.length)
    }


def register_sequences(
    register_keys: RegisterKeys, device_registers: DeviceRegisters
) -> RegisterSequences:
    if register_keys.holding:
        holding_sequence = keys_sequences(
            get_all_keys_from_register(device_registers.holding, register_keys.holding),
            device_registers.max_length,
            continuation_keys(device_registers.holding),
        )
    else:
        holding_sequence = set()

    if register_keys.input:
        input_sequence = keys_sequences(
            get_all_keys_from_register(device_registers.input, register_keys.input),
            device_registers.max_length,
            continuation_keys(device_registers.input),
        )
    else:
        input_sequence = set()

    return RegisterSequences(holding_sequence, input_sequence)


def get_keys_from_register(register: dict[int, GrowattDeviceRegisters]) -> set[int]:
    results = set()
    for key, value in register.items():
        results.add(key)

        if value.length > 1:
            for i in range(value.length):
                results.add(key + i)

    return results


def get_all_keys_from_register(
    registers: dict[int, GrowattDeviceRegisters], keys: set[int]
) -> set[int]:
    """
    Lookup all related keys from the given keys based on the register config.
    returns list a sorted list of all keys.
    """
    result = set()

    for key in keys:
        result.add(key)
        if (register := registers.get(key)) is None:
            continue

        if register.length > 1:
            for i in range(register.length):
                result.add(key + i)

    return result


def keys_sequences(
    keys: Iterable[int],
    maximum_length: int,
    continuation: Collection[int] = (),
) -> set[tuple[int, int]]:
    """
    Creates the set of sequences based on the given keys.
    returns set containing tuples with start_key and length.
    """
    sorted_keys = sorted(keys)
    indexes = split_sequence(sorted_keys, maximum_length, continuation)

    sequence = set()

    start = 0
    indexes.append(len(sorted_keys))
    for end in indexes:
        sequence.add(
            (
                sorted_keys[start],
                max(sorted_keys[start:end]) - min(sorted_keys[start:end]) + 1,
            )
        )
        start = end

    _LOGGER.debug(
        "determined key seqences %s",
        [f"start: {s[0]}, end: {s[0] + s[1]}" for s in sequence],
    )
    return sequence


def split_sequence(
    keys: list[int], maximum_length: int, continuation: Collection[int] = ()
) -> list[int]:
    """
    Return the indexes into the sorted ``keys`` at which a new read starts.

    A new read starts at a key when either
    - the gap from the previous key reaches ``maximum_length / 4``: reading
      the unused words in between would cost more than another request, or
    - including the key would make the current read longer than
      ``maximum_length`` words, which the inverter rejects.

    ``continuation`` holds the second and later words of multi-word registers.
    A read never starts on one of those: the split moves back to the first
    word, so a 32-bit counter's two halves come from the same request. Read
    separately, a carry between the requests would decode off by 65536 raw.

    Greedy, so every read is guaranteed to be at most ``maximum_length``.
    """
    separation_threshold = maximum_length / 4

    indexes: list[int] = []
    read_start = 0
    for index in range(1, len(keys)):
        gap = keys[index] - keys[index - 1]
        span = keys[index] - keys[read_start] + 1
        if gap >= separation_threshold or span > maximum_length:
            split = index
            while split > read_start + 1 and keys[split] in continuation:
                split -= 1
            indexes.append(split)
            read_start = split

    _LOGGER.debug("split sequence keys %s at indexes %s", keys, indexes)
    return indexes


def to_signed(value: int, bits: int) -> int:
    """Reinterpret an unsigned ``bits``-wide register value as two's complement."""
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


def to_register_value(register: GrowattDeviceRegisters, value: float) -> int:
    """Encode a user-facing value into the raw register integer to write.

    Inverse of :func:`process_registers` for the int/float paths. Float
    registers are multiplied back by their scale; integer registers are written
    as-is. Signed negative values are returned unchanged - the Modbus client
    encodes them as two's complement when writing.
    """
    if register.value_type is float:
        return int(round(value * register.scale))
    return int(round(value))


def process_registers(
    registers: dict[int, GrowattDeviceRegisters], register_values: dict[int, int]
) -> dict[str, Any]:
    """
    Processes the register value corisponding to the given register dict.
    returns a dict of name and value
    """
    result: dict[str, Any] = {}

    for key, value in register_values.items():
        if (register := registers.get(key)) is None:
            continue

        if register.value_type is int:
            result[register.name] = to_signed(value, 16) if register.signed else value

        elif register.value_type is float and register.length == 2:
            if (second_value := register_values.get(key + 1, None)) is None:
                continue

            raw = (value << 16) + second_value
            if register.signed:
                raw = to_signed(raw, 32)

            result[register.name] = round(float(raw) / register.scale, 3)

        elif register.value_type is float:
            raw = to_signed(value, 16) if register.signed else value
            result[register.name] = round(float(raw) / register.scale, 3)

        elif register.value_type is str:
            string = ""
            for i in range(key, key + register.length):
                if (item := register_values.get(i)) is not None:
                    string += chr(item >> 8)
                    string += chr(item & 0x00FF)

            result[register.name] = string

        elif register.value_type is bool:
            result[register.name] = bool(value)

        elif register.value_type is custom_function:
            if register.function is None:
                continue

            if register.length == 1:
                decoded = register.function(value)
            else:
                decoded = register.function(
                    [register_values.get(i) for i in range(key, key + register.length)]
                )

            # A custom_function may decode a single register into several named
            # values (e.g. a packed bitfield) by returning a dict; each entry is
            # suffixed onto the register name to form its own result key.
            if isinstance(decoded, dict):
                for sub_name, sub_value in decoded.items():
                    result[f"{register.name}_{sub_name}"] = sub_value
            else:
                result[register.name] = decoded

    return result
