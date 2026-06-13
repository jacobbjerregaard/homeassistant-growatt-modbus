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
* **Additional telemetry**: battery voltage / current, self-consumption power
  and energy (today/total), system output energy (today/total), BMS max/min
  SOC, and parallel battery count.

Some command registers are model-specific (US / XH variants); on a model that
does not implement a register it may simply read `0` and ignore writes.

> Scope note: the V1.39 document defines ~1700 registers across every model and
> for Growatt's own server (raw per-unit serial-number blocks, 10-unit parallel
> BDC/APX battery dumps, reserved ranges). This integration deliberately
> surfaces the meaningful storage/hybrid telemetry and command registers rather
> than every register. Open an issue if you need a specific one.

Currently the communication layer (API) is included in this repository but following the guidelines of HASS there should be seperate repositories