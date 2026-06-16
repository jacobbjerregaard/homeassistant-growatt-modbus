"""Pure logic to compile an EMHASS battery schedule into time-of-use slots.

This module is intentionally free of Home Assistant / pymodbus imports so it can
be unit-tested in the stdlib-only environment (imported as ``growatt_api``).

Priority codes match ``TIME_SLOT_PRIORITIES`` in ``device_type/storage_120``:
``0 = Load First`` (self-consumption, the inverter's resting behaviour),
``1 = Battery First`` (charge the battery, from grid when AC charge is on) and
``2 = Grid First`` (export to grid).
"""
from __future__ import annotations

LOAD_FIRST = 0
BATTERY_FIRST = 1
GRID_FIRST = 2

# Steps below these power magnitudes (W) are treated as "idle" / resting.
DEFAULT_CHARGE_THRESHOLD = 50.0
DEFAULT_DISCHARGE_THRESHOLD = 50.0
DEFAULT_EXPORT_THRESHOLD = 50.0


def priority_for_step(
    p_batt: float | None,
    p_grid: float | None = None,
    *,
    charge_threshold: float = DEFAULT_CHARGE_THRESHOLD,
    discharge_threshold: float = DEFAULT_DISCHARGE_THRESHOLD,
    export_threshold: float = DEFAULT_EXPORT_THRESHOLD,
) -> int:
    """Map an EMHASS battery (and optional grid) power forecast to a priority.

    Sign conventions follow EMHASS: ``p_batt`` negative = charging, positive =
    discharging; ``p_grid`` positive = importing, negative = exporting.

    - Charging  -> Battery First.
    - Discharging while exporting -> Grid First.
    - Discharging to cover load, or idle -> Load First (the default).
    """
    if p_batt is None:
        return LOAD_FIRST
    if p_batt < -charge_threshold:
        return BATTERY_FIRST
    if p_batt > discharge_threshold:
        if p_grid is not None and p_grid < -export_threshold:
            return GRID_FIRST
        return LOAD_FIRST
    return LOAD_FIRST


def compile_tou_slots(
    steps: list[tuple[int, int, int]],
    max_slots: int,
    default_priority: int = LOAD_FIRST,
) -> list[tuple[int, int, int]]:
    """Compile contiguous ``(start_min, end_min, priority)`` steps into slots.

    ``start_min`` / ``end_min`` are minutes-of-day. Adjacent steps with the same
    priority are merged. Runs at ``default_priority`` are dropped, since the
    inverter falls back to that mode whenever no slot is active, so they need no
    explicit slot. If more non-default runs remain than ``max_slots`` the longest
    are kept (and the rest fall back to the default behaviour).

    Returns up to ``max_slots`` ``(start_min, end_min, priority)`` tuples sorted
    by start time.
    """
    # 1. Merge adjacent, contiguous steps that share a priority.
    merged: list[tuple[int, int, int]] = []
    for start, end, prio in steps:
        if merged and merged[-1][2] == prio and merged[-1][1] == start:
            prev_start, _prev_end, _prio = merged[-1]
            merged[-1] = (prev_start, end, prio)
        else:
            merged.append((start, end, prio))

    # 2. Drop default-priority runs - they are the inverter's resting state.
    runs = [run for run in merged if run[2] != default_priority]

    # 3. Cap to the hardware slot budget, keeping the longest windows.
    if len(runs) > max_slots:
        runs = sorted(runs, key=lambda run: run[1] - run[0], reverse=True)[:max_slots]
        runs.sort(key=lambda run: run[0])

    return runs


def minutes_to_hm(minutes: int) -> tuple[int, int]:
    """Convert minutes-of-day to ``(hour, minute)`` for slot encoding.

    End-of-day (1440) is represented as 23:59 because the inverter expects a
    same-day end time within a slot's two registers.
    """
    if minutes >= 1440:
        return 23, 59
    return divmod(minutes, 60)
