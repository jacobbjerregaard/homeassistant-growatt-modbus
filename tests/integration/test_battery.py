"""Integration tests for the battery / BMS detail sensors."""
from homeassistant.helpers import entity_registry as er

from custom_components.growatt_modbus.const import DOMAIN


def _state(hass, entry, key: str) -> str:
    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{entry.unique_id}_{key}"
    entity = next(
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id == uid
    )
    return hass.states.get(entity.entity_id).state


async def test_bms_detail_sensors(hass, setup_storage):
    entry, fake = setup_storage
    fake.registers[3222] = 96    # SOH %
    fake.registers[3212] = 1     # BMS status -> Charging
    fake.registers[3230] = 3340  # cell voltage max 0.001V -> 3.34 V
    fake.registers[3219] = 5000  # max charge current 0.01A -> 50.0 A
    fake.registers[3167] = 7     # storage fault code

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "bms_soh") == "96"
    assert _state(hass, entry, "bms_status") == "Charging"
    assert float(_state(hass, entry, "bms_cell_voltage_max")) == 3.34
    assert float(_state(hass, entry, "bms_max_charge_current")) == 50.0
    assert _state(hass, entry, "storage_fault_code") == "7"


async def test_per_battery_module_serial_sensors(hass, setup_storage_modules):
    entry, fake = setup_storage_modules
    # Module 1 serial "TESTSN01" at holding 5400 (2 ASCII chars per register).
    for addr, word in {5400: 0x5445, 5401: 0x5354, 5402: 0x534E, 5403: 0x3031}.items():
        fake.registers[addr] = word
    # Module 2 serial "MOD2" at holding 5440.
    for addr, word in {5440: 0x4D4F, 5441: 0x4432}.items():
        fake.registers[addr] = word

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "battery_module_1_serial_number") == "TESTSN01"
    assert _state(hass, entry, "battery_module_2_serial_number") == "MOD2"


async def test_per_battery_module_live_telemetry(hass, setup_storage_modules):
    entry, fake = setup_storage_modules
    fake.registers[5080] = 2             # module 1 system state -> Charging
    fake.registers[5081] = 0x5F5F        # module 1 SOC replicated in both bytes -> 95
    fake.registers[5083] = 522           # module 1 voltage 0.1V -> 52.2
    fake.registers[5084] = (-15) & 0xFFFF  # module 1 current -1.5 A (signed)
    fake.registers[5086] = 0             # module 1 discharged total (u32 hi)
    fake.registers[5087] = 12345         # module 1 discharged total (u32 lo) 0.1kWh -> 1234.5
    fake.registers[5088] = 3340          # module 1 cell voltage max 0.001V -> 3.34
    fake.registers[5089] = 3310          # module 1 cell voltage min 0.001V -> 3.31
    fake.registers[5121] = 0x5F49        # module 2 SOC (5081 + 40) low byte 0x49 -> 73

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "battery_module_1_system_state") == "Charging"
    assert _state(hass, entry, "battery_module_1_soc") == "95"
    assert float(_state(hass, entry, "battery_module_1_voltage")) == 52.2
    assert float(_state(hass, entry, "battery_module_1_current")) == -1.5
    assert float(_state(hass, entry, "battery_module_1_discharge_energy_total")) == 1234.5
    assert float(_state(hass, entry, "battery_module_1_cell_voltage_max")) == 3.34
    assert float(_state(hass, entry, "battery_module_1_cell_voltage_min")) == 3.31
    assert _state(hass, entry, "battery_module_2_soc") == "73"


async def test_per_battery_module_health_detail(hass, setup_storage_modules):
    entry, fake = setup_storage_modules
    fake.registers[5094] = (2 << 8) | 6      # balance: Top requested, 6 h left
    fake.registers[5095] = 1500              # cell capacity 0.1Ah -> 150.0
    fake.registers[5097] = 11                # fault code
    fake.registers[5098] = 22                # warning code
    fake.registers[5099] = 0b11 | (3 << 8) | (5 << 12)  # subcode bitfield
    fake.registers[5100] = 0                 # charge energy total (u32 hi)
    fake.registers[5101] = 5000              #   (u32 lo) 0.1kWh -> 500.0
    fake.registers[5102] = 0                 # discharge capacity total (u32 hi)
    fake.registers[5103] = 20000             #   (u32 lo) 0.01Ah -> 200.0
    fake.registers[5108] = 1234              # cycle count 0.1 -> 123.4
    fake.registers[5109] = (0x12 << 8) | 0x34  # internal state bytes
    fake.registers[5110] = 19                # derating: Bus voltage too high

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "battery_module_1_balance_state") == "Top requested"
    assert int(float(_state(hass, entry, "battery_module_1_balance_time_hours"))) == 6
    assert float(_state(hass, entry, "battery_module_1_cell_capacity")) == 150.0
    assert _state(hass, entry, "battery_module_1_fault_code") == "11"
    assert _state(hass, entry, "battery_module_1_warning_code") == "22"
    assert _state(hass, entry, "battery_module_1_flags_charge_enabled") == "1"
    assert _state(hass, entry, "battery_module_1_flags_fault_subcode") == "5"
    assert _state(hass, entry, "battery_module_1_flags_warning_subcode") == "3"
    assert float(_state(hass, entry, "battery_module_1_charge_energy_total")) == 500.0
    assert float(_state(hass, entry, "battery_module_1_discharge_capacity_total")) == 200.0
    assert float(_state(hass, entry, "battery_module_1_cycle_count")) == 123.4
    assert _state(hass, entry, "battery_module_1_internal_short_circuit") == "18"  # 0x12
    assert _state(hass, entry, "battery_module_1_internal_sox_correction") == "52"  # 0x34
    assert _state(hass, entry, "battery_module_1_derating_mode") == "Bus voltage too high"


async def test_firmware_sensors(hass, setup_storage):
    entry, fake = setup_storage
    # Control firmware "FW12" at holding 12-14 (ASCII).
    fake.registers[12] = 0x4657  # "FW"
    fake.registers[13] = 0x3132  # "12"
    fake.registers[14] = 0x0000
    # BDC firmware: code "ZEBA" (3099-3100) + version 10 (3101).
    fake.registers[3099] = 0x5A45  # "ZE"
    fake.registers[3100] = 0x4241  # "BA"
    fake.registers[3101] = 10
    fake.registers[3105] = 7       # BMS firmware version

    await entry.runtime_data.main_coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, entry, "control_firmware") == "FW12"
    assert _state(hass, entry, "bdc_firmware") == "ZEBA-10"
    assert _state(hass, entry, "bms_firmware") == "7"
