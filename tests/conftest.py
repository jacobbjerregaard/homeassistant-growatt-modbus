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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "custom_components" / "growatt_modbus" / "API"

# Make ``custom_components`` importable for the Home Assistant integration tests.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _register_namespace_package(name: str, path: Path) -> None:
    """Expose ``path`` as an importable namespace package called ``name``."""
    if name in sys.modules:
        return
    spec = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = [str(path)]
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module


_register_namespace_package("growatt_api", _API_DIR)


# The tests/integration suite needs Home Assistant + pytest-homeassistant-custom
# -component. When those aren't installed (e.g. the pure-logic Python 3.14 venv)
# skip collecting that directory entirely so the rest of the suite still runs.
try:
    import pytest_homeassistant_custom_component  # noqa: F401
except ImportError:
    collect_ignore = ["integration"]
