"""Service layer: logging rules, duplicates, profiles and statistics."""

from __future__ import annotations

import datetime as dt

import pytest

from hamrlog.core.entry import parse
from hamrlog.core.services import (
    ProfileService,
    QsoService,
    ServiceError,
    SettingsService,
    StationService,
)
from hamrlog.core.state import SessionState


def log_line(line: str, state: SessionState, **kwargs):
    parsed = parse(line, field_order=state.field_order, mode_name=state.mode)
    return QsoService.log(parsed.fields, state, digital=parsed.digital, **kwargs)


def test_logging_uses_the_session_defaults(state):
    row = log_line("ea4abc,juan,59,57", state)
    assert row.call == "EA4ABC"
    assert row.band == "40m"
    assert row.freq_hz == 7_130_000
    assert row.mode == "SSB"
    assert row.country == "España"
    assert row.entry_mode == "AUTO"
    assert row.station_name == "HF-Casa"


def test_logging_without_an_operator_is_rejected():
    state = SessionState()
    state.set_band("40m")
    with pytest.raises(ServiceError, match="operador"):
        QsoService.log({"call": "EA4ABC"}, state)


def test_manual_timestamp_marks_the_contact_as_manual(state):
    row = log_line("ea3mno,laia", state, qso_utc=dt.datetime(2026, 1, 15, 12, 30))
    assert row.entry_mode == "MANUAL"
    assert row.qso_utc == dt.datetime(2026, 1, 15, 12, 30)


def test_automatic_contact_only_allows_the_callsign_to_change(state):
    row = log_line("ea4abc,juan", state)
    assert QsoService.editable_fields(row.id) == frozenset({"call"})

    updated = QsoService.update(row.id, {"call": "ea4abc/p"})
    assert updated.call == "EA4ABC/P"

    for forbidden in ({"name": "Otro"}, {"qth": "X"}, {"qso_utc": dt.datetime(2020, 1, 1)}):
        with pytest.raises(ServiceError, match="automático"):
            QsoService.update(row.id, forbidden)


def test_manual_contact_allows_every_field(state):
    row = log_line("ea3mno,laia", state, qso_utc=dt.datetime(2026, 1, 15, 12, 30))
    updated = QsoService.update(
        row.id,
        {
            "name": "Laia M.",
            "qth": "Barcelona",
            "freq_hz": 14_250_000,
            "qso_utc": dt.datetime(2026, 1, 15, 13, 0),
        },
    )
    assert updated.name == "Laia M."
    assert updated.qth == "Barcelona"
    # Changing the frequency must move the band with it.
    assert updated.band == "20m"
    assert updated.qso_utc == dt.datetime(2026, 1, 15, 13, 0)


def test_changing_the_callsign_recomputes_the_country(state):
    row = log_line("ea4abc", state, qso_utc=dt.datetime(2026, 1, 15, 12, 30))
    assert row.country == "España"
    assert QsoService.update(row.id, {"call": "DL2JKL"}).country == "Alemania"


def test_duplicates_are_scoped_to_band_and_mode(state):
    log_line("ea4abc,juan", state)
    assert len(QsoService.find_duplicates("EA4ABC", "40m", "SSB")) == 1
    assert QsoService.find_duplicates("EA4ABC", "20m", "SSB") == []
    assert QsoService.find_duplicates("EA4ABC", "40m", "CW") == []
    # Portable operation is the same station.
    assert len(QsoService.find_duplicates("EA4ABC/P", "40m", "SSB")) == 1


def test_history_is_returned_oldest_first(state):
    for index, call in enumerate(["ea1aaa", "ea2bbb", "ea3ccc"]):
        log_line(call, state, qso_utc=dt.datetime(2026, 1, 15, 12, index))
    assert [row.call for row in QsoService.recent()] == ["EA1AAA", "EA2BBB", "EA3CCC"]


def test_search_matches_several_fields(state):
    log_line("ea4abc,juan,59,57,Madrid,por la tarde", state)
    assert len(QsoService.search("juan")) == 1
    assert len(QsoService.search("madrid")) == 1
    assert len(QsoService.search("tarde")) == 1
    assert len(QsoService.search("nada de eso")) == 0


def test_delete_removes_the_contact(state):
    row = log_line("ea4abc", state)
    QsoService.delete(row.id)
    assert QsoService.get(row.id) is None
    with pytest.raises(ServiceError):
        QsoService.delete(row.id)


def test_stats_counts_by_band_and_mode(state):
    log_line("ea1aaa", state)
    state.set_band("20m")
    log_line("ea2bbb", state)
    state.set_mode("CW")
    log_line("dl2jkl", state)

    stats = QsoService.stats()
    assert stats.total == 3
    assert stats.today == 3
    assert stats.unique_calls == 3
    assert stats.countries == 2
    assert stats.by_band == {"40m": 1, "20m": 2}
    assert stats.by_mode == {"SSB": 2, "CW": 1}


def test_profiles_round_trip_the_session_state(state):
    state.set_mode("DMR")
    state.digital_data = {"talkgroup": "21466", "network": "Brandmeister"}
    ProfileService.save_from_state("DMR-Hotspot", state)

    restored = SessionState()
    ProfileService.apply_to_state(ProfileService.list_all()[0].id, restored)
    assert restored.profile_name == "DMR-Hotspot"
    assert restored.band == state.band
    assert restored.freq_hz == state.freq_hz
    assert restored.mode == "DMR"
    assert restored.digital_data == {"talkgroup": "21466", "network": "Brandmeister"}
    assert restored.station_id == state.station_id


def test_saving_a_profile_twice_needs_overwrite(state):
    ProfileService.save_from_state("perfil", state)
    with pytest.raises(ServiceError, match="Ya existe"):
        ProfileService.save_from_state("perfil", state)
    state.set_band("20m")
    updated = ProfileService.save_from_state("perfil", state, overwrite=True)
    assert updated.band == "20m"


def test_only_one_profile_is_the_default(state):
    first = ProfileService.save_from_state("uno", state)
    second = ProfileService.save_from_state("dos", state)
    ProfileService.set_default(first.id)
    ProfileService.set_default(second.id)
    assert ProfileService.get_default().id == second.id


def test_deleting_a_station_keeps_its_contacts(state):
    row = log_line("ea4abc", state)
    StationService.delete(state.station_id)
    assert QsoService.get(row.id) is not None
    assert QsoService.get(row.id).station_name == ""


def test_session_state_survives_a_restart(state):
    state.set_mode("C4FM")
    state.digital_data = {"room": "ESPANA"}
    SettingsService.save_state(state)

    restored = SettingsService.load_state()
    assert restored.mode == "C4FM"
    assert restored.digital_data == {"room": "ESPANA"}
    assert restored.operator_id == state.operator_id
    assert restored.field_order == state.field_order


def test_changing_mode_drops_stale_digital_values(state):
    state.set_mode("DMR")
    state.digital_data = {"talkgroup": "214"}
    state.set_mode("SSB")
    assert state.digital_data == {}
