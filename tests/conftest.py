"""Test bootstrap for the Growatt Modbus integration.

The integration package (``custom_components/growatt_modbus``) imports Home
Assistant at import time, so it cannot be imported directly in a plain unit
test environment.  The protocol/decoding logic in ``API`` is however pure
Python (stdlib only) and is the part most worth testing.

To exercise it in isolation we register the ``API`` directory as a standalone
namespace package named ``growatt_api``.  Tests can then do::

    from growatt_api.utils import keys_sequences
    from growatt_api.device_type.base import GrowattDeviceRegisters

without pulling in Home Assistant or pymodbus.
"""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_API_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "growatt_modbus"
    / "API"
)


def _register_namespace_package(name: str, path: Path) -> None:
    """Expose ``path`` as an importable namespace package called ``name``."""
    if name in sys.modules:
        return
    spec = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = [str(path)]
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module


_register_namespace_package("growatt_api", _API_DIR)
