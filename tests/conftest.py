"""Shared fixtures.

Every test gets a fresh SQLite file so module level engine state from one test
can never leak into the next.
"""

from __future__ import annotations

import pytest

from hamrlog.core.services import OperatorService, StationService
from hamrlog.core.state import SessionState
from hamrlog.db import session as db_session


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    """Point the application at a throwaway database.

    The URL goes through the environment rather than straight into
    ``init_engine`` so that code which re-initialises the engine on its own
    (the TUI does, on mount) resolves to the same file.
    """
    url = f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}"
    monkeypatch.setenv("HAMRLOG_HOME", str(tmp_path))
    monkeypatch.setenv("HAMRLOG_DATABASE_URL", url)
    db_session.dispose()
    db_session.init_engine(url)
    yield
    db_session.dispose()


@pytest.fixture
def operator():
    return OperatorService.create("EA7WM", "Manuel", "IM76", "Sevilla")


@pytest.fixture
def station():
    return StationService.create("HF-Casa", rig="IC-7300", antenna="Dipolo", power_w=100)


@pytest.fixture
def state(operator, station) -> SessionState:
    """A configured session: 40 m, SSB, with operator and rig selected."""
    value = SessionState(operator_id=operator.id, station_id=station.id)
    value.set_band("40m")
    value.set_mode("SSB")
    return value
