"""Updates on start: finding the latest release, asking, installing it."""

from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from hamrlog import __version__, appconfig, updater
from hamrlog.updater import Installation, Release

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LINUX_INSTALLER = PROJECT_ROOT / "packaging" / "linux" / "install.sh"
NEW = "99.0.0"
NOW = dt.datetime(2026, 10, 9, 12, 0)

linux_only = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="the Linux installer is a bash script",
)


def fake_hamrlog(folder: Path, version: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    binary = folder / "hamrlog"
    binary.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "hamrlog {version}"; exit 0; fi\n'
        "exit 0\n"
    )
    binary.chmod(0o755)
    return binary


def publish(releases: Path, version: str = NEW, *, corrupt: bool = False) -> None:
    """A release laid out as GitHub serves it, with its Linux tarball."""
    staging = releases.parent / "staging"
    bundle = staging / f"hamrlog-{version}-linux-x86_64"
    fake_hamrlog(bundle, version)
    shutil.copy(LINUX_INSTALLER, bundle / "install.sh")
    name = f"hamrlog-{version}-linux-x86_64.tar.gz"
    tarball = staging / name
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(bundle, arcname=bundle.name)
    digest = "0" * 64 if corrupt else hashlib.sha256(tarball.read_bytes()).hexdigest()
    sums = f"{'1' * 64}  hamrlog-{version}-setup.exe\n{digest}  {name}\n"
    for folder in (releases / "latest" / "download", releases / "download" / f"v{version}"):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SHA256SUMS.txt").write_text(sums)
        shutil.copy(tarball, folder / name)


@pytest.fixture
def releases(tmp_path, monkeypatch):
    folder = tmp_path / "releases"
    monkeypatch.setenv(updater.RELEASES_URL_ENV, folder.as_uri())
    return folder


def answers(*replies: str):
    """An ask() that answers in turn and records the questions."""
    asked: list[str] = []
    pending = list(replies)

    def ask(question: str) -> str:
        asked.append(question)
        return pending.pop(0)

    ask.asked = asked
    return ask


# --------------------------------------------------------------------------- #
# The latest release
# --------------------------------------------------------------------------- #

def test_versions_compare_by_number():
    assert updater.is_newer("0.10.0", "0.9.3")
    assert updater.is_newer("1.0.0", "0.99.0")
    assert not updater.is_newer("0.3.1", "0.3.1")
    assert not updater.is_newer("0.3.0", "0.3.1")


def test_the_latest_release_comes_from_its_sums(releases):
    publish(releases)

    release = updater.latest_release()

    assert release.version == NEW
    assert f"hamrlog-{NEW}-linux-x86_64.tar.gz" in release.sums


def test_no_network_means_no_release(releases):
    assert updater.latest_release() is None


def test_the_network_is_asked_once_a_day():
    calls = []

    def fetch():
        calls.append(1)
        return Release(NEW, {})

    assert updater.known_release(NOW, fetch).version == NEW
    assert updater.known_release(NOW + dt.timedelta(hours=23), fetch).version == NEW
    assert len(calls) == 1
    updater.known_release(NOW + dt.timedelta(hours=25), fetch)
    assert len(calls) == 2


# --------------------------------------------------------------------------- #
# The question
# --------------------------------------------------------------------------- #

WINDOWS = Installation("windows", Path("x"))


def offer(ask, *, fetch=lambda: Release(NEW, {}), found=WINDOWS, said=None):
    return updater.offer_update(
        [], ask=ask, say=(said.append if said is not None else lambda _text: None),
        fetch=fetch, now=NOW, found=found,
    )


def test_nothing_is_asked_when_this_is_the_latest():
    ask = answers()

    assert offer(ask, fetch=lambda: Release(__version__, {})) is None
    assert ask.asked == []


def test_nothing_is_asked_without_network():
    ask = answers()

    assert offer(ask, fetch=lambda: None) is None
    assert ask.asked == []


def test_no_keeps_this_version_and_asks_again_next_time():
    ask = answers("n", "n")

    assert offer(ask) is None
    assert offer(ask) is None
    assert len(ask.asked) == 2
    assert NEW in ask.asked[0]


def test_omit_skips_that_version_for_good():
    ask = answers("o")

    assert offer(ask) is None
    assert offer(ask) is None
    assert len(ask.asked) == 1


def test_a_hamrlog_installed_by_other_means_is_only_told(capsys):
    said: list[str] = []
    ask = answers()

    assert offer(ask, found=Installation("other"), said=said) is None
    assert ask.asked == []
    assert any(NEW in line for line in said)


def test_a_failed_download_opens_the_current_version(releases):
    said: list[str] = []
    release = Release(NEW, {f"hamrlog-{NEW}-setup.exe": "0" * 64})

    result = offer(answers("s"), fetch=lambda: release, said=said)

    assert result is None
    assert any(__version__ in line for line in said)


# --------------------------------------------------------------------------- #
# Installing it
# --------------------------------------------------------------------------- #

@linux_only
def test_linux_downloads_installs_and_opens_the_new_version(tmp_path, releases, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LANG", "C")
    prefix = tmp_path / "prefix"
    old = fake_hamrlog(tmp_path / "old", "0.0.1")
    shutil.copy(LINUX_INSTALLER, old.parent / "install.sh")
    subprocess.run(["bash", str(old.parent / "install.sh"), "--prefix", str(prefix)],
                   check=True, capture_output=True)
    publish(releases)
    ran = []
    real_call = subprocess.call
    monkeypatch.setattr(updater.subprocess, "call",
                        lambda command, **kwargs: ran.append(command) or real_call(command))

    result = updater.offer_update(
        ["--lang", "es"], ask=answers("s"), say=lambda _text: None,
        fetch=updater.latest_release, now=NOW, found=Installation("linux", prefix),
    )

    assert result == 0
    assert (prefix / "lib" / "hamrlog" / "version").read_text().strip() == NEW
    assert ran == [[str(prefix / "bin" / "hamrlog"), "--lang", "es"]]


@linux_only
def test_linux_does_not_install_a_download_that_fails_its_sum(tmp_path, releases, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    publish(releases, corrupt=True)
    release = updater.latest_release()

    with pytest.raises(updater.UpdateError, match="SHA-256"):
        updater.install_linux(release, prefix)
    assert not (prefix / "bin" / "hamrlog").exists()


def test_windows_starts_the_setup_and_lets_hamrlog_close(tmp_path, monkeypatch):
    local = tmp_path / "AppData" / "Local"
    app_dir = local / "Programs" / "hamrlog"
    app_dir.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    setup = tmp_path / "setup.exe"
    setup.write_bytes(b"MZ")
    monkeypatch.setattr(updater, "download", lambda release, name, folder: setup)
    started = []
    monkeypatch.setattr(updater.subprocess, "Popen",
                        lambda command, **kwargs: started.append(command))

    result = offer(answers(""), found=Installation("windows", app_dir))

    assert result == 0
    assert started[0][0] == str(setup)
    assert {"/SILENT", "/RELAUNCH", "/CURRENTUSER"} <= set(started[0])


def test_a_machine_wide_windows_install_is_upgraded_machine_wide(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))

    arguments = updater.setup_arguments(tmp_path / "Program Files" / "hamrlog")

    assert "/ALLUSERS" in arguments


# --------------------------------------------------------------------------- #
# When to check
# --------------------------------------------------------------------------- #

def test_the_check_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.delenv(updater.DISABLE_ENV, raising=False)
    assert updater.should_check()

    monkeypatch.setenv(updater.DISABLE_ENV, "1")
    assert not updater.should_check()

    monkeypatch.delenv(updater.DISABLE_ENV)
    config = appconfig.load()
    config.check_updates = False
    appconfig.save(config)
    assert not updater.should_check()


def test_the_interface_asks_before_opening(monkeypatch):
    """main() hands over to the new version instead of opening the old one."""
    from hamrlog import cli

    monkeypatch.setattr(updater, "should_check", lambda: True)
    monkeypatch.setattr(updater, "offer_update", lambda argv: 7)

    assert cli.main([]) == 7


def test_other_commands_never_ask(monkeypatch, capsys):
    from hamrlog import cli

    monkeypatch.setattr(updater, "should_check", lambda: pytest.fail("asked"))

    assert cli.main(["info"]) == 0
