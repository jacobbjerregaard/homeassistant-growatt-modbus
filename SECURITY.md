# Security Policy

## Supported versions

This is a Home Assistant custom integration distributed through HACS. Fixes are
released on a rolling basis, so only the **latest published release** is
supported. Please reproduce any issue on the most recent version before
reporting it.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Instead, use GitHub's private vulnerability reporting:

1. Go to the [**Security** tab](https://github.com/jacobbjerregaard/homeassistant-growatt-modbus/security) of this repository.
2. Click **Report a vulnerability** and fill in the advisory form.

This keeps the report private until a fix is available. Helpful details to
include:

- the integration version and your Home Assistant version,
- the inverter model and connection layer (serial / TCP / UDP),
- steps to reproduce and the impact you observed.

You can expect an initial response within a few days. Once a fix is released, the
advisory will be published with appropriate credit.

## Scope

This integration talks to inverters over a local Modbus link and performs no
outbound network calls except the optional EMHASS optimizer bridge (to a
user-configured URL). Reports about register writes, the config/options flow,
diagnostics output (which is redacted), or the EMHASS bridge are all in scope.
