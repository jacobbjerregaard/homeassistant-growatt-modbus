#!/usr/bin/env bash
# Combined test coverage for the integration.
#
# The two test suites run in different interpreters (pure-logic on any Python,
# the Home Assistant suite on 3.13), so coverage is collected separately and
# merged. Override the interpreters with VENV / VENV_HA if your paths differ.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv/bin/python}"
VENV_HA="${VENV_HA:-.venv-ha/bin/python}"
SRC="custom_components/growatt_modbus"

rm -f .coverage .coverage.pure .coverage.int
"$VENV"    -m coverage run --source="$SRC" --data-file=.coverage.pure -m pytest tests --ignore=tests/integration -q
"$VENV_HA" -m coverage run --source="$SRC" --data-file=.coverage.int  -m pytest tests/integration -q
"$VENV_HA" -m coverage combine .coverage.pure .coverage.int
"$VENV_HA" -m coverage report --show-missing
