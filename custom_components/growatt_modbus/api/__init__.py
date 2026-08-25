"""Growatt Modbus protocol layer (no Home Assistant imports).

The modules here speak Modbus and decode the register maps; they are kept
free of Home Assistant so they can be unit-tested standalone (see
tests/conftest.py, which imports this package as ``growatt_api``).
"""
