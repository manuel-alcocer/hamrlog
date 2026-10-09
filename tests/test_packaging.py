"""The version number must not drift between the places that carry it."""

from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

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


def test_the_windows_bundle_carries_translations_and_catalog():
    """Both are read through importlib.resources, which PyInstaller only
    serves for files it was told to bundle."""
    spec = (PROJECT_ROOT / "packaging" / "pyinstaller" / "hamrlog.spec").read_text()
    assert '"hamrlog/locales"' in spec
    assert '"hamrlog/data/preseed"' in spec


# Inno Setup's own messages, defined by its language files.
INNO_BUILTIN_MESSAGES = {"CreateDesktopIcon", "LaunchProgram", "UninstallProgram"}


def test_every_installer_message_exists_in_both_languages():
    """A message missing in one language shows up as an empty label."""
    script = (PROJECT_ROOT / "packaging" / "windows" / "hamrlog.iss").read_text(
        encoding="utf-8-sig"
    )
    used = set(re.findall(r"\{cm:(\w+)", script))
    used |= set(re.findall(r"CustomMessage\('(\w+)'\)", script))
    used -= INNO_BUILTIN_MESSAGES
    for language in ("english", "spanish"):
        defined = set(re.findall(rf"^{language}\.(\w+)=", script, re.MULTILINE))
        assert used <= defined, f"{language} lacks {sorted(used - defined)}"


def test_the_windows_installer_is_utf8_with_a_bom():
    """Without the BOM Inno Setup may read the accents as ANSI."""
    raw = (PROJECT_ROOT / "packaging" / "windows" / "hamrlog.iss").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")


def test_the_upgrade_check_and_the_release_tests_use_the_app_id():
    """Upgrades find the installed copy through AppId, and the installer's
    own code and the release workflow look it up by the same GUID."""
    script = (PROJECT_ROOT / "packaging" / "windows" / "hamrlog.iss").read_text(
        encoding="utf-8-sig"
    )
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text()
    app_id = re.search(r"^AppId=\{\{([0-9A-F-]+)\}$", script, re.MULTILINE)
    assert app_id is not None
    assert f"Uninstall\\{{{app_id.group(1)}}}_is1'" in script
    assert f"{{{app_id.group(1)}}}_is1" in workflow


def test_the_release_ships_what_the_linux_installer_downloads():
    """install.sh --upgrade looks for this tarball name in SHA256SUMS.txt."""
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text()
    installer = (PROJECT_ROOT / "packaging" / "linux" / "install.sh").read_text()
    assert 'PLATFORM="linux-x86_64"' in installer
    assert 'bundle="hamrlog-${{ steps.version.outputs.value }}-linux-x86_64"' in workflow
    assert 'tar -czf "artifacts/$bundle.tar.gz"' in workflow
    assert "artifacts/hamrlog-install.sh" in workflow
    assert "releases/latest/download/hamrlog-install.sh" in installer
