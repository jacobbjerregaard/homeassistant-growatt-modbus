"""Battery charge/discharge time-of-use slots (Protocol II V1.39, storage).

Split out of ``storage_120`` because the slot encoding is consumed well
outside the register map: the ``tou`` entity helpers, the ``set_time_slot``
service and the EMHASS optimizer all encode or decode slots without caring
about the rest of the storage protocol.
"""

from .base import GrowattDeviceRegisters

# Battery charge/discharge time slots 1-9. Each slot is a register pair:
#   reg1: Bit0-7 start minute | Bit8-12 start hour | Bit13-14 priority | Bit15 enable
#   reg2: Bit0-7 end minute   | Bit8-12 end hour
# Slots 1-4 are at 3038/3040/3042/3044; slots 5-9 at 3050/3052/.../3058.
TIME_SLOT_PRIORITIES = {"load": 0, "battery": 1, "grid": 2}


def time_slot_register(slot: int) -> int:
    """Return the first holding register of time slot `slot` (1-9)."""
    if 1 <= slot <= 4:
        return 3038 + (slot - 1) * 2
    if 5 <= slot <= 9:
        return 3050 + (slot - 5) * 2
    raise ValueError(f"time slot must be 1-9, got {slot}")


def encode_time_slot(
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    priority: int,
    enabled: bool,
) -> tuple[int, int]:
    """Encode a time slot into its two register values (reg1, reg2)."""
    reg1 = (
        (start_minute & 0xFF)
        | ((start_hour & 0x1F) << 8)
        | ((priority & 0x3) << 13)
        | ((1 if enabled else 0) << 15)
    )
    reg2 = (end_minute & 0xFF) | ((end_hour & 0x1F) << 8)
    return reg1, reg2


def decode_time_slot(reg1: int, reg2: int) -> dict:
    """Decode a slot register pair into its fields."""
    return {
        "start_hour": (reg1 >> 8) & 0x1F,
        "start_minute": reg1 & 0xFF,
        "end_hour": (reg2 >> 8) & 0x1F,
        "end_minute": reg2 & 0xFF,
        "priority": (reg1 >> 13) & 0x3,
        "enabled": bool((reg1 >> 15) & 0x1),
    }


def apply_time_slot_field(reg1: int, reg2: int, **changes) -> tuple[int, int]:
    """Return new (reg1, reg2) with `changes` applied to the decoded fields."""
    fields = decode_time_slot(reg1, reg2)
    fields.update(changes)
    return encode_time_slot(
        fields["start_hour"],
        fields["start_minute"],
        fields["end_hour"],
        fields["end_minute"],
        fields["priority"],
        fields["enabled"],
    )


def build_time_slot_registers(count: int) -> tuple[GrowattDeviceRegisters, ...]:
    """Raw register pair (word1/word2) for each of `count` time-of-use slots."""
    registers: list[GrowattDeviceRegisters] = []
    for slot in range(1, count + 1):
        base = time_slot_register(slot)
        registers.extend(
            (
                GrowattDeviceRegisters(
                    name=f"tou_slot_{slot}_word1", register=base, value_type=int
                ),
                GrowattDeviceRegisters(
                    name=f"tou_slot_{slot}_word2", register=base + 1, value_type=int
                ),
            )
        )
    return tuple(registers)
