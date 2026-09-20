"""End-to-end interface tests driven through Textual's pilot."""

from __future__ import annotations

from hamrlog.core.services import QsoService
from hamrlog.tui.app import HamrlogApp
from hamrlog.tui.screens.base import ConfirmScreen, SelectionScreen
from hamrlog.tui.screens.config import ConfigScreen
from hamrlog.tui.screens.contacts import ContactsScreen
from hamrlog.tui.screens.help import HelpScreen
from hamrlog.tui.screens.log import LogScreen
from hamrlog.tui.screens.profiles import ProfileScreen
from hamrlog.tui.screens.repeaters import RepeaterScreen
from hamrlog.tui.screens.selectors import FrequencyScreen
from hamrlog.tui.screens.stations import StationScreen
from hamrlog.tui.widgets.detail import DetailPanel
from hamrlog.tui.widgets.entry import EntryPanel
from hamrlog.tui.widgets.history import HistoryPanel


async def type_line(pilot, app, line: str) -> None:
    """Fill the entry form from a comma-separated shorthand and submit.

    The panel has one box per field now; the tests keep the compact notation
    and spread it over the boxes in the profile's order.
    """
    panel = app.query_one(EntryPanel)
    if line.startswith("/"):
        panel.set_first_value(line)
    else:
        parts = [part.strip() for part in line.split(",")]
        panel.set_values(
            {
                name: parts[index] if index < len(parts) else ""
                for index, name in enumerate(app.state.field_order)
            }
        )
    await pilot.press("enter")
    await pilot.pause()


def entry_value(app, field: str = "call") -> str:
    """Contents of one box of the entry form."""
    return app.query_one(EntryPanel).values().get(field, "")


async def wait_for(pilot, app, selector: str, tries: int = 60):
    """Wait until a widget exists, then return it.

    A screen is current as soon as it is pushed, but its children are mounted
    on a later refresh. A single pause is enough on a fast machine and not on
    a slow one, which made these tests flaky on the Windows runners.
    """
    for _ in range(tries):
        found = app.screen.query(selector)
        if found:
            return found.first()
        await pilot.pause()
    raise AssertionError(f"{selector} no apareció en {app.screen}")


async def test_logging_from_the_entry_line(operator, station):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea4abc,juan,59,57")
        await type_line(pilot, app, "dl2jkl,hans")

        assert app.query_one(HistoryPanel).qso_count == 2
        rows = QsoService.recent()
        assert [row.call for row in rows] == ["EA4ABC", "DL2JKL"]
        assert rows[0].band == app.state.band
        assert rows[0].entry_mode == "AUTO"


async def test_entry_line_is_cleared_after_logging(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea4abc,juan")
        assert entry_value(app) == ""


async def test_duplicate_warning_appears_while_typing(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea4abc,juan")
        app.query_one(EntryPanel).set_first_value("ea4abc")
        await pilot.pause()
        feedback = str(app.query_one("#entry-feedback").render())
        assert "DUPLICADO" in feedback


async def test_function_keys_open_their_screens(operator, station):
    app = HamrlogApp()
    expected = {
        "f1": LogScreen,
        "f2": SelectionScreen,
        "f3": FrequencyScreen,
        "f4": SelectionScreen,
        "f5": ConfigScreen,
        "f6": StationScreen,
        "f7": ProfileScreen,
        "f8": ContactsScreen,
        "f9": RepeaterScreen,
    }
    async with app.run_test(size=(120, 30)) as pilot:
        for key, screen_type in expected.items():
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, screen_type), key
            await pilot.press("escape")
            await pilot.pause()


async def test_band_command_changes_the_session(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "/banda 20m")
        assert app.state.band == "20m"
        assert app.state.freq_hz == 14_250_000

        await type_line(pilot, app, "/frec 14.074")
        assert app.state.freq_hz == 14_074_000
        assert app.state.band == "20m"

        await type_line(pilot, app, "/modo cw")
        assert app.state.mode == "CW"


async def test_unknown_command_reports_an_error(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "/noexiste")
        assert "desconocido" in str(app.query_one("#entry-feedback").render())


async def test_new_contacts_inherit_the_changed_configuration(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "/banda 20m")
        await type_line(pilot, app, "/modo cw")
        await type_line(pilot, app, "ea4abc")

        row = QsoService.recent()[-1]
        assert row.band == "20m"
        assert row.mode == "CW"
        # CW pre-fills 599 rather than the SSB 59.
        assert row.rst_sent == "599"


async def test_digital_mode_is_in_the_single_mode_selector(operator):
    """Analogue and digital modes share one list, reached with F4."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("f4")
        await pilot.pause()
        (await wait_for(pilot, app, "#filter")).value = "DMR"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # The mode is applied and its extra fields are requested.
        assert app.state.mode == "DMR"
        (await wait_for(pilot, app, "#field-talkgroup")).value = "21466"
        await pilot.press("ctrl+s")
        await pilot.pause()

        assert app.state.digital_data["talkgroup"] == "21466"
        await type_line(pilot, app, "ea5zz,pepe")
        assert QsoService.recent()[-1].digital_data["talkgroup"] == "21466"


async def test_profile_saves_and_reloads_the_configuration(operator, station):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "/banda 20m")
        await type_line(pilot, app, "/modo cw")

        await pilot.press("f7")
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        (await wait_for(pilot, app, "#field-name")).value = "CW-20m"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.state.profile_name == "CW-20m"

        await type_line(pilot, app, "/banda 40m")
        assert app.state.band == "40m"

        await type_line(pilot, app, "/perfil CW-20m")
        assert app.state.band == "20m"
        assert app.state.mode == "CW"


async def test_line_recall_walks_previous_entries(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa,uno")
        await type_line(pilot, app, "ea2bbb,dos")

        entry = app.query_one(EntryPanel)
        entry.focus_input()
        await pilot.press("ctrl+up")
        await pilot.pause()
        assert entry.values()["call"] == "ea2bbb"
        assert entry.values()["name"] == "dos"
        await pilot.press("ctrl+up")
        await pilot.pause()
        assert entry.values()["call"] == "ea1aaa"
        await pilot.press("ctrl+down")
        await pilot.pause()
        assert entry.values()["call"] == "ea2bbb"


async def test_log_screen_lists_the_qsos(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await type_line(pilot, app, "ea2bbb")

        await pilot.press("f1")
        await pilot.pause()
        assert isinstance(app.screen, LogScreen)
        assert app.screen.query_one("#log-table").row_count == 2

        (await wait_for(pilot, app, "#search")).value = "ea1"
        await pilot.pause()
        assert app.screen.query_one("#log-table").row_count == 1


async def test_first_run_asks_for_a_callsign(tmp_path):
    """With no operator in the database the application must not just fail."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.state.operator_id is None
        (await wait_for(pilot, app, "#field-callsign")).value = "EA7WM"
        await pilot.press("ctrl+s")
        await pilot.pause()

        assert app.state.operator_id is not None
        await type_line(pilot, app, "ea4abc")
        assert QsoService.stats().total == 1


async def test_ctrl_d_deletes_the_last_contact_from_the_entry_line(operator):
    """The common case: the callsign was just mistyped and Enter already hit."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa,uno")
        await type_line(pilot, app, "ea2bbb,dos")

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()

        assert [row.call for row in QsoService.recent()] == ["EA1AAA"]
        assert app.query_one(HistoryPanel).qso_count == 1


async def test_delete_key_on_the_history_removes_the_highlighted_contact(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        for call in ("ea1aaa", "ea2bbb", "ea3ccc"):
            await type_line(pilot, app, call)

        # Walk up to the oldest QSO with the arrow keys from the entry line.
        for _ in range(3):
            await pilot.press("up")
            await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()

        assert [row.call for row in QsoService.recent()] == ["EA2BBB", "EA3CCC"]


async def test_cancelling_the_confirmation_keeps_the_contact(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert QsoService.stats().total == 1


async def test_delete_command_is_available(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await type_line(pilot, app, "/borrar")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()
        assert QsoService.stats().total == 0


async def test_deleting_with_an_empty_log_is_harmless(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("ctrl+d")
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmScreen)
        assert "borrar" in str(app.query_one("#entry-feedback").render())


async def test_log_screen_opens_focused_on_the_table(operator):
    """Delete must work as soon as F1 opens, without moving the focus first."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await type_line(pilot, app, "ea2bbb")

        await pilot.press("f1")
        await pilot.pause()
        assert app.focused.id == "log-table"

        await pilot.press("delete")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()
        assert QsoService.stats().total == 1


async def test_log_screen_deletes_while_searching(operator):
    """Ctrl+D has priority, so it works even with the search box focused."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await type_line(pilot, app, "ea2bbb")

        await pilot.press("f1")
        await pilot.pause()
        app.screen.query_one("#search").focus()
        app.screen.query_one("#search").value = "ea2"
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()

        assert [row.call for row in QsoService.recent()] == ["EA1AAA"]


async def test_main_history_shows_date_and_time(operator):
    from hamrlog.tui.widgets.history import COLUMNS

    assert COLUMNS[0][0] == "FECHA HORA"

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        history = app.query_one(HistoryPanel)
        cell = history.get_cell_at((0, 0))
        stamp = QsoService.recent()[0].qso_utc.strftime("%Y-%m-%d %H:%M:%S")
        assert str(cell) == stamp


async def test_f9_opens_the_repeater_screen_and_direct_works(operator):
    from hamrlog.core.services import RepeaterService

    RepeaterService.create("ED7ZAE", name="Sevilla", output_hz=145_600_000, ctcss_tx="88.5")

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("f9")
        await pilot.pause()
        assert isinstance(app.screen, RepeaterScreen)

        # The list starts with DIRECTO, so the repeater is the second entry.
        app.screen.query_one("#repeaters").highlighted = 1
        await pilot.press("enter")
        await pilot.pause()

        assert app.state.via_repeater
        assert app.state.repeater_call == "ED7ZAE"
        assert app.state.freq_hz == 145_600_000
        assert app.state.freq_tx_hz == 145_000_000
        assert app.state.band == "2m"

        await type_line(pilot, app, "ea4abc,juan")
        row = QsoService.recent()[-1]
        assert row.repeater_call == "ED7ZAE"
        assert row.freq_tx_hz == 145_000_000

        await type_line(pilot, app, "/directo")
        assert not app.state.via_repeater
        await type_line(pilot, app, "ea5bbb")
        assert QsoService.recent()[-1].repeater_call == ""


async def test_repeater_command_takes_a_callsign(operator):
    from hamrlog.core.services import RepeaterService

    RepeaterService.create("ED7ZAF", output_hz=438_750_000, mode="DMR",
                           digital_data={"talkgroup": "214"})

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "/repetidor ED7ZAF")
        assert app.state.repeater_call == "ED7ZAF"
        assert app.state.mode == "DMR"
        assert app.state.digital_data["talkgroup"] == "214"

        await type_line(pilot, app, "/repetidor NOEXISTE")
        assert "No hay ningún repetidor" in str(app.query_one("#entry-feedback").render())


async def test_changing_band_leaves_the_repeater_in_the_interface(operator):
    from hamrlog.core.services import RepeaterService

    RepeaterService.create("ED7ZAE", output_hz=145_600_000)

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "/repetidor ED7ZAE")
        assert app.state.via_repeater
        await type_line(pilot, app, "/banda 20m")
        assert not app.state.via_repeater
        assert app.state.band == "20m"


async def test_import_export_is_reachable_from_config(operator):
    """F9 became the repeater, so the log transfer moved into the config."""
    from hamrlog.tui.screens.transfer import TransferScreen

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        sections = app.screen.query_one("#sections")
        ids = [sections.get_option_at_index(i).id for i in range(sections.option_count)]
        assert "transfer" in ids

        sections.highlighted = ids.index("transfer")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TransferScreen)

        # The command still works too.
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await type_line(pilot, app, "/exportar")
        assert isinstance(app.screen, TransferScreen)


async def test_log_and_contacts_are_separate_screens(operator):
    """F1 is what you worked, F8 is who they are: two screens, not two tabs."""
    from hamrlog.core.services import ContactService

    ContactService.create("EA7WM", first_name="Manuel", city="Sevilla", dmr_id=2147001)

    app = HamrlogApp()
    async with app.run_test(size=(140, 34)) as pilot:
        await type_line(pilot, app, "ea4abc,juan")

        await pilot.press("f1")
        await pilot.pause()
        assert isinstance(app.screen, LogScreen)
        assert app.screen.query_one("#log-table").row_count == 1

        # F8 from the log swaps to the address book without stacking screens.
        await pilot.press("f8")
        await pilot.pause()
        assert isinstance(app.screen, ContactsScreen)
        # EA7WM was already there; EA4ABC was added by the QSO just logged.
        assert app.screen.query_one("#book-table").row_count == 2

        # F1 goes back the same way.
        await pilot.press("f1")
        await pilot.pause()
        assert isinstance(app.screen, LogScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, LogScreen | ContactsScreen)


async def test_address_book_search_filters_the_table(operator):
    from hamrlog.core.services import ContactService

    for call, city in (("EA7WM", "Sevilla"), ("EA1DEF", "Bilbao"), ("DL2JKL", "Berlin")):
        ContactService.create(call, city=city)

    app = HamrlogApp()
    async with app.run_test(size=(140, 34)) as pilot:
        await pilot.press("f8")
        await pilot.pause()

        table = app.screen.query_one("#book-table")
        assert table.row_count == 3
        (await wait_for(pilot, app, "#book-search")).value = "bilbao"
        await pilot.pause()
        assert table.row_count == 1


async def test_typing_a_known_callsign_shows_who_it_is(operator):
    from hamrlog.core.services import ContactService

    ContactService.create(
        "EA7WM", first_name="Manuel", city="Sevilla", dmr_id=2147001
    )

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        app.query_one(EntryPanel).set_first_value("ea7wm")
        await pilot.pause()
        feedback = str(app.query_one("#entry-feedback").render())
        assert "Manuel" in feedback
        assert "Sevilla" in feedback
        assert "2147001" in feedback


async def test_logging_fills_the_name_from_the_address_book(operator):
    from hamrlog.core.services import ContactService

    ContactService.create("EA7WM", first_name="Manuel", city="Sevilla")

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea7wm")
        row = QsoService.recent()[-1]
        assert row.name == "Manuel"
        assert row.qth == "Sevilla"


async def test_address_book_import_from_the_interface(operator, tmp_path):
    from hamrlog.core.services import ContactService

    path = tmp_path / "users.csv"
    path.write_text(
        "RADIO_ID,CALLSIGN,FIRST_NAME,LAST_NAME,CITY,STATE,COUNTRY,REMARKS\n"
        "2147001,EA7WM,Manuel,Alcocer,Sevilla,Sevilla,Spain,\n"
        "2147122,EA7ABC,Jose,Garcia,Cordoba,Cordoba,Spain,\n",
        encoding="utf-8",
    )

    app = HamrlogApp()
    async with app.run_test(size=(140, 34)) as pilot:
        await pilot.press("f8")
        await pilot.pause()
        await pilot.press("ctrl+i")
        await pilot.pause()

        (await wait_for(pilot, app, "#field-path")).value = str(path)
        await pilot.press("ctrl+s")
        await pilot.pause()
        # The import runs in a worker thread.
        await pilot.pause(0.5)

        assert ContactService.count() == 2
        assert ContactService.lookup("EA7WM").first_name == "Manuel"


async def test_malformed_callsign_is_refused_in_the_interface(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "qwerty,juan")
        assert QsoService.stats().total == 0
        assert "número" in str(app.query_one("#entry-feedback").render())

        # The override marker gets it in anyway.
        await type_line(pilot, app, "bv100!,chen")
        assert QsoService.stats().total == 1
        assert QsoService.recent()[-1].call == "BV100"


async def test_bad_callsign_is_flagged_while_typing(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        app.query_one(EntryPanel).set_first_value("ea77")
        await pilot.pause()
        assert "indicativo" in str(app.query_one("#entry-feedback").render()).lower()


async def test_commands_open_the_right_screen(operator):
    app = HamrlogApp()
    async with app.run_test(size=(140, 34)) as pilot:
        for command in ("/agenda", "/contactos", "/listin"):
            await type_line(pilot, app, command)
            assert isinstance(app.screen, ContactsScreen), command
            await pilot.press("escape")
            await pilot.pause()

        for command in ("/registro", "/log", "/qso"):
            await type_line(pilot, app, command)
            assert isinstance(app.screen, LogScreen), command
            await pilot.press("escape")
            await pilot.pause()


async def test_help_is_on_ctrl_f1_and_f12(operator):
    """F1 belongs to the log now; help moved out of the top menu."""

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("ctrl+f1")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("f12")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()

        await type_line(pilot, app, "/ayuda")
        assert isinstance(app.screen, HelpScreen)


async def test_f10_walks_the_menu_with_the_cursor_keys(operator):
    """F10 turns the top bar into a Midnight Commander style menu."""
    from hamrlog.tui.widgets.menubar import SHORTCUTS, MenuBar

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        menu = app.query_one(MenuBar)
        assert menu.active_index is None

        await pilot.press("f10")
        await pilot.pause()
        assert menu.active_index == 0
        assert app.focused is menu

        await pilot.press("right")
        await pilot.pause()
        assert menu.active_index == 1
        await pilot.press("left")
        await pilot.press("left")
        await pilot.pause()
        # Wraps around to the last navigable entry.
        assert menu.active_index == len(SHORTCUTS) - 2

        await pilot.press("escape")
        await pilot.pause()
        assert menu.active_index is None
        assert app.focused.id == "entry-call"


async def test_menu_opens_the_selected_entry(operator):
    from hamrlog.tui.widgets.menubar import SHORTCUTS, MenuBar

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("f10")
        await pilot.pause()
        menu = app.query_one(MenuBar)
        menu.active_index = next(
            index for index, entry in enumerate(SHORTCUTS) if entry[3] == "band"
        )
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, SelectionScreen)


async def test_mode_selector_holds_analogue_and_digital_modes(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.press("f4")
        await pilot.pause()
        options = app.screen.query_one("#choices")
        assert options.option_count > 20

        # Filtering by the group name narrows it to the digital ones.
        (await wait_for(pilot, app, "#filter")).value = "voz digital"
        await pilot.pause()
        assert 0 < app.screen.query_one("#choices").option_count < 10

        app.screen.query_one("#filter").value = "cw"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.state.mode == "CW"


async def test_footer_shows_the_help_shortcut(operator):
    from hamrlog.tui.widgets.footer import HELP_HINT, StatsFooter

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert HELP_HINT in str(app.query_one(StatsFooter).render())


async def test_history_ends_with_the_insert_row(operator):
    from hamrlog.tui.widgets.history import INSERT_ROW_KEY

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        history = app.query_one(HistoryPanel)
        # Present even with an empty log: it is where you write.
        assert history.row_count == 1
        assert history.on_insert_row

        await type_line(pilot, app, "ea1aaa")
        assert history.qso_count == 1
        assert history.row_count == 2
        # The cursor returns to the insert row after logging.
        assert history.on_insert_row
        key = history.coordinate_to_cell_key(history.cursor_coordinate).row_key
        assert key.value == INSERT_ROW_KEY


async def test_arrows_browse_the_history_without_moving_focus(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        for call in ("ea1aaa", "ea2bbb", "ea3ccc"):
            await type_line(pilot, app, call)

        history = app.query_one(HistoryPanel)
        assert history.on_insert_row

        await pilot.press("up")
        await pilot.pause()
        assert not history.on_insert_row
        assert history.selected_row().call == "EA3CCC"
        # The keyboard stays inside the entry panel: it swaps the form for the
        # action bar, but never hands the focus to the history table.
        assert app.focused in app.query_one(EntryPanel).walk_children()
        assert not isinstance(app.focused, HistoryPanel)

        await pilot.press("up")
        await pilot.pause()
        assert history.selected_row().call == "EA2BBB"

        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        assert history.on_insert_row


async def test_history_panel_is_not_reachable_with_tab(operator):
    """The main screen has one focusable thing: the entry line."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        assert app.focused.id == "entry-call"

        await pilot.press("tab")
        await pilot.pause()
        assert not isinstance(app.focused, HistoryPanel)
        assert not app.query_one(HistoryPanel).can_focus


async def test_typing_always_logs_a_new_qso_wherever_the_cursor_is(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await pilot.press("up")
        await pilot.pause()
        assert not app.query_one(HistoryPanel).on_insert_row

        # Typing jumps back to the insert row rather than editing.
        await type_line(pilot, app, "ea2bbb")
        assert QsoService.stats().total == 2
        assert app.query_one(HistoryPanel).on_insert_row


async def test_enter_on_a_selected_qso_opens_the_log(operator):
    """With nothing typed, Enter means 'work on the one I am looking at'."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await pilot.press("up")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, LogScreen)


async def test_delete_removes_the_browsed_qso_but_still_edits_text(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        panel = app.query_one(EntryPanel)

        # In the form, Delete belongs to the text box.
        assert not panel.browsing
        box = panel.fields[0]
        box.focus()
        box.value = "abc"
        box.cursor_position = 0
        await pilot.press("delete")
        await pilot.pause()
        assert box.value == "bc"
        box.value = ""
        await pilot.pause()

        # Browsing a QSO, Delete removes it.
        await pilot.press("up")
        await pilot.pause()
        assert panel.browsing
        await pilot.press("delete")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()
        assert QsoService.stats().total == 0


async def test_history_direction_is_configurable(operator):
    from hamrlog.tui.widgets.history import (
        INSERT_ROW_KEY,
        ORDER_NEWEST_FIRST,
        ORDER_OLDEST_FIRST,
    )

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        for call in ("ea1aaa", "ea2bbb"):
            await type_line(pilot, app, call)

        history = app.query_one(HistoryPanel)

        # Oldest first: the insert row is at the bottom.
        assert app.state.history_order == ORDER_OLDEST_FIRST
        assert history.get_row_at(0)[1].plain == "EA1AAA"
        assert history.coordinate_to_cell_key((2, 0)).row_key.value == INSERT_ROW_KEY

        app.state.history_order = ORDER_NEWEST_FIRST
        app._reload_history()
        await pilot.pause()

        # Newest first: the insert row moves to the top, where QSOs appear.
        assert history.coordinate_to_cell_key((0, 0)).row_key.value == INSERT_ROW_KEY
        assert history.get_row_at(1)[1].plain == "EA2BBB"
        assert history.on_insert_row


async def test_entry_form_becomes_an_action_bar_over_a_qso(operator):
    from hamrlog.tui.widgets.entry import BrowseBar

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa,uno")
        panel = app.query_one(EntryPanel)

        # On the insert row it is a form of text boxes.
        assert not panel.browsing
        assert panel.query_one("#entry-fields").display
        for character in "ea2":
            await pilot.press(character)
        await pilot.pause()
        assert panel.values()["call"] == "ea2"

        # Over a QSO the form is replaced by the action bar.
        await pilot.press("up")
        await pilot.pause()
        assert panel.browsing
        assert not panel.query_one("#entry-fields").display
        assert panel.query_one("#entry-browse", BrowseBar).display
        assert isinstance(app.focused, BrowseBar)

        # The half-typed QSO comes back untouched.
        await pilot.press("down")
        await pilot.pause()
        assert not panel.browsing
        assert panel.values()["call"] == "ea2"


async def test_letters_do_not_type_while_browsing(operator):
    """D, E and R are ordinary letters in a callsign; no silent typing."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await pilot.press("up")
        await pilot.pause()

        panel = app.query_one(EntryPanel)
        await pilot.press("x")
        await pilot.pause()
        assert panel.values()["call"] == ""
        assert "D suprimir" in str(app.query_one("#entry-feedback").render())


async def test_r_repeats_a_qso_into_the_entry_line(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea4abc,juan,59,57,Madrid,por la tarde")

        await pilot.press("up")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()

        panel = app.query_one(EntryPanel)
        history = app.query_one(HistoryPanel)
        assert panel.values() == {
            "call": "EA4ABC",
            "name": "Juan",
            "rst_sent": "59",
            "rst_rcvd": "57",
            "qth": "Madrid",
            "comment": "por la tarde",
        }
        # Back on the insert row, editable, ready for Enter.
        assert history.on_insert_row
        assert not panel.browsing

        panel.query_one("#entry-rst_sent").value = "55"
        panel.query_one("#entry-rst_rcvd").value = "59"
        await pilot.press("enter")
        await pilot.pause()

        assert QsoService.stats().total == 2
        row = QsoService.recent()[-1]
        assert row.call == "EA4ABC"
        assert row.rst_sent == "55"
        assert row.rst_rcvd == "59"
        assert row.qth == "Madrid"


async def test_repeat_uses_the_current_band_and_mode(operator):
    """Repeating means working the same station again now, not re-filing it."""
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea4abc,juan")
        await type_line(pilot, app, "/banda 20m")
        await type_line(pilot, app, "/modo cw")

        await pilot.press("up")
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        row = QsoService.recent()[-1]
        assert row.band == "20m"
        assert row.mode == "CW"


async def test_e_and_d_act_on_the_browsed_qso(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await type_line(pilot, app, "ea2bbb")

        await pilot.press("up")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, LogScreen)
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("up")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("s")
        await pilot.pause()
        assert QsoService.stats().total == 1


async def test_escape_returns_from_browsing_to_writing(operator):
    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea1aaa")
        await pilot.press("up")
        await pilot.pause()
        assert app.query_one(EntryPanel).browsing

        await pilot.press("escape")
        await pilot.pause()
        assert not app.query_one(EntryPanel).browsing
        assert app.query_one(HistoryPanel).on_insert_row


async def test_logging_says_when_the_station_is_new_to_the_book(operator):
    from hamrlog.core.services import ContactService

    app = HamrlogApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await type_line(pilot, app, "ea4abc,juan")
        feedback = str(app.query_one("#entry-feedback").render())
        assert "nuevo en la agenda" in feedback
        assert ContactService.lookup("EA4ABC") is not None

        # Second time around it is already known, so no notice.
        await type_line(pilot, app, "ea4abc,juan")
        assert "nuevo en la agenda" not in str(app.query_one("#entry-feedback").render())


async def test_tab_walks_the_entry_fields(operator):
    """Each field has its own box; Tab and Shift+Tab move between them."""
    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        panel = app.query_one(EntryPanel)
        names = [box.field_name for box in panel.fields]
        assert names == list(app.state.field_order)

        assert app.focused.id == "entry-call"
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused.id == "entry-name"
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused.id == "entry-rst_sent"

        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.focused.id == "entry-name"
        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.focused.id == "entry-call"


async def test_typing_field_by_field_logs_the_qso(operator):
    """The whole point: type, Tab, type, Enter."""
    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        for character in "ea4abc":
            await pilot.press(character)
        await pilot.press("tab")
        for character in "juan":
            await pilot.press(character)
        await pilot.press("tab")
        await pilot.press("5", "9")
        await pilot.press("tab")
        await pilot.press("5", "7")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        row = QsoService.recent()[-1]
        assert row.call == "EA4ABC"
        assert row.name == "Juan"
        assert row.rst_sent == "59"
        assert row.rst_rcvd == "57"
        # The form is cleared and ready for the next one.
        assert app.query_one(EntryPanel).values()["call"] == ""
        assert app.focused.id == "entry-call"


async def test_enter_logs_from_any_field(operator):
    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        panel = app.query_one(EntryPanel)
        panel.set_values({"call": "ea4abc", "name": "Juan", "qth": "Madrid"})
        panel.query_one("#entry-qth").focus()
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()
        assert QsoService.stats().total == 1
        assert QsoService.recent()[-1].qth == "Madrid"


async def test_a_comma_is_no_longer_a_separator(operator):
    """Commas are ordinary text now; in a callsign that makes it invalid."""
    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        panel = app.query_one(EntryPanel)
        panel.set_first_value("ea4abc,juan")
        await pilot.press("enter")
        await pilot.pause()

        assert QsoService.stats().total == 0
        assert "no permitidos" in str(app.query_one("#entry-feedback").render())

        # A comma inside a free-text field is kept verbatim.
        panel.set_values({"call": "ea4abc", "comment": "primero, y luego otro"})
        await pilot.press("enter")
        await pilot.pause()
        assert QsoService.recent()[-1].comment == "primero, y luego otro"


async def test_changing_the_field_order_rebuilds_the_boxes(operator):
    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        panel = app.query_one(EntryPanel)
        app.state.field_order = ("call", "rst_sent", "rst_rcvd", "comment")
        app._refresh_status()
        await panel.ready()
        await pilot.pause()

        assert [box.field_name for box in panel.fields] == [
            "call",
            "rst_sent",
            "rst_rcvd",
            "comment",
        ]


async def test_log_area_is_framed_with_a_title(operator):
    from textual.containers import Vertical

    app = HamrlogApp()
    async with app.run_test(size=(126, 26)) as pilot:
        await pilot.pause()
        frame = app.query_one("#log-frame", Vertical)
        assert frame.border_title == "Registro"
        # The history and the detail live inside it.
        assert app.query_one(HistoryPanel) in frame.walk_children()
        assert app.query_one(DetailPanel) in frame.walk_children()


async def test_detail_shows_what_a_new_qso_would_inherit(operator, station):
    app = HamrlogApp()
    async with app.run_test(size=(126, 26)) as pilot:
        app.state.station_id = station.id
        app._refresh_status()
        await pilot.pause()

        text = str(app.query_one(DetailPanel).render())
        assert "NUEVO CONTACTO" in text
        assert operator.callsign in text
        assert app.state.band in text
        assert station.rig in text


async def test_detail_expands_the_selected_qso(operator, station):
    app = HamrlogApp()
    async with app.run_test(size=(126, 26)) as pilot:
        app.state.station_id = station.id
        app._refresh_status()
        await pilot.pause()
        await type_line(
            pilot, app, "ea4abc,Juan Garcia,59,57,Madrid,primer contacto"
        )

        detail = app.query_one(DetailPanel)
        assert "NUEVO CONTACTO" in str(detail.render())

        await pilot.press("up")
        await pilot.pause()
        text = str(detail.render())

        assert "EA4ABC" in text
        assert "Juan Garcia" in text
        assert "Madrid" in text
        assert "AUTO" in text
        # Things the table has no room for.
        assert operator.callsign in text
        assert station.name in text
        assert "primer contacto" in text

        # Coming back to the insert row restores the session summary.
        await pilot.press("down")
        await pilot.pause()
        assert "NUEVO CONTACTO" in str(detail.render())


async def test_detail_shows_both_frequencies_over_a_repeater(operator):
    from hamrlog.core.services import RepeaterService

    RepeaterService.create("ED7ZAE", output_hz=145_600_000, ctcss_tx="88.5")

    app = HamrlogApp()
    async with app.run_test(size=(126, 26)) as pilot:
        await type_line(pilot, app, "/repetidor ED7ZAE")
        await type_line(pilot, app, "ea5zz,Pepe")

        await pilot.press("up")
        await pilot.pause()
        text = str(app.query_one(DetailPanel).render())
        assert "ED7ZAE" in text
        assert "145.600" in text
        assert "TX 145.000" in text


async def test_detail_marks_a_manual_qso(operator):
    import datetime as dt

    from hamrlog.core.services import QsoService as Service

    app = HamrlogApp()
    async with app.run_test(size=(126, 26)) as pilot:
        Service.log(
            {"call": "EA3MNO", "name": "Laia"},
            app.state,
            qso_utc=dt.datetime(2026, 1, 15, 12, 30),
        )
        app._reload_history()
        await pilot.pause()

        await pilot.press("up")
        await pilot.pause()
        text = str(app.query_one(DetailPanel).render())
        assert "MANUAL" in text
        assert "2026-01-15 12:30:00" in text


async def test_frequency_format_applies_across_the_interface(operator):
    from hamrlog.core import units
    from hamrlog.tui.widgets.menubar import StatusLine

    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        await type_line(pilot, app, "/banda 40m")
        await type_line(pilot, app, "ea4abc,Juan")

        # Default: megahertz, dot, no grouping.
        assert "7.130 MHz" in str(app.query_one(StatusLine).render())
        assert "7.130 MHz" in str(app.query_one(DetailPanel).render())

        # Switching the format redraws everything.
        app.state.freq_unit = units.UNIT_HZ
        app.state.decimal_separator = ","
        app.state.thousands_separator = "."
        app._refresh_status()
        app._reload_history()
        await pilot.pause()

        assert "7.130.000 Hz" in str(app.query_one(StatusLine).render())
        assert "7.130.000 Hz" in str(app.query_one(DetailPanel).render())


async def test_frequency_command_reads_the_configured_unit(operator):
    from hamrlog.core import units

    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        # Megahertz by default, so a bare number is megahertz.
        await type_line(pilot, app, "/frec 14.250")
        assert app.state.freq_hz == 14_250_000

        # A unit written by hand wins.
        await type_line(pilot, app, "/frec 7130 K")
        assert app.state.freq_hz == 7_130_000

        app.state.freq_unit = units.UNIT_KHZ
        app.state.apply_frequency_format()
        await type_line(pilot, app, "/frec 21300")
        assert app.state.freq_hz == 21_300_000


async def test_units_are_configurable_from_the_settings(operator):
    from hamrlog.tui.screens.config import ConfigScreen

    app = HamrlogApp()
    async with app.run_test(size=(140, 34)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)

        sections = app.screen.query_one("#sections")
        ids = [sections.get_option_at_index(i).id for i in range(sections.option_count)]
        assert "units" in ids

        sections.highlighted = ids.index("units")
        await pilot.press("enter")
        await pilot.pause()

        (await wait_for(pilot, app, "#field-unit")).value = "k"
        app.screen.query_one("#field-decimal").value = ","
        app.screen.query_one("#field-thousands").value = "."
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Lower case k is stored as K.
        assert app.state.freq_unit == "KHz"
        assert app.state.decimal_separator == ","
        assert app.state.thousands_separator == "."


async def test_settings_refuse_the_same_separator_twice(operator):

    app = HamrlogApp()
    async with app.run_test(size=(140, 34)) as pilot:
        await pilot.press("f5")
        await pilot.pause()
        sections = app.screen.query_one("#sections")
        ids = [sections.get_option_at_index(i).id for i in range(sections.option_count)]
        sections.highlighted = ids.index("units")
        await pilot.press("enter")
        await pilot.pause()

        (await wait_for(pilot, app, "#field-unit")).value = "M"
        app.screen.query_one("#field-decimal").value = "."
        app.screen.query_one("#field-thousands").value = "."
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Rejected: the settings are unchanged and the default still stands.
        assert app.state.decimal_separator == "."
        assert app.state.thousands_separator == ""


async def test_frequency_format_survives_a_restart(operator):
    from hamrlog.core.services import SettingsService

    app = HamrlogApp()
    async with app.run_test(size=(140, 30)) as pilot:
        app.state.freq_unit = "KHz"
        app.state.thousands_separator = " "
        SettingsService.save_state(app.state)
        await pilot.pause()

    restored = SettingsService.load_state()
    assert restored.freq_unit == "KHz"
    assert restored.frequency_format.format(7_130_000) == "7 130 KHz"
