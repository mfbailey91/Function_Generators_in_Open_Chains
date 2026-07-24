"""Smoke tests for package metadata."""

from inequality_mechanisms import __version__


def test_package_version() -> None:
    """Package exposes the expected release version."""
    assert __version__ == "0.1.0"
