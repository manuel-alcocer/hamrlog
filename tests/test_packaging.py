"""The version number must not drift between the places that carry it."""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

import hamrlog

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_takes_the_version_from_the_package():
    """One source of truth, so a release cannot ship mismatched numbers."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    assert "version" not in data["project"]
    assert data["project"]["dynamic"] == ["version"]
    assert data["tool"]["hatch"]["version"]["path"] == "src/hamrlog/__init__.py"


def test_the_arch_package_matches_the_version():
    """makepkg reads its own number, so it has to be bumped with the rest."""
    pkgbuild = (PROJECT_ROOT / "packaging" / "arch" / "PKGBUILD").read_text()
    found = re.search(r"^pkgver=(.+)$", pkgbuild, re.MULTILINE)
    assert found is not None
    assert found.group(1) == hamrlog.__version__


def test_the_windows_installer_default_matches_the_version():
    """CI passes the real version in, but the default should not go stale."""
    script = (PROJECT_ROOT / "packaging" / "windows" / "hamrlog.iss").read_text()
    found = re.search(r'#define HamrlogVersion "(.+)"', script)
    assert found is not None
    assert found.group(1) == hamrlog.__version__
