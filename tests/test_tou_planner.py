"""Pure-logic tests for the EMHASS -> time-of-use slot compiler."""
from growatt_api.tou_planner import (
    BATTERY_FIRST,
    GRID_FIRST,
    LOAD_FIRST,
    clamp_soc,
    compile_tou_slots,
    minutes_to_hm,
    power_to_rate,
    priority_for_step,
)


# --- priority_for_step -----------------------------------------------------


def test_charging_maps_to_battery_first():
    assert priority_for_step(-2000) == BATTERY_FIRST


def test_discharging_to_load_maps_to_load_first():
    assert priority_for_step(1500) == LOAD_FIRST
    # Importing from grid while discharging is still self-consumption.
    assert priority_for_step(1500, p_grid=300) == LOAD_FIRST


def test_discharging_while_exporting_maps_to_grid_first():
    assert priority_for_step(1500, p_grid=-1200) == GRID_FIRST


def test_idle_and_none_map_to_load_first():
    assert priority_for_step(0) == LOAD_FIRST
    assert priority_for_step(10) == LOAD_FIRST  # below threshold
    assert priority_for_step(None) == LOAD_FIRST


# --- compile_tou_slots -----------------------------------------------------


def test_adjacent_same_priority_steps_merge():
    steps = [
        (0, 60, BATTERY_FIRST),
        (60, 120, BATTERY_FIRST),
        (120, 180, BATTERY_FIRST),
    ]
    assert compile_tou_slots(steps, 9) == [(0, 180, BATTERY_FIRST)]


def test_default_priority_runs_are_dropped():
    steps = [
        (0, 120, BATTERY_FIRST),
        (120, 480, LOAD_FIRST),
        (480, 600, GRID_FIRST),
        (600, 1440, LOAD_FIRST),
    ]
    assert compile_tou_slots(steps, 9) == [
        (0, 120, BATTERY_FIRST),
        (480, 600, GRID_FIRST),
    ]


def test_non_contiguous_same_priority_stay_separate():
    steps = [
        (0, 60, BATTERY_FIRST),
        (60, 120, LOAD_FIRST),
        (120, 180, BATTERY_FIRST),
    ]
    assert compile_tou_slots(steps, 9) == [
        (0, 60, BATTERY_FIRST),
        (120, 180, BATTERY_FIRST),
    ]


def test_caps_to_max_slots_keeping_longest():
    # Three battery windows of 30, 120 and 60 minutes; max_slots=2 keeps the
    # two longest, re-sorted by start time.
    steps = [
        (0, 30, BATTERY_FIRST),
        (60, 90, LOAD_FIRST),
        (120, 240, BATTERY_FIRST),
        (300, 360, BATTERY_FIRST),
    ]
    result = compile_tou_slots(steps, 2)
    assert result == [(120, 240, BATTERY_FIRST), (300, 360, BATTERY_FIRST)]


def test_all_default_yields_no_slots():
    steps = [(0, 720, LOAD_FIRST), (720, 1440, LOAD_FIRST)]
    assert compile_tou_slots(steps, 9) == []


# --- minutes_to_hm ---------------------------------------------------------


def test_minutes_to_hm():
    assert minutes_to_hm(0) == (0, 0)
    assert minutes_to_hm(90) == (1, 30)
    assert minutes_to_hm(1439) == (23, 59)
    # End-of-day clamps to 23:59 so it fits a same-day slot end.
    assert minutes_to_hm(1440) == (23, 59)


# --- clamp_soc -------------------------------------------------------------


def test_clamp_soc_within_and_outside_range():
    assert clamp_soc(50, 10, 90) == 50
    assert clamp_soc(5, 10, 90) == 10
    assert clamp_soc(95, 10, 90) == 90
    # Defaults clamp to 0..100.
    assert clamp_soc(-5) == 0
    assert clamp_soc(150) == 100
    # Swapped bounds are tolerated.
    assert clamp_soc(50, 90, 10) == 50


# --- power_to_rate ---------------------------------------------------------


def test_power_to_rate():
    assert power_to_rate(2500, 5000) == 50
    assert power_to_rate(-2500, 5000) == 50  # sign ignored
    assert power_to_rate(6000, 5000) == 100  # clamped to 100
    assert power_to_rate(0, 5000) == 0
    # No maximum configured -> leave the rate untouched.
    assert power_to_rate(2500, 0) is None
    assert power_to_rate(2500, -1) is None
