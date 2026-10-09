"""The version number must not drift between the places that carry it."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
    pkgbuild = (PROJECT_ROOT / "packaging" / "arch" / "PKGBUILD").read_text(encoding="utf-8")
    found = re.search(r"^pkgver=(.+)$", pkgbuild, re.MULTILINE)
    assert found is not None
    assert found.group(1) == hamrlog.__version__


def test_the_windows_installer_has_no_version_of_its_own():
    """semantic-release cannot bump it, so CI must always pass it in."""
    script = (PROJECT_ROOT / "packaging" / "windows" / "hamrlog.iss").read_text(
        encoding="utf-8-sig"
    )
    assert re.search(r'#define HamrlogVersion "', script) is None
    assert "#error" in script


def test_the_windows_bundle_carries_translations_and_catalog():
    """Both are read through importlib.resources, which PyInstaller only
    serves for files it was told to bundle."""
    spec = (PROJECT_ROOT / "packaging" / "pyinstaller" / "hamrlog.spec").read_text(encoding="utf-8")
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
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    app_id = re.search(r"^AppId=\{\{([0-9A-F-]+)\}$", script, re.MULTILINE)
    assert app_id is not None
    assert f"Uninstall\\{{{app_id.group(1)}}}_is1'" in script
    assert f"{{{app_id.group(1)}}}_is1" in workflow


def test_the_release_ships_what_the_linux_installer_downloads():
    """install.sh --upgrade looks for this tarball name in SHA256SUMS.txt."""
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "packaging" / "linux" / "install.sh").read_text(encoding="utf-8")
    assert 'PLATFORM="linux-x86_64"' in installer
    assert 'bundle="hamrlog-${{ needs.meta.outputs.version }}-linux-x86_64"' in workflow
    assert 'tar -czf "artifacts/$bundle.tar.gz"' in workflow
    assert "artifacts/hamrlog-install.sh" in workflow
    assert "releases/latest/download/hamrlog-install.sh" in installer


def semantic_release_config() -> dict:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["semantic_release"]


def test_semantic_release_bumps_every_version_number():
    """The release commit has to move all of them, or the version tests above
    fail on the next push."""
    variables = semantic_release_config()["version_variables"]
    assert "src/hamrlog/__init__.py:__version__" in variables
    # nf: PKGBUILD writes the number unquoted.
    assert "packaging/arch/PKGBUILD:pkgver:nf" in variables


def test_semantic_release_tags_what_the_release_workflow_expects():
    config = semantic_release_config()
    assert config["tag_format"] == "v{version}"
    assert config["branches"]["main"]["match"] == "main"


@pytest.mark.skipif(sys.platform == "win32" or shutil.which("sed") is None,
                    reason="semantic-release runs the build command on Linux")
def test_the_release_dates_the_unreleased_changelog_section(tmp_path):
    """build_command turns "Sin publicar" into the new version, and the
    changed changelog goes into the release commit."""
    config = semantic_release_config()
    assert "CHANGELOG.md" in config["assets"]
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Cambios\n\n## Sin publicar\n\n- Algo nuevo.\n\n## v0.2.0\n")

    subprocess.run(config["build_command"], shell=True, cwd=tmp_path, check=True,
                   env={**os.environ, "NEW_VERSION": "0.3.0"})

    expected = "# Cambios\n\n## v0.3.0\n\n- Algo nuevo.\n\n## v0.2.0\n"
    assert changelog.read_text(encoding="utf-8") == expected


def test_the_changelog_keeps_the_heading_the_release_looks_for():
    """New entries go under "## Sin publicar"; right after a release the top
    section is the version just published."""
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## (.+)$", changelog, re.MULTILINE)
    assert first is not None
    assert first.group(1) == "Sin publicar" or re.fullmatch(r"v\d+\.\d+\.\d+", first.group(1))


def test_ci_hands_the_new_tag_to_the_release_workflow():
    """A tag pushed with GITHUB_TOKEN triggers nothing, so CI calls it."""
    ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/release.yml" in ci
    assert "tag: ${{ needs.release.outputs.tag }}" in ci
    assert "workflow_call:" in release
    assert (PROJECT_ROOT / "packaging" / "release-notes.md").exists()


def test_the_windows_installer_reopens_hamrlog_after_a_self_upgrade():
    """hamrlog closes to let the setup replace it, passing /RELAUNCH so the
    setup opens it again; updater.py and the script must agree on it."""
    script = (PROJECT_ROOT / "packaging" / "windows" / "hamrlog.iss").read_text(
        encoding="utf-8-sig"
    )
    updater = (PROJECT_ROOT / "src" / "hamrlog" / "updater.py").read_text(encoding="utf-8")
    assert "Check: WantsRelaunch" in script
    assert "'/RELAUNCH'" in script
    assert '"/RELAUNCH"' in updater
