"""Schema library shim: probatio on Home Assistant 2026.10+, voluptuous before.

From 2026.10 Home Assistant validates with probatio and aliases `voluptuous` to
it at runtime, but its type hints name probatio's classes, so schemas built
from `voluptuous` no longer type-check. Older releases (hacs.json allows
2024.12+) don't ship probatio. The two are API-compatible, so modules import
`vol` from here instead of importing either library directly.
"""

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol  # type: ignore[no-redef]

__all__ = ["vol"]
