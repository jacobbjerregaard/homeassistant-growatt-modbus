"""The declared minimum versions must cover the APIs the integration uses.

HACS offers an update to anyone whose Home Assistant meets hacs.json, and
Home Assistant skips installing a requirement that is already satisfied. A
floor set too low therefore ships an integration that fails at runtime:

- pymodbus: the client calls pass ``device_id=``, which pymodbus 3.10.0
  introduced (earlier releases call it ``slave=``). With 3.8/3.9 already
  installed - e.g. pinned by Home Assistant's own modbus integration - every
  read and write raises TypeError.
- Home Assistant: ``UpdateFailed`` accepts translation arguments from 2024.12,
  and the reconfigure flow uses helpers added in 2024.11.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIN_PYMODBUS = (3, 10, 0)
MIN_HOMEASSISTANT = (2024, 12, 0)


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def test_manifest_pymodbus_floor_supports_device_id():
    manifest = json.loads(
        (ROOT / "custom_components" / "growatt_modbus" / "manifest.json").read_text()
    )
    (requirement,) = [r for r in manifest["requirements"] if r.startswith("pymodbus")]
    match = re.fullmatch(r"pymodbus>=([\d.]+)", requirement)
    assert match, f"expected a pymodbus>= floor, got {requirement!r}"
    assert _version(match.group(1)) >= MIN_PYMODBUS


def test_hacs_homeassistant_floor_supports_used_apis():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert _version(hacs["homeassistant"]) >= MIN_HOMEASSISTANT
