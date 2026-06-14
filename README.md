[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

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
    `number.*`).
  * `select`: battery type, generator force, UPS output voltage, UPS output
    frequency.
  * `switch`: AC charge, pre-PTO, generator charge, UPS function, dry contact.
  * `button`: "Sync device time" writes the Home Assistant host clock to the
    inverter (useful because clock drift skews the daily energy resets).
* **Additional telemetry**: battery voltage / current, self-consumption power
  and energy (today/total), system output energy (today/total), BMS max/min
  SOC, and parallel battery count.
* **Battery health**: State of Health (SOH), BMS status, cycle count, cell
  voltage min/max, charge/discharge current limits, and storage fault/warning
  codes.
* **Per-battery-module serial sensors**: the module count is auto-detected
  (holding register 185), and each module's serial number is exposed so you can
  track which physical module sits in each position over time. The protocol
  exposes per-module *identity* but no per-module live telemetry, so live
  battery values are the system aggregates above. Override the count with the
  *Number of battery modules* option if auto-detection is wrong.
* **Time-slot scheduling**: the `growatt_modbus.set_time_slot` service
  configures any of the 9 battery charge/discharge time slots (start/end time,
  priority load/battery/grid, enable).
* **Firmware readouts** (diagnostic): inverter, control, DSP, BDC and BMS
  firmware versions, plus per-module DSP/MCU firmware where available.

The writable controls are grouped under *Configuration* on the device page and
internal readings under *Diagnostic*. A redacted diagnostics download is
available from the device's three-dot menu for bug reports.

Some command registers are model-specific (US / XH variants); on a model that
does not implement a register it may simply read `0` and ignore writes.

> Scope note: the V1.39 document defines ~1700 registers across every model and
> for Growatt's own server (raw per-unit serial-number blocks, 10-unit parallel
> BDC/APX battery dumps, reserved ranges). This integration deliberately
> surfaces the meaningful storage/hybrid telemetry and command registers rather
> than every register. Open an issue if you need a specific one.

Currently the communication layer (API) is included in this repository but following the guidelines of HASS there should be seperate repositories

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