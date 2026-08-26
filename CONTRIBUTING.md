# Contributing

Thanks for helping out.

## Layout

```
custom_components/growatt_modbus/
  api/                  Modbus transport and protocol decoding.
                        Deliberately free of Home Assistant imports, so it
                        can be unit-tested standalone.
    device_type/        Per-model register maps and decoders.
  entity_descriptions/  Entity description tables, by device family.
  optimizer/            Optional EMHASS bridge.
  coordinator.py        DataUpdateCoordinator and runtime data.
  entity.py             Shared entity base and device-registry helper.
```

The `api/` layer stays Home-Assistant-free. `tests/conftest.py` registers it
as a standalone package named `growatt_api` so the pure-logic suite can import
it without Home Assistant installed. If you add an import of `homeassistant`
under `api/`, that suite stops working.

## Tests

Two suites, two interpreters:

```bash
pip install -r requirements_test.txt
pytest                    # pure logic; tests/integration is skipped

pip install -r requirements_test_ha.txt
pytest tests/integration  # real config entries, coordinators, entities
```

Combined coverage, which needs both venvs:

```bash
./scripts/coverage.sh
```

Lint and types:

```bash
pip install -r requirements_lint.txt
ruff check .
mypy
```

## Changing register definitions

This is where the bugs live, so it gets its own section.

A register is defined by its address, length, scale, signedness and value
type. Getting any of them wrong produces a plausible-looking number rather
than an error, which is why these need a citation rather than a guess.

- **Cite the protocol document** - section and register number - in the PR.
- **Say which models it applies to.** Registers 112-115, for example, are
  ACCharge energy on Storage Power units and Warn Maincode / real Power
  Percent / inv start delay / bINVAllFaultCode on the MAX series. A register
  that only exists on some models belongs in that model's map, not the
  shared one.
- **Scale is a divisor.** A register documented as `0.1 kWh` per LSB gets
  `scale=10`. Writing `scale=0.1` multiplies by ten instead.
- **Mark anything that can cross zero as `signed=True`.** An unsigned 32-bit
  register reading -0.1 decodes to 429,496,729.5. For sensors with
  `state_class: TOTAL_INCREASING` Home Assistant treats the following drop
  as a meter reset and folds that into the lifetime total permanently.
  Signed decoding is a no-op for real readings - 100 kW is 1e6 raw, far
  below the 2^31 sign bit.
- **Only `float` (with `length=2`), `str` and `custom_function` honour
  `length`.** The `int` and `bool` paths always decode a single 16-bit word.

## Reading a wrong value

Useful fingerprints when triaging a report:

| symptom | likely cause |
|---|---|
| ratio of exactly 65,536 | word order, or only one word decoded |
| value just below 429,496,729.5 | negative value decoded as unsigned; the gap from that ceiling is the true magnitude |
| pinned exactly at 429,496,729.5 | register not implemented on that model (reads all ones) |
| clean 10x or 100x | wrong `scale` |
| plausible but wrong quantity | wrong device type, so every address is offset |

## Style

`ruff` and `mypy` run in CI and must be clean. Match the surrounding code;
the register tables are hand-aligned on purpose.
