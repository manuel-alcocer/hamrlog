"""The Linux installer: install, upgrade, downgrade guard and uninstall.

Runs packaging/linux/install.sh against a fake hamrlog executable, so the
tests need neither PyInstaller nor the network: releases are served from a
local folder through a file:// URL.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="the Linux installer is a bash script",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = PROJECT_ROOT / "packaging" / "linux" / "install.sh"
PLATFORM = "linux-x86_64"


def fake_hamrlog(folder: Path, version: str) -> Path:
    """An executable that answers --version and build-demo like hamrlog."""
    folder.mkdir(parents=True, exist_ok=True)
    binary = folder / "hamrlog"
    binary.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "hamrlog {version}"; exit 0; fi\n'
        'if [ "$1" = "build-demo" ]; then mkdir -p "$XDG_DATA_HOME/hamrlog/demo"; exit 0; fi\n'
        "exit 0\n"
    )
    binary.chmod(0o755)
    return binary


def release_bundle(folder: Path, version: str) -> Path:
    """The tarball layout the release workflow publishes: the installer
    next to the executable."""
    bundle = folder / f"hamrlog-{version}-{PLATFORM}"
    fake_hamrlog(bundle, version)
    shutil.copy(INSTALLER, bundle / "install.sh")
    return bundle


def publish_release(releases: Path, version: str, *, latest: bool = True,
                    corrupt: bool = False, with_tarball: bool = True) -> None:
    """Lays a release out as GitHub serves it, under releases/."""
    staging = releases.parent / f"staging-{version}"
    bundle = release_bundle(staging, version)
    name = f"hamrlog-{version}-{PLATFORM}.tar.gz"
    tarball = staging / name
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(bundle, arcname=bundle.name)
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    if corrupt:
        digest = "0" * 64
    sums = f"{'1' * 64}  hamrlog-{version}-setup.exe\n{digest}  {name}\n"

    targets = [releases / "download" / f"v{version}"]
    if latest:
        targets.append(releases / "latest" / "download")
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        (target / "SHA256SUMS.txt").write_text(sums)
        if with_tarball:
            shutil.copy(tarball, target / name)


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {
        "HOME": str(home),
        "PATH": os.environ["PATH"],
        "LANG": "C",
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "HAMRLOG_RELEASES_URL": (tmp_path / "releases").as_uri(),
    }


@pytest.fixture
def prefix(tmp_path):
    return tmp_path / "prefix"


def run(script: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(script), *args],
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def installed_version(prefix: Path) -> str | None:
    version_file = prefix / "lib" / "hamrlog" / "version"
    return version_file.read_text().strip() if version_file.exists() else None


def test_installs_the_executable_next_to_the_script(tmp_path, env, prefix):
    bundle = release_bundle(tmp_path / "bundle", "0.2.0")

    result = run(bundle / "install.sh", env, "--prefix", str(prefix))

    assert result.returncode == 0, result.stderr
    binary = prefix / "bin" / "hamrlog"
    assert os.access(binary, os.X_OK)
    assert subprocess.run([binary, "--version"], capture_output=True, text=True).stdout.strip() \
        == "hamrlog 0.2.0"
    assert installed_version(prefix) == "0.2.0"
    desktop = (prefix / "share" / "applications" / "hamrlog.desktop").read_text()
    assert f'Exec="{binary}"' in desktop
    assert "Terminal=true" in desktop
    # The demo database is prepared at install time.
    assert (Path(env["XDG_DATA_HOME"]) / "hamrlog" / "demo").is_dir()


def test_the_same_version_again_changes_nothing(tmp_path, env, prefix):
    bundle = release_bundle(tmp_path / "bundle", "0.2.0")
    run(bundle / "install.sh", env, "--prefix", str(prefix))

    result = run(bundle / "install.sh", env, "--prefix", str(prefix))

    assert result.returncode == 0
    assert "already installed" in result.stdout


def test_a_newer_bundle_upgrades(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "old", "0.2.0") / "install.sh", env, "--prefix", str(prefix))

    result = run(release_bundle(tmp_path / "new", "0.10.0") / "install.sh", env,
                 "--prefix", str(prefix))

    assert result.returncode == 0, result.stderr
    assert "Upgrading hamrlog from 0.2.0 to 0.10.0" in result.stdout
    assert installed_version(prefix) == "0.10.0"


def test_an_older_bundle_needs_force(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "new", "0.3.0") / "install.sh", env, "--prefix", str(prefix))
    old = release_bundle(tmp_path / "old", "0.2.0") / "install.sh"

    refused = run(old, env, "--prefix", str(prefix))
    assert refused.returncode != 0
    assert "--force" in refused.stderr
    assert installed_version(prefix) == "0.3.0"

    forced = run(old, env, "--prefix", str(prefix), "--force")
    assert forced.returncode == 0, forced.stderr
    assert installed_version(prefix) == "0.2.0"


def test_does_not_overwrite_a_hamrlog_installed_by_other_means(tmp_path, env, prefix):
    foreign = prefix / "bin" / "hamrlog"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("#!/bin/sh\necho pipx\n")
    bundle = release_bundle(tmp_path / "bundle", "0.2.0")

    refused = run(bundle / "install.sh", env, "--prefix", str(prefix))
    assert refused.returncode != 0
    assert "not installed by this script" in refused.stderr
    assert "pipx" in foreign.read_text()

    assert run(bundle / "install.sh", env, "--prefix", str(prefix), "--force").returncode == 0
    assert installed_version(prefix) == "0.2.0"


def test_uninstall_removes_the_program_and_keeps_the_log(tmp_path, env, prefix):
    bundle = release_bundle(tmp_path / "bundle", "0.2.0")
    run(bundle / "install.sh", env, "--prefix", str(prefix))
    log = Path(env["XDG_DATA_HOME"]) / "hamrlog" / "hamrlog.sqlite3"
    log.write_text("QSOs")

    result = run(INSTALLER, env, "--prefix", str(prefix), "--uninstall")

    assert result.returncode == 0, result.stderr
    assert not (prefix / "bin" / "hamrlog").exists()
    assert not (prefix / "share" / "applications" / "hamrlog.desktop").exists()
    assert not (prefix / "lib" / "hamrlog").exists()
    assert log.read_text() == "QSOs"


def test_purge_deletes_the_log_and_settings_too(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "bundle", "0.2.0") / "install.sh", env, "--prefix", str(prefix))
    config = Path(env["XDG_CONFIG_HOME"]) / "hamrlog"
    config.mkdir(parents=True)

    result = run(INSTALLER, env, "--prefix", str(prefix), "--purge", "--yes")

    assert result.returncode == 0, result.stderr
    assert not (Path(env["XDG_DATA_HOME"]) / "hamrlog").exists()
    assert not config.exists()


@pytest.mark.skipif(shutil.which("setsid") is None, reason="setsid drops the terminal")
def test_purge_without_a_terminal_asks_for_yes(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "bundle", "0.2.0") / "install.sh", env, "--prefix", str(prefix))
    data = Path(env["XDG_DATA_HOME"]) / "hamrlog"

    # setsid leaves the installer without a terminal to read the answer from.
    result = subprocess.run(
        ["setsid", "bash", str(INSTALLER), "--prefix", str(prefix), "--purge"],
        env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60,
    )

    assert result.returncode != 0
    assert "--yes" in result.stderr
    assert data.exists()


def test_uninstall_when_nothing_is_installed_fails(env, prefix):
    result = run(INSTALLER, env, "--prefix", str(prefix), "--uninstall")

    assert result.returncode != 0
    assert "not installed" in result.stderr


def test_status_reports_the_installed_version(tmp_path, env, prefix):
    assert run(INSTALLER, env, "--prefix", str(prefix), "--status").returncode != 0
    run(release_bundle(tmp_path / "bundle", "0.2.0") / "install.sh", env, "--prefix", str(prefix))

    result = run(INSTALLER, env, "--prefix", str(prefix), "--status")

    assert result.returncode == 0
    assert "hamrlog 0.2.0" in result.stdout


def test_without_a_bundle_it_downloads_the_latest_release(tmp_path, env, prefix):
    publish_release(tmp_path / "releases", "0.3.0")

    result = run(INSTALLER, env, "--prefix", str(prefix))

    assert result.returncode == 0, result.stderr
    assert installed_version(prefix) == "0.3.0"


def test_upgrade_downloads_the_latest_release(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "bundle", "0.2.0") / "install.sh", env, "--prefix", str(prefix))
    publish_release(tmp_path / "releases", "0.3.0")

    result = run(INSTALLER, env, "--prefix", str(prefix), "--upgrade")

    assert result.returncode == 0, result.stderr
    assert "Upgrading hamrlog from 0.2.0 to 0.3.0" in result.stdout
    assert installed_version(prefix) == "0.3.0"


def test_upgrade_when_up_to_date_downloads_only_the_sums(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "bundle", "0.3.0") / "install.sh", env, "--prefix", str(prefix))
    publish_release(tmp_path / "releases", "0.3.0", with_tarball=False)

    result = run(INSTALLER, env, "--prefix", str(prefix), "--upgrade")

    assert result.returncode == 0, result.stderr
    assert "already the latest version" in result.stdout


def test_upgrade_needs_an_installed_hamrlog(tmp_path, env, prefix):
    publish_release(tmp_path / "releases", "0.3.0")

    result = run(INSTALLER, env, "--prefix", str(prefix), "--upgrade")

    assert result.returncode != 0
    assert installed_version(prefix) is None


def test_a_download_that_fails_its_checksum_is_not_installed(tmp_path, env, prefix):
    run(release_bundle(tmp_path / "bundle", "0.2.0") / "install.sh", env, "--prefix", str(prefix))
    publish_release(tmp_path / "releases", "0.3.0", corrupt=True)

    result = run(INSTALLER, env, "--prefix", str(prefix), "--upgrade")

    assert result.returncode != 0
    assert "SHA-256" in result.stderr
    assert installed_version(prefix) == "0.2.0"


def test_a_pinned_version_is_downloaded_instead_of_the_latest(tmp_path, env, prefix):
    releases = tmp_path / "releases"
    publish_release(releases, "0.2.0", latest=False)
    publish_release(releases, "0.3.0")

    result = run(INSTALLER, env, "--prefix", str(prefix), "--version", "v0.2.0")

    assert result.returncode == 0, result.stderr
    assert installed_version(prefix) == "0.2.0"


def test_messages_follow_a_spanish_locale(tmp_path, env, prefix):
    bundle = release_bundle(tmp_path / "bundle", "0.2.0")

    result = run(bundle / "install.sh", {**env, "LANG": "es_ES.UTF-8"}, "--prefix", str(prefix))

    assert "Instalando hamrlog 0.2.0" in result.stdout
