[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![CodeQL](https://github.com/jacobbjerregaard/homeassistant-growatt-modbus/actions/workflows/codeql.yml/badge.svg)](https://github.com/jacobbjerregaard/homeassistant-growatt-modbus/actions/workflows/codeql.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Known Vulnerabilities](https://snyk.io/test/github/jacobbjerregaard/homeassistant-growatt-modbus/badge.svg)](https://snyk.io/test/github/jacobbjerregaard/homeassistant-growatt-modbus)

# Home Assistant Growatt Modbus Integration
 Growatt Modbus is a custom component for Home Assistant that connects directly to your Growatt inverter using the Modbus protocol and supports Serial, TCP and UDP communication layers to connect to your inverter

 This repository is at this moment not part of HACS therefore requiring manual adding this custom repository to HACS.

 This integration makes use of the *config_flow* and can be configured using the UI; no configuration is required in `configuration.yaml`.

 The requirements to be able to use this integration are:
 * The communication layer and related parameters
 * Modbus address of the device (Default value: 1)
 * Used protocol version by your device

## Protocol version
Currently there are 2 protocol versions supported with this integration:
* RTU Protocol version 3.15 used by older models that would support up to two strings
* RTU Protocol 2 used by newer models and larger devices (storage / hybrid)

The storage / hybrid (Protocol II) register map has been updated to the
**V1.39 (2024-04-16)** specification.

### Storage / hybrid (Protocol II V1.39)
In addition to the existing telemetry, the storage/hybrid device type now
exposes:

* **Writable controls** (the V1.39 "command API"):
  * `number`: Grid-First stop-discharge SOC, On-Grid stop-discharge SOC, and
    the Grid-First discharge rate / Battery-First charge rate / Battery-First
    stop SOC (these three moved from read-only `sensor.*` to writable
    `number.*`), plus the generic Battery charge stop SOC / Battery discharge
    stop SOC (holding 951/952, not tied to a priority mode).
  * `select`: export limit (disable / RS485 / RS232 / CT), battery type,
    generator force, UPS output voltage, UPS output frequency.
  * `number`: export limit power rate (%), in addition to the SOC settings.
  * `switch`: AC charge, pre-PTO, generator charge, UPS function, dry contact.
  * `button`: "Sync device time" writes the Home Assistant host clock to the
    inverter (useful because clock drift skews the daily energy resets).
* **Additional telemetry**: battery voltage / current, self-consumption power
  and energy (today/total), system output energy (today/total), BMS max/min
  SOC, and parallel battery count.
* **Battery health**: State of Health (SOH), BMS status, cycle count, cell
  voltage min/max, charge/discharge current limits, and storage fault/warning
  codes.
* **Per-battery-module sensors**: the module count is auto-detected (holding
  register 185), and each module exposes live telemetry (state, SOC, SOH,
  voltage, current, power, total charged/discharged energy, cell voltage
  min/max, temperature min/max) from the 5080+ input block, plus identity
  (serial number, DSP/MCU firmware). The module state and derating mode are
  decoded to text (Standby / Charging / Discharging / Fault / …) and cell
  voltages are shown to millivolt resolution. A *Diagnostic* group adds the
  balance state / hours, cell capacity (effective / min), Ah integral,
  cumulative charge/discharge capacity, cycle count, fault / warning codes and
  subcodes, internal short-circuit / SOX-correction state, and the
  charge/discharge enable flags. Each module's sensors are grouped under their
  own device, named by the module serial number, so a module keeps its identity
  and history even if the slot order changes. Override the count with the
  *Number of battery modules* option if auto-detection is wrong.
* **Time-of-use scheduling**: set *Number of time-of-use slots* in the options
  to expose each battery charge/discharge slot as editable entities (start/end
  time, priority Load/Battery/Grid First, enable) on the device page. The
  `growatt_modbus.set_time_slot` service is also available for automations.
* **Firmware readouts** (diagnostic): inverter, control, DSP, BDC and BMS
  firmware versions, plus per-module DSP/MCU firmware where available.
* **Nameplate / rated values** (diagnostic): inverter rated power (Pmax,
  holding 6–7, VA), cell rated capacity (holding 3119, Ah) and — APX only —
  battery rated capacity (holding 3121; the spec lists no unit, so the raw
  value is shown).

The writable controls are grouped under *Configuration* on the device page and
internal readings under *Diagnostic*. A redacted diagnostics download is
available from the device's three-dot menu for bug reports.

State sensors (system / balance / derating / BMS status) are exposed as
`enum` device-class entities. If the inverter is unreachable the entities go
*unavailable* (rather than holding a stale value), and setup retries
automatically with Home Assistant's normal backoff until the device responds.

If the connection details change (for example the inverter gets a new IP, or
you move it to a different serial port), use **Reconfigure** on the device's
three-dot menu to update them in place — the integration verifies the same
device answers (by serial number) before saving, so its entities and history
are preserved.

Some command registers are model-specific (US / XH variants); on a model that
does not implement a register it may simply read `0` and ignore writes.

> Scope note: the V1.39 document defines ~1700 registers across every model and
> for Growatt's own server (raw per-unit serial-number blocks, 10-unit parallel
> BDC/APX battery dumps, reserved ranges). This integration deliberately
> surfaces the meaningful storage/hybrid telemetry and command registers rather
> than every register. Open an issue if you need a specific one.

Currently the communication layer (API) is included in this repository but following the guidelines of HASS there should be separate repositories

### Peak shaving (Protocol II V1.39)

Peak shaving caps how much power the system draws from the grid, discharging the
battery to cover demand above an *Import Limit* during expensive peak periods. It
runs alongside the inverter's normal mode: when the battery SOC is **above** the
*Reserved SOC* the system behaves as originally configured (self-consumption by
default, or TOU if you switch to it on the previous page); when SOC is **below**
the *Reserved SOC*, the battery only supplies the load while the *Import Limit* is
exceeded. If no *Reserved SOC* is set, the system keeps its original mode and
simply never draws more than the *Import Limit* from the grid.

The following controls appear on the device page (storage / hybrid only):

* `switch`: **Peak Shaving Mode** (holding 3306) — enable / disable.
* `number`: **Peak Shaving Import Limit** (holding 3307, kW) — the maximum power
  drawn from the grid.
* `number`: **Peak Shaving Export Limit** (holding 3308, kW, may be negative) —
  the maximum power fed into the grid. When the export limit is enabled and set
  to a negative value, the import limit must be greater than its absolute value
  (e.g. a 10 kW system with a −30 % export limit needs an import limit above
  3 kW).
* `switch`: **Reserved SOC for Peak Shaving** (holding 3309) — enable the
  reserved-SOC threshold.
* `number`: **Reserved SOC for Peak Shaving Level** (holding 3310, %) — the SOC
  above which the system runs in its originally-set mode.

## Energy optimization (EMHASS)

The integration can bridge to [EMHASS](https://github.com/davidusb-geek/emhass)
(Energy Management for Home Assistant), which optimises battery usage against
dynamic electricity prices and a PV forecast. EMHASS does the optimisation; this
integration reads back the plan and (in later phases) drives the battery's
time-of-use slots and charge controls to follow it.

Set the *EMHASS URL* in the integration options (optionally a bearer token, a
battery-SOC sensor and an update interval). When configured, four diagnostic
sensors appear under the inverter device, mirroring the plan EMHASS publishes:

* *Optimizer Status* — EMHASS optimisation result (e.g. `Optimal`).
* *Optimizer Battery Power Target* — planned battery power (W; negative =
  charging). The full forecast series is exposed as a `forecast` attribute.
* *Optimizer Battery SOC Target* — planned state of charge (%).
* *Optimizer Plan Updated* — when the plan was last read.

The `growatt_modbus.run_optimization` service triggers a fresh EMHASS day-ahead
optimisation + publish and refreshes those sensors.

### Letting the optimizer control the battery (day-ahead)

Reading the plan is **read-only by default**. To let the optimizer act on it,
turn on *Let the optimizer control the battery* in the options. When enabled it
compiles the published day-ahead plan onto the inverter:

* Each forecast step is mapped to a priority — charging → **Battery First**,
  discharging while exporting → **Grid First**, everything else →
  **Load First** (the inverter's resting behaviour).
* Adjacent same-priority steps are merged into contiguous windows and written to
  the 9 time-of-use slots (Load-First windows need no slot; the longest windows
  win if the plan needs more than 9). Unused slots are disabled so a stale
  window can't linger.
* **AC charge** is enabled whenever the plan includes a grid-charging window, so
  the battery actually charges from the grid during cheap hours.

Compilation runs once just after midnight (from the freshly published day-ahead
plan) and on every `run_optimization` call. With no plan available the existing
slots are left untouched rather than stranding the battery. **While enabled the
optimizer owns all 9 time-of-use slots and the AC-charge control**, so don't
also drive them by hand.

The *Optimizer Control* switch (under the inverter device) is the master on/off
for this actuation and mirrors the option above, so you can stop the optimizer
from a dashboard without re-opening the options.

### Intraday corrections (model-predictive)

The day-ahead slots are a baseline. While control is enabled the optimizer also
runs a lightweight correction every *optimizer update interval*: it re-runs the
EMHASS naive-MPC optimisation seeded with the live battery SOC (from the
configured SOC sensor) and then adjusts the **current** controls without
rewriting the slots —

* **AC charge** is switched on/off to match whether the plan charges right now;
* the **stop-charge / stop-discharge SOC** tracks the plan's SOC target, so the
  battery follows the planned trajectory and stops at the right level;
* the **charge / discharge rate** is set from the planned power, converting
  EMHASS watts to the inverter's percentage. The battery max power is taken from
  the *Battery max power* option, or — when that is left at 0 — derived live from
  the BMS current limit × battery voltage; with neither available the rates are
  left untouched.

Fail-safes guard every write: corrections are skipped unless the plan is
`Optimal`, and any SOC target is clamped to the battery's BMS-reported safe
window (a missing or bogus BMS reading falls back to 0–100 % rather than
stranding the battery).

### Options layout and custom EMHASS entities

The integration options are grouped into **General & polling** and **EMHASS
optimizer** sections. If your EMHASS instance publishes under non-default entity
ids, override the battery-power, battery-SOC, grid-power and status sensors in
the optimizer section; left blank they fall back to the EMHASS defaults
(`sensor.p_batt_forecast`, `sensor.soc_batt_forecast`, `sensor.p_grid_forecast`,
`sensor.optim_status`).

## Data updates

This is a **local polling** integration. Each configured inverter is polled
directly over Modbus (serial, TCP or UDP) by a data update coordinator:

* The **main coordinator** reads the full register set on a fixed interval
  (default **60 s**, configurable under *General & polling* options).
* When **fast power scanning** is enabled a **second coordinator** polls just the
  power registers at a shorter interval (default **5 s**) so live power entities
  update more frequently without re-reading everything.

Transport access is serialised, so the two coordinators never talk to the device
at the same time. If the link drops, the entities become *unavailable* and the
coordinator keeps retrying (reconnecting periodically) until the inverter
responds again. Daily-energy sensors reset at local midnight.

## Automation examples

Schedule a battery time-of-use slot (charge from grid 02:00–05:00):

```yaml
automation:
  - alias: "Night charge window"
    trigger:
      - platform: time
        at: "01:55:00"
    action:
      - service: growatt_modbus.set_time_slot
        data:
          device_id: "{{ device_id('Growatt …') }}"
          slot: 1
          start_time: "02:00:00"
          end_time: "05:00:00"
          priority: "Battery first"
          enabled: true
```

Notify when the battery gets low:

```yaml
automation:
  - alias: "Battery low warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.growatt_…_soc
        below: 15
    action:
      - service: notify.mobile_app
        data:
          message: "Growatt battery at {{ states('sensor.growatt_…_soc') }}%"
```

Trigger an EMHASS optimisation on demand (when the optimizer is configured):

```yaml
- service: growatt_modbus.run_optimization
```

You can also set the charge/discharge stop-SOC and rate directly through the
**number** entities, and pick a slot priority through the **select** entities.

## Troubleshooting

* **Device not detected / setup fails** — double-check the Modbus *address*
  (default 1), and for serial the *baud rate*, *parity*, *stop bits* and *byte
  size*. RS485 A/B polarity being swapped is the most common wiring fault.
* **Entities show *unavailable*** — the inverter stopped responding. The
  integration reconnects automatically; verify cabling/power and that no other
  client (e.g. ShineWiFi dongle) is holding the Modbus line.
* **Connection parameters changed** (new IP, different serial port) — use the
  entry's **Reconfigure** option instead of deleting and re-adding it, so entity
  history is preserved.
* **Firmware sensors are missing** — the firmware-version sensors are
  *disabled by default*; enable them from the entity settings if you want them.
* **Enable debug logging** to capture register-level detail when reporting an
  issue:

  ```yaml
  logger:
    logs:
      custom_components.growatt_modbus: debug
  ```

## Testing

Two test suites:

* **Pure-logic** (register batching, decoding, write-encoding) — runs on any
  recent Python, no Home Assistant required:

  ```bash
  pip install -r requirements_test.txt
  pytest            # tests/integration is skipped automatically
  ```

* **Home Assistant integration** (config-entry setup, entities, write paths) —
  needs Python 3.13:

  ```bash
  pip install -r requirements_test_ha.txt
  pytest tests/integration
  ```

Both run in CI on every push/PR.

The two suites run in different interpreters, so combined coverage is collected
separately and merged by `scripts/coverage.sh` (≈95%).

## Credits

This project was originally based on
[Homeassistant-Growatt-Local-Modbus](https://github.com/WouterTuinstra/Homeassistant-Growatt-Local-Modbus)
by Wouter Tuinstra and contributors, and started as a fork of it. It has since
been substantially rewritten and extended (Protocol II V1.39 storage/hybrid
support, per-battery-module telemetry, writable controls, time-of-use
scheduling, an EMHASS optimization bridge and a full test suite), and is
maintained independently under the `growatt_modbus` domain. Thanks to the
original authors for the foundation.

Licensed under the Apache License 2.0 (see [LICENSE](LICENSE)), the same license
as the upstream project.