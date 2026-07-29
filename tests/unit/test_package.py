"""Smoke tests for the Python package."""

from importlib import import_module


def test_package_is_importable() -> None:
    package = import_module("trippilot")

    assert package.__name__ == "trippilot"
