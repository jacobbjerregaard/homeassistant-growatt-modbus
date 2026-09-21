"""Tests for the Modbus register-batching logic in ``API/utils.py``.

These functions decide how a set of requested register addresses is grouped
into a minimal number of contiguous Modbus reads.  They are the most intricate
piece of pure logic in the integration and previously had no coverage.
"""

from growatt_api.device_type.base import GrowattDeviceRegisters
from growatt_api.utils import (
    DeviceRegisters,
    RegisterKeys,
    get_all_keys_from_register,
    get_keys_from_register,
    keys_sequences,
    register_sequences,
    split_sequence,
)


def _u16(name: str, register: int, length: int = 1) -> GrowattDeviceRegisters:
    return GrowattDeviceRegisters(
        name=name, register=register, value_type=int, length=length
    )


def _covers(spans, keys) -> bool:
    """True if every requested key falls inside one of the (start, length) spans."""
    covered: set[int] = set()
    for start, length in spans:
        covered.update(range(start, start + length))
    return set(keys).issubset(covered)


# --- key expansion -------------------------------------------------------


def test_get_keys_from_register_expands_multi_word_registers():
    registers = {
        1: _u16("a", 1),
        5: _u16("b", 5, length=2),  # occupies 5 and 6
    }
    assert get_keys_from_register(registers) == {1, 5, 6}


def test_get_all_keys_from_register_expands_only_requested_keys():
    registers = {
        1: _u16("a", 1),
        5: _u16("b", 5, length=2),
    }
    # Only key 5 is requested; it must pull in its continuation word 6.
    assert get_all_keys_from_register(registers, {5}) == {5, 6}
    # A key with no register definition is passed through unchanged.
    assert get_all_keys_from_register(registers, {99}) == {99}


# --- sequence building ---------------------------------------------------


def test_contiguous_keys_become_single_span():
    spans = keys_sequences([0, 1, 2, 3], maximum_length=20)
    assert spans == {(0, 4)}


def test_large_gap_splits_into_separate_reads():
    # The two clusters are far further apart than the separation threshold
    # (maximum_length / 4 == 5), so they must not be merged into one read.
    spans = keys_sequences([0, 1, 2, 50, 51], maximum_length=20)
    assert len(spans) == 2
    assert _covers(spans, [0, 1, 2, 50, 51])
    # No span should bridge the gap.
    assert all(length <= 3 for _, length in spans)


def test_run_longer_than_maximum_length_is_split():
    keys = list(range(0, 31))  # 31 contiguous words, max read is 20
    spans = keys_sequences(keys, maximum_length=20)
    assert len(spans) >= 2
    assert _covers(spans, keys)
    assert all(length <= 20 for _, length in spans)


def test_every_key_is_covered_exactly_once_for_mixed_layout():
    keys = [0, 1, 2, 3, 9, 10, 45, 46, 47]
    spans = keys_sequences(keys, maximum_length=20)
    assert _covers(spans, keys)


def test_split_sequence_no_split_when_within_bounds():
    assert split_sequence([0, 1, 2, 3], maximum_length=20) == []


# --- end-to-end over a DeviceRegisters ----------------------------------


def test_register_sequences_covers_holding_and_input():
    holding = {1: _u16("hv", 1), 2: _u16("hw", 2)}
    input_regs = {10: _u16("iv", 10, length=2)}
    device = DeviceRegisters(holding=holding, input=input_regs, max_length=20)

    seqs = register_sequences(RegisterKeys(holding={1, 2}, input={10}), device)

    assert _covers(seqs.holding, [1, 2])
    assert _covers(seqs.input, [10, 11])


def test_register_sequences_skips_empty_side():
    device = DeviceRegisters(holding={1: _u16("hv", 1)}, input={}, max_length=20)
    seqs = register_sequences(RegisterKeys(holding={1}), device)
    assert seqs.input == set()
    assert _covers(seqs.holding, [1])


def test_register_sequences_empty_side_branches():
    regs = DeviceRegisters(
        holding={1: _u16("a", 1), 2: _u16("b", 2)},
        input={10: _u16("c", 10)},
        max_length=20,
    )
    # Only holding requested -> the input sequence stays empty.
    only_h = register_sequences(RegisterKeys(holding={1, 2}, input=set()), regs)
    assert only_h.holding and not only_h.input
    assert len(only_h) == len(only_h.holding)  # __len__

    # Only input requested -> the holding sequence stays empty.
    only_i = register_sequences(RegisterKeys(holding=set(), input={10}), regs)
    assert only_i.input and not only_i.holding


def test_keys_sequences_never_exceed_maximum_length():
    """Property check: no planned read is longer than the device allows.

    A read longer than ``maximum_length`` is rejected by the inverter, which
    fails the whole poll. Sparse key sets with several large gaps exercise the
    split-merging branches in ``split_sequence``.
    """
    import random

    rng = random.Random(1234)
    for _ in range(2000):
        maximum_length = rng.choice((20, 40, 45, 100, 125))
        keys: set[int] = set()
        position = rng.randrange(0, 50)
        for _ in range(rng.randrange(1, 60)):
            keys.add(position)
            position += rng.choice((1, 1, 1, 2, 3, maximum_length // 3, 70, 200))

        spans = keys_sequences(keys, maximum_length)

        assert _covers(spans, keys), (sorted(keys), maximum_length, spans)
        assert all(length <= maximum_length for _start, length in spans), (
            sorted(keys),
            maximum_length,
            sorted(spans),
        )


def test_multi_word_registers_are_never_split_across_reads():
    """Both words of a 32-bit value must come from the same request.

    Read in two requests, a carry into the high word between them decodes the
    counter off by 65536 raw (6553.6 kWh at 0.1 kWh scale).
    """
    import random

    rng = random.Random(4321)
    for _ in range(2000):
        maximum_length = rng.choice((20, 45, 100))
        registers: dict[int, GrowattDeviceRegisters] = {}
        position = rng.randrange(0, 20)
        for index in range(rng.randrange(1, 60)):
            length = rng.choice((1, 1, 2, 2, 4))
            registers[position] = _u16(f"r{index}", position, length)
            position += length + rng.choice((0, 0, 0, 1, 5, 40))
        device = DeviceRegisters(holding=registers, input={}, max_length=maximum_length)

        spans = register_sequences(RegisterKeys(holding=set(registers)), device).holding

        for register in registers.values():
            words = set(range(register.register, register.register + register.length))
            assert any(
                words <= set(range(start, start + length)) for start, length in spans
            ), (register, maximum_length, sorted(spans))
            assert all(length <= maximum_length for _start, length in spans)
