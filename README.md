[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

<img src="brands/logo.png" alt="Growatt Modbus" width="420">

# Home Assistant Growatt Modbus Intergration
 Growatt Modbus is a custom component for Home Assistant that connects directly to your Growatt inverter using the Modbus protocol and supports Serial, TCP and UDP communication layers to connect to your inverter

 This repository is at this moment not part of HACS therefore requiring manual adding this custom repository to HACS.

 This intergration makes use of the *config_flow* and can be configured using the UI no confgration required using the `configration.yaml`

 The requirement to be able to uses this intergration are:
 * The communication layer and related parameters
 * Modbus address of the device (Default value: 1)
 * Used protocol version by your device

## Protocol version
Currently there are 2 protocol versions supported with this intergration:
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

Some command registers are model-specific (US / XH variants); on a model that
does not implement a register it may simply read `0` and ignore writes.

> Scope note: the V1.39 document defines ~1700 registers across every model and
> for Growatt's own server (raw per-unit serial-number blocks, 10-unit parallel
> BDC/APX battery dumps, reserved ranges). This integration deliberately
> surfaces the meaningful storage/hybrid telemetry and command registers rather
> than every register. Open an issue if you need a specific one.

Currently the communication layer (API) is included in this repository but following the guidelines of HASS there should be seperate repositories

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