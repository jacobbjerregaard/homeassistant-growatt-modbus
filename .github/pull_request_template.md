## What and why

<!-- What changes, and what problem it solves. Link the issue if there is one. -->

## Register changes

<!-- Delete if not applicable.

Register definitions are the easiest thing to get subtly wrong, and the
hardest to notice. If you changed an address, length, scale or signedness,
please cite the protocol document section, and say which models it applies
to - several registers mean different things on MAX vs Storage Power units.
-->

## Testing

- [ ] `pytest` (pure-logic suite)
- [ ] `pytest tests/integration` (needs Home Assistant)
- [ ] `ruff check .` and `mypy`

## User impact

<!-- Delete if none. Call out anything users will notice: entities added or
removed, renamed, or changes to a unit or device class - the last one makes
Home Assistant discard long-term statistics for the affected entities. -->
