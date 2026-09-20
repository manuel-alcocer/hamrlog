"""Main Textual application.

Layout, top to bottom: shortcut menu, active configuration, history panel,
fast entry panel, counters. Everything the operator does during a session
happens in the entry line; the function keys only change what that line
inherits.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import resources

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical

from ..core import bands, callsign, modes
from ..core import entry as entry_parser
from ..core.services import (
    ContactService,
    OperatorService,
    ProfileService,
    QsoService,
    RepeaterService,
    ServiceError,
    SettingsService,
    StationService,
)
from ..core.state import SessionState
from ..db.session import init_engine
from .screens.base import ConfirmScreen, Field, FormScreen
from .screens.config import DEFAULT_METRICS, METRICS_KEY, ConfigScreen
from .screens.contacts import ContactsScreen
from .screens.help import HelpScreen
from .screens.log import LogScreen
from .screens.profiles import ProfileScreen
from .screens.repeaters import DIRECT, RepeaterScreen
from .screens.selectors import FrequencyScreen, band_screen, mode_screen
from .screens.stations import StationScreen
from .screens.transfer import TransferScreen
from .widgets.detail import DetailPanel
from .widgets.entry import BrowseBar, EntryField, EntryPanel
from .widgets.footer import StatsFooter
from .widgets.history import HistoryPanel
from .widgets.menubar import MenuBar, StatusLine

#: Command word -> action name, for the ``/command`` fallback to the F keys.
COMMANDS: dict[str, str] = {
    "ayuda": "help", "help": "help", "?": "help",
    "banda": "band", "band": "band",
    "frec": "frequency", "freq": "frequency", "qrg": "frequency", "frecuencia": "frequency",
    "modo": "mode", "mode": "mode", "digital": "mode",
    "equipo": "station", "station": "station",
    "perfil": "profiles", "perfiles": "profiles", "profile": "profiles",
    # The address book.
    "contactos": "contacts", "contacts": "contacts",
    "agenda": "contacts", "listin": "contacts", "listín": "contacts",
    # The QSO log.
    "registro": "log", "registros": "log", "log": "log", "qso": "log",
    # Import and export.
    "exportar": "transfer", "importar": "transfer", "export": "transfer",
    "import": "transfer", "adif": "transfer",
    "repetidor": "repeater", "rptr": "repeater", "repeater": "repeater",
    "directo": "direct", "simplex": "direct",
    "config": "config", "configuracion": "config", "configuración": "config",
    "deshacer": "undo", "undo": "undo", "borrar": "undo", "delete": "undo",
    "salir": "quit", "quit": "quit", "exit": "quit",
}

#: How many previously typed lines the up/down keys can recall.
LINE_HISTORY_LIMIT = 100

#: Browse screens that replace one another rather than stacking.
SWAPPABLE_SCREENS: tuple[type, ...] = (LogScreen, ContactsScreen)


class HamrlogApp(App[None]):
    """The logbook application."""

    # Read as package data rather than by file path: inside a PyInstaller
    # bundle the modules live in an archive and __file__ points nowhere on
    # disk, so CSS_PATH would fail there.
    CSS = resources.files("hamrlog.tui").joinpath("styles.tcss").read_text(encoding="utf-8")
    TITLE = "hamrlog"
    SUB_TITLE = "diario de radioaficionado"

    # priority=True so the function keys work while the entry line has focus.
    BINDINGS = [
        Binding("f1", "log", "Registro", priority=True),
        Binding("f2", "band", "Banda", priority=True),
        Binding("f3", "frequency", "Frecuencia", priority=True),
        Binding("f4", "mode", "Modo", priority=True),
        Binding("f5", "config", "Configuración", priority=True),
        Binding("f6", "station", "Equipo", priority=True),
        Binding("f7", "profiles", "Perfiles", priority=True),
        Binding("f8", "contacts", "Contactos", priority=True),
        Binding("f9", "repeater", "Repetidor", priority=True),
        Binding("f10", "menu", "Menú", priority=True),
        # Help is out of the top menu, so it lives here and in the footer.
        # F12 is kept as a fallback: some terminals swallow Ctrl+F1.
        Binding("ctrl+f1", "help", "Ayuda", priority=True),
        Binding("f12", "help", "Ayuda", priority=True, show=False),
        Binding("ctrl+d", "delete_qso", "Borrar QSO", priority=True),
        Binding("escape", "back_to_entry", "Volver a escribir", show=False),
        Binding("ctrl+q", "quit", "Salir", priority=True),
    ]

    def __init__(self, database_url: str | None = None) -> None:
        super().__init__()
        self.database_url = database_url
        self.state = SessionState()
        self._line_history: list[dict[str, str]] = []
        self._history_index: int | None = None
        self._last_dup_check = ""
        #: True while the feedback line describes the selected QSO, so that
        #: leaving the selection clears it without wiping other messages.
        self._showing_selection = False

    # ------------------------------------------------------------- layout --
    def compose(self) -> ComposeResult:
        yield MenuBar(id="menubar")
        yield StatusLine(id="statusline")
        # The log and the detail of whatever is selected share one frame: they
        # are two views of the same thing, the entry form is a separate job.
        with Vertical(id="log-frame"):
            yield HistoryPanel(id="history")
            yield DetailPanel(id="detail")
        yield EntryPanel(id="entry")
        yield StatsFooter(id="stats")

    async def on_mount(self) -> None:
        init_engine(self.database_url)
        self._load_initial_state()
        # Before anything renders a frequency.
        self.state.apply_frequency_format()
        self._maybe_start_metrics()
        self.query_one(HistoryPanel).order = self.state.history_order
        self.query_one(HistoryPanel).load(QsoService.recent())
        self._refresh_status()
        self._refresh_stats()
        # Wait for the field boxes to exist before handing them the keyboard,
        # so nothing else can take it first.
        self.query_one("#log-frame", Vertical).border_title = "Registro"
        self._refresh_detail(None)
        panel = self.query_one(EntryPanel)
        await panel.ready()
        panel.focus_input()
        if self.state.operator_id is None:
            self.call_after_refresh(self._first_run_wizard)

    def _load_initial_state(self) -> None:
        """Restore the previous session, falling back to the default profile."""
        self.state = SettingsService.load_state()

        if not self.state.band and not self.state.freq_hz:
            default_profile = ProfileService.get_default()
            if default_profile is not None:
                ProfileService.apply_to_state(default_profile.id, self.state)

        # The stored operator may have been removed since the last run.
        if self.state.operator_id is not None:
            if OperatorService.get(self.state.operator_id) is None:
                self.state.operator_id = None
        if self.state.operator_id is None:
            operators = OperatorService.list_all()
            if operators:
                self.state.operator_id = operators[0].id

        if not self.state.mode:
            self.state.mode = modes.DEFAULT_MODE
        if not self.state.band and self.state.freq_hz is None:
            self.state.set_band("40m")

    def _maybe_start_metrics(self) -> None:
        """Start the Prometheus exporter when it is enabled in the settings."""
        config = SettingsService.get(METRICS_KEY, {}) or {}
        if not config.get("enabled"):
            return
        from ..api.metrics import start_exporter

        port = int(config.get("port", DEFAULT_METRICS["port"]))
        if start_exporter(port):
            self.notify(f"Métricas Prometheus en el puerto {port}.", severity="information")
        else:
            self.notify(
                "No se pudo arrancar el exportador de métricas. "
                "Comprueba el puerto o instala hamrlog[metrics].",
                severity="warning",
            )

    def _first_run_wizard(self) -> None:
        """Ask for a callsign the first time the application is opened."""
        self.push_screen(
            FormScreen(
                "Bienvenido a hamrlog",
                [
                    Field("callsign", "Tu indicativo", placeholder="EA7WM"),
                    Field("name", "Nombre"),
                    Field("gridsquare", "Locator", placeholder="IM76"),
                ],
                subtitle="Necesito un operador para empezar a registrar contactos.",
                save_label="Empezar",
            ),
            self._create_first_operator,
        )

    def _create_first_operator(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("callsign"):
            self.notify("Sin operador no se pueden registrar contactos (F10).", severity="warning")
            return
        try:
            operator = OperatorService.create(
                values["callsign"], values.get("name", ""), values.get("gridsquare", "")
            )
        except ServiceError as exc:
            self.notify(str(exc), severity="error")
            return
        self.state.operator_id = operator.id
        self._refresh_status()
        self.notify(f"Operador {operator.callsign} listo. Buena suerte con el DX.")

    # ------------------------------------------------------------ refresh --
    def _refresh_status(self) -> None:
        """Push the session state into the status line."""
        status = self.query_one(StatusLine)
        operator = OperatorService.get(self.state.operator_id) if self.state.operator_id else None
        station = StationService.get(self.state.station_id) if self.state.station_id else None

        status.operator = operator.callsign if operator else ""
        status.repeater = self.state.repeater_call
        status.band = self.state.band
        status.freq_hz = self.state.freq_hz
        status.mode = self.state.mode
        status.station = station.summary if station else ""
        status.profile = self.state.profile_name
        status.digital_summary = modes.status_summary(
            self.state.digital_data, has_repeater=self.state.via_repeater
        )
        self.state.apply_frequency_format()
        self.query_one(EntryPanel).set_hint(self.state.field_order)
        history = self.query_one(HistoryPanel)
        history.set_order(self.state.history_order)
        history.refresh_headers()
        # Reactives only redraw when their value changes, and a format change
        # leaves every value untouched.
        status.refresh()
        if not self.query_one(HistoryPanel).selected_qso_id():
            self._refresh_detail(None)

    def _refresh_detail(self, row: object | None) -> None:
        """Show the selected QSO, or what a new one would inherit."""
        detail = self.query_one(DetailPanel)
        if row is not None:
            detail.show_qso(row)  # type: ignore[arg-type]
            return

        operator = OperatorService.get(self.state.operator_id) if self.state.operator_id else None
        station = StationService.get(self.state.station_id) if self.state.station_id else None
        stats = QsoService.stats()
        detail.show_session(
            self.state,
            operator=operator.display if operator else "",
            station=station.summary if station else "",
            stats_line=f"{stats.today} QSO hoy" if stats.today else "",
        )

    def _refresh_stats(self) -> None:
        self.query_one(StatsFooter).stats = QsoService.stats()

    def _reload_history(self) -> None:
        panel = self.query_one(HistoryPanel)
        panel.set_order(self.state.history_order)
        panel.load(QsoService.recent())

    def _persist_state(self) -> None:
        try:
            SettingsService.save_state(self.state)
        except Exception:  # noqa: BLE001 - never block exit on a settings write
            pass

    # -------------------------------------------------------------- entry --
    @on(EntryField.MoveHistory)
    def _on_move_history(self, event: EntryField.MoveHistory) -> None:
        """Arrow keys browse the log without moving the focus."""
        self.query_one(HistoryPanel).move_selection(event.delta)

    @on(HistoryPanel.SelectionChanged)
    def _on_selection_changed(self, event: HistoryPanel.SelectionChanged) -> None:
        """Tell the operator what the arrows have landed on."""
        panel = self.query_one(EntryPanel)
        if event.qso_id is None:
            panel.set_browsing(False)
            self._refresh_detail(None)
            # Only clear a message this handler put there: returning to the
            # insert row must not wipe the confirmation of what was just saved.
            if self._showing_selection:
                panel.feedback("")
                self._showing_selection = False
            return

        row = QsoService.get(event.qso_id)
        if row is None:
            return
        # The detail pane says what this QSO is; the feedback line is left
        # free for messages rather than repeating it.
        self._refresh_detail(row)
        panel.set_browsing(True)
        if self._showing_selection:
            panel.feedback("")
        self._showing_selection = True

    @on(EntryField.Recall)
    def _on_recall(self, event: EntryField.Recall) -> None:
        """Walk previously entered QSOs with Ctrl+Up and Ctrl+Down."""
        if not self._line_history:
            return
        if self._history_index is None:
            self._history_index = len(self._line_history)
        self._history_index = max(
            0, min(len(self._line_history), self._history_index + event.direction)
        )
        entry = self.query_one(EntryPanel)
        if self._history_index >= len(self._line_history):
            entry.clear()
        else:
            entry.set_values(self._line_history[self._history_index])

    @on(EntryField.Changed)
    def _on_entry_changed(self, event: EntryField.Changed) -> None:
        """Warn about a duplicate as soon as the callsign is recognisable.

        EntryField does not define its own Changed, so this fires for every
        Input on screen, including the search boxes of the modal screens.
        """
        if not isinstance(event.input, EntryField):
            return
        if event.input.field_name != "call":
            return
        panel = self.query_one(EntryPanel)
        text = event.value.strip()
        if not text or entry_parser.is_command(text):
            if self._last_dup_check:
                panel.feedback("")
                self._last_dup_check = ""
            return

        token, _ = callsign.strip_override(text.upper())
        if len(token) < 4:
            if self._last_dup_check:
                panel.feedback("")
                self._last_dup_check = ""
            return
        if token == self._last_dup_check:
            return
        self._last_dup_check = token

        # Flag a malformed callsign as it is typed, before Enter is pressed.
        if self.state.callsign_validation != "off":
            problem = callsign.validate(token)
            if problem is not None:
                panel.feedback(problem, "error")
                return

        # Who they are, from the address book, and whether we know them already.
        known = ContactService.lookup(token) if self.state.autofill_from_book else None
        identity = known.summary if known else ""

        previous = QsoService.find_duplicates(token, self.state.band, self.state.mode)
        if previous:
            last = previous[0]
            message = (
                f" DUPLICADO  ya trabajado {len(previous)}× en {last.band}/{last.mode} · "
                f"último {last.qso_utc:%Y-%m-%d %H:%M} UTC"
            )
            name = identity or last.name
            panel.feedback(f"{message} · {name}" if name else message, "dup")
            return

        worked = QsoService.find_duplicates(token, "", "")
        if worked:
            last = worked[0]
            message = f"Conocido: {len(worked)} QSO previos · último en {last.band}/{last.mode}"
            name = identity or last.name
            panel.feedback(f"{message} · {name}" if name else message, "info")
        elif identity:
            panel.feedback(f"Agenda: {identity}", "info")
        else:
            panel.feedback("")

    @on(EntryPanel.Submitted)
    def _on_entry_submitted(self) -> None:
        panel = self.query_one(EntryPanel)
        history = self.query_one(HistoryPanel)
        values = panel.values()

        # A command is typed in the leading box, on its own.
        first = panel.first_value
        if entry_parser.is_command(first):
            panel.clear()
            self._last_dup_check = ""
            self._run_command(first)
            return

        if not any(values.values()):
            # Nothing filled in: on a logged QSO, Enter means "edit this one".
            if not history.on_insert_row:
                self.action_edit_selected()
            return

        # Anything filled in is a new QSO, wherever the cursor happens to be.
        history.go_to_insert_row()

        self._line_history.append(values)
        del self._line_history[:-LINE_HISTORY_LIMIT]
        self._history_index = None
        self._last_dup_check = ""

        self._log_contact(values)

    def _log_contact(self, values: dict[str, str]) -> None:
        """Validate the form and store the QSO."""
        panel = self.query_one(EntryPanel)
        parsed = entry_parser.from_fields(
            values,
            mode_name=self.state.mode,
            validation=self.state.callsign_validation,
        )
        if not parsed.ok:
            panel.feedback(parsed.error or "Entrada no válida.", "error")
            return

        # Checked before logging: afterwards the entry may exist because
        # this very QSO created it.
        was_known = (
            ContactService.lookup(str(parsed.fields.get("call", ""))) is not None
            if self.state.add_to_book
            else True
        )

        try:
            row = QsoService.log(parsed.fields, self.state, digital=parsed.digital)
        except ServiceError as exc:
            panel.feedback(str(exc), "error")
            return

        panel.clear()
        self.query_one(HistoryPanel).append_row_for(row)
        self._refresh_stats()
        self._refresh_detail(None)

        message = f"✓ {row.call} guardado a las {row.qso_utc:%H:%M:%S} UTC"
        if row.country:
            message += f" · {row.country}"
        if not was_known:
            message += " · nuevo en la agenda"
        if parsed.warnings:
            panel.feedback(f"{message}   ⚠ {' '.join(parsed.warnings)}", "warning")
        else:
            panel.feedback(message, "ok")

    def _run_command(self, line: str) -> None:
        """Dispatch a ``/command`` typed in the entry line."""
        panel = self.query_one(EntryPanel)
        command = entry_parser.parse_command(line)
        action = COMMANDS.get(command.name)
        if action is None:
            panel.feedback(
                f"Comando desconocido: «/{command.name}». Escribe /ayuda para ver la lista.",
                "error",
            )
            return

        # Commands that accept an inline argument skip their selector entirely.
        if command.argument:
            if action == "band":
                self._apply_band(command.argument)
                return
            if action == "frequency":
                freq_hz = bands.parse_frequency(command.argument)
                if freq_hz is None:
                    panel.feedback(f"Frecuencia no reconocida: «{command.argument}»", "error")
                    return
                self._apply_frequency(freq_hz)
                return
            if action in ("mode", "digital"):
                self._apply_mode(command.argument)
                return
            if action == "profiles":
                self._load_profile_by_name(command.argument)
                return
            if action == "repeater":
                self._load_repeater_by_callsign(command.argument)
                return

        getattr(self, f"action_{action}")()

    # ------------------------------------------------------------ actions --
    @property
    def _modal_open(self) -> bool:
        """True when a modal screen sits on top of the main one."""
        return len(self.screen_stack) > 1

    def _shortcut_busy(self, screen_type: type | None = None) -> bool:
        """Decide whether a function key should open its screen.

        The function keys have priority so they work from the entry line, but
        that means they also fire while a modal is open. Without this guard a
        second copy of the same screen would stack on top of the first.

        Pressing the shortcut of the screen already showing closes it, which
        is what a toggle should do.

        Returns:
            True when the caller must not open anything.
        """
        if screen_type is not None and isinstance(self.screen, screen_type):
            for name in ("action_close", "action_cancel"):
                handler = getattr(self.screen, name, None)
                if callable(handler):
                    handler()
                    return True
        return self._modal_open

    def action_help(self) -> None:
        if self._shortcut_busy(HelpScreen):
            return
        self.push_screen(HelpScreen())

    def action_band(self) -> None:
        if self._shortcut_busy():
            return
        self.push_screen(band_screen(self.state.band), self._on_band_chosen)

    def _on_band_chosen(self, band_name: str | None) -> None:
        if band_name:
            self._apply_band(band_name)

    def _apply_band(self, band_name: str) -> None:
        band = bands.get(band_name)
        panel = self.query_one(EntryPanel)
        if band is None:
            panel.feedback(f"Banda desconocida: «{band_name}»", "error")
            return
        self.state.set_band(band.name)
        self.state.profile_name = ""
        self._refresh_status()
        panel.feedback(
            f"Banda {band.name} · {bands.format_frequency(self.state.freq_hz)}", "ok"
        )
        panel.focus_input()

    def action_frequency(self) -> None:
        if self._shortcut_busy(FrequencyScreen):
            return
        self.push_screen(FrequencyScreen(self.state.freq_hz), self._on_frequency_chosen)

    def _on_frequency_chosen(self, freq_hz: int | None) -> None:
        if freq_hz:
            self._apply_frequency(freq_hz)

    def _apply_frequency(self, freq_hz: int) -> None:
        self.state.set_frequency(freq_hz)
        self.state.profile_name = ""
        self._refresh_status()
        panel = self.query_one(EntryPanel)
        panel.feedback(
            f"Frecuencia {bands.format_frequency(freq_hz)}"
            + (f" · banda {self.state.band}" if self.state.band else " · fuera de banda"),
            "ok" if self.state.band else "warning",
        )
        panel.focus_input()

    def action_mode(self) -> None:
        if self._shortcut_busy():
            return
        self.push_screen(mode_screen(self.state.mode), self._on_mode_chosen)

    def _on_mode_chosen(self, mode_name: str | None) -> None:
        if mode_name:
            self._apply_mode(mode_name)

    def _apply_mode(self, mode_name: str) -> None:
        mode = modes.get(mode_name)
        panel = self.query_one(EntryPanel)
        if mode is None:
            panel.feedback(f"Modo desconocido: «{mode_name}»", "error")
            return
        self.state.set_mode(mode.name)
        self.state.profile_name = ""
        self._refresh_status()
        if mode.digital_fields:
            self._ask_digital_fields(mode)
        else:
            panel.feedback(f"Modo {mode.name}", "ok")
            panel.focus_input()

    def _ask_digital_fields(self, mode: modes.Mode) -> None:
        """Ask for the values a digital mode needs (talkgroup, reflector...)."""
        fields = [
            Field(key, label, self.state.digital_data.get(key, ""))
            for key, label in mode.digital_fields
        ]
        self.push_screen(
            FormScreen(
                f"Datos de {mode.name}",
                fields,
                subtitle="Se aplican a todos los contactos hasta que los cambies. "
                "Se exportan como campos APP_HAMRLOG_* en ADIF.",
                save_label="Aplicar",
            ),
            self._on_digital_fields,
        )

    def _on_digital_fields(self, values: dict[str, str] | None) -> None:
        panel = self.query_one(EntryPanel)
        if values is not None:
            self.state.digital_data = {k: v for k, v in values.items() if v}
        self._refresh_status()
        panel.feedback(f"Modo {self.state.mode} configurado", "ok")
        panel.focus_input()

    def action_station(self) -> None:
        if self._shortcut_busy(StationScreen):
            return
        self.push_screen(StationScreen(self.state.station_id), self._on_station_chosen)

    def _on_station_chosen(self, station_id: int | None) -> None:
        if station_id is None:
            self.query_one(EntryPanel).focus_input()
            return
        self.state.station_id = station_id or None
        self.state.profile_name = ""
        self._refresh_status()
        station = StationService.get(station_id) if station_id else None
        panel = self.query_one(EntryPanel)
        panel.feedback(f"Equipo: {station.summary}" if station else "Sin equipo asignado", "ok")
        panel.focus_input()

    def action_repeater(self) -> None:
        if self._shortcut_busy(RepeaterScreen):
            return
        self.push_screen(RepeaterScreen(self.state), self._on_repeater_chosen)

    def _on_repeater_chosen(self, repeater_id: int | None) -> None:
        panel = self.query_one(EntryPanel)
        if repeater_id is None:
            panel.focus_input()
            return
        if repeater_id == DIRECT:
            self.action_direct()
            return
        self._apply_repeater(repeater_id)

    def _apply_repeater(self, repeater_id: int) -> None:
        panel = self.query_one(EntryPanel)
        try:
            RepeaterService.apply_to_state(repeater_id, self.state)
        except ServiceError as exc:
            panel.feedback(str(exc), "error")
            return
        self.state.profile_name = ""
        self._refresh_status()
        repeater = RepeaterService.get(repeater_id)
        if repeater is not None:
            detail = (
                f"escucha {bands.format_frequency(repeater.output_hz)} · "
                f"transmite {bands.format_frequency(repeater.input_hz)}"
            )
            if repeater.ctcss_tx:
                detail += f" · subtono {repeater.ctcss_tx}"
            panel.feedback(f"Por el repetidor {repeater.callsign} · {detail}", "ok")
        panel.focus_input()

    def action_direct(self) -> None:
        """Leave the repeater and work simplex on the current frequency."""
        panel = self.query_one(EntryPanel)
        if not self.state.via_repeater:
            panel.feedback("Ya estabas trabajando en directo.", "info")
            panel.focus_input()
            return
        self.state.clear_repeater()
        self.state.profile_name = ""
        self._refresh_status()
        panel.feedback(
            f"Directo en {bands.format_frequency(self.state.freq_hz)} (simplex)", "ok"
        )
        panel.focus_input()

    def _load_repeater_by_callsign(self, call: str) -> None:
        """Support ``/repetidor ED7ZAE`` without opening the list."""
        panel = self.query_one(EntryPanel)
        repeater = RepeaterService.get_by_callsign(call)
        if repeater is None:
            panel.feedback(
                f"No hay ningún repetidor dado de alta con el indicativo «{call}»", "error"
            )
            return
        self._apply_repeater(repeater.id)

    def action_profiles(self) -> None:
        if self._shortcut_busy(ProfileScreen):
            return
        self.push_screen(ProfileScreen(self.state), self._on_profile_result)

    def _on_profile_result(self, result: tuple[str, int | None] | None) -> None:
        panel = self.query_one(EntryPanel)
        if result is None:
            panel.focus_input()
            return
        action, profile_id = result
        if action == "load" and profile_id is not None:
            try:
                ProfileService.apply_to_state(profile_id, self.state)
            except ServiceError as exc:
                panel.feedback(str(exc), "error")
                return
            panel.feedback(f"Perfil «{self.state.profile_name}» cargado", "ok")
        elif action == "saved" and profile_id is not None:
            profile = ProfileService.get(profile_id)
            if profile is not None:
                self.state.profile_name = profile.name
            panel.feedback(f"Perfil «{self.state.profile_name}» guardado", "ok")
        self._refresh_status()
        panel.focus_input()

    def _load_profile_by_name(self, name: str) -> None:
        """Support ``/perfil HF-Casa`` without opening the selector."""
        panel = self.query_one(EntryPanel)
        needle = name.strip().lower()
        for profile in ProfileService.list_all():
            if profile.name.lower() == needle:
                ProfileService.apply_to_state(profile.id, self.state)
                self._refresh_status()
                panel.feedback(f"Perfil «{profile.name}» cargado", "ok")
                return
        panel.feedback(f"No existe el perfil «{name}»", "error")

    def _open_or_swap(self, screen_type: type, factory: Callable[[], object]) -> None:
        """Open one of the two browse screens.

        The log and the address book are siblings: going from one to the
        other is a common move, so they replace each other instead of
        stacking. Pressing the shortcut of the screen already open closes it.
        """
        if isinstance(self.screen, screen_type):
            self.screen.action_close()  # type: ignore[attr-defined]
            return
        if isinstance(self.screen, SWAPPABLE_SCREENS):
            self.screen.action_close()  # type: ignore[attr-defined]
        elif self._modal_open:
            return
        self.push_screen(factory(), self._on_contacts_closed)  # type: ignore[arg-type]

    def action_log(self) -> None:
        """F1: the QSOs recorded."""
        self._open_or_swap(LogScreen, lambda: LogScreen(self.state))

    def action_contacts(self) -> None:
        """F8: the address book."""
        self._open_or_swap(ContactsScreen, ContactsScreen)

    def _on_contacts_closed(self, changed: bool | None) -> None:
        if changed:
            self._reload_history()
            self._refresh_stats()
        self.query_one(EntryPanel).focus_input()

    def action_transfer(self) -> None:
        if self._shortcut_busy(TransferScreen):
            return
        self.push_screen(TransferScreen(self.state), self._on_contacts_closed)

    def action_menu(self) -> None:
        """F10: walk the top menu with the cursor keys, like Midnight Commander."""
        if self._modal_open:
            return
        self.query_one(MenuBar).enter_menu()

    @on(MenuBar.Activated)
    def _on_menu_activated(self, event: MenuBar.Activated) -> None:
        self.query_one(EntryPanel).focus_input()
        handler = getattr(self, f"action_{event.action}", None)
        if callable(handler):
            handler()

    @on(MenuBar.Left)
    def _on_menu_left(self) -> None:
        self.query_one(EntryPanel).focus_input()

    def action_back_to_entry(self) -> None:
        """Escape leaves the log and returns to the insert row."""
        if self._modal_open:
            return
        self.query_one(HistoryPanel).go_to_insert_row()

    def action_edit_selected(self) -> None:
        """Edit the QSO under the history cursor, from the main screen."""
        row = self.query_one(HistoryPanel).selected_row()
        if row is None:
            return
        self.push_screen(LogScreen(self.state), self._on_contacts_closed)

    def action_config(self) -> None:
        if self._shortcut_busy(ConfigScreen):
            return
        self.push_screen(ConfigScreen(self.state), self._on_config_closed)

    def _on_config_closed(self, changed: bool | None) -> None:
        if changed:
            self._refresh_status()
        self.query_one(EntryPanel).focus_input()

    @on(BrowseBar.Action)
    def _on_browse_action(self, event: BrowseBar.Action) -> None:
        """D, E and R act on the QSO the cursor is sitting on."""
        history = self.query_one(HistoryPanel)
        row = history.selected_row()
        if row is None:
            return
        if event.action == "delete":
            self._confirm_delete(row.id)
        elif event.action == "edit":
            self.action_edit_selected()
        elif event.action == "repeat":
            self._repeat_qso(row)

    @on(BrowseBar.UnknownKey)
    def _on_unknown_browse_key(self) -> None:
        """Remind the operator that the line is not a text field right now."""
        self.query_one(EntryPanel).feedback(
            "Estás sobre un QSO del histórico: D suprimir · E editar · R repetir · "
            "↓ hasta «<Insertar nuevo>» para escribir",
            "warning",
        )

    def _repeat_qso(self, row) -> None:  # type: ignore[no-untyped-def]
        """Load a logged QSO back into the entry line as a new one.

        The line comes back editable with the current field order, so the
        operator changes what differs and presses Enter. It is logged with the
        session's band and mode, not the old ones: repeating means working the
        same station again, now.
        """
        panel = self.query_one(EntryPanel)
        self.query_one(HistoryPanel).go_to_insert_row()
        panel.set_values(entry_parser.values_from_row(row, self.state.field_order))
        self._showing_selection = False
        # No message here on purpose: filling the line is the confirmation,
        # and the duplicate check that fires next says something more useful.

    def action_delete_qso(self) -> None:
        """Delete a QSO without leaving the main screen.

        Which one depends on where the focus is: the highlighted row when the
        operator is browsing the history, otherwise the most recent QSO,
        which is the one they just mistyped.

        The binding needs priority because Input already uses Ctrl+D to delete
        forwards, which would otherwise swallow it. That means it also fires
        over an open modal, so the key is handed to that screen's own delete.
        """
        if self._modal_open:
            handler = getattr(self.screen, "action_remove", None)
            if callable(handler):
                handler()
            return
        history = self.query_one(HistoryPanel)
        qso_id = history.selected_qso_id()
        if qso_id is None:
            recent = QsoService.recent(limit=1)
            if not recent:
                self.query_one(EntryPanel).feedback("No hay QSO que borrar.", "warning")
                return
            qso_id = recent[-1].id
        self._confirm_delete(qso_id)

    #: ``/deshacer`` is the command form of the same action.
    action_undo = action_delete_qso

    def _confirm_delete(self, qso_id: int) -> None:
        """Ask before removing a QSO, naming it so there is no doubt."""
        row = QsoService.get(qso_id)
        panel = self.query_one(EntryPanel)
        if row is None:
            panel.feedback("Ese QSO ya no existe.", "warning")
            return
        self.push_screen(
            ConfirmScreen(
                f"¿Borrar el QSO con {row.call}?",
                detail=f"{row.qso_utc:%Y-%m-%d %H:%M:%S} UTC · {row.band or '-'} · "
                f"{row.mode or '-'}" + (f" · {row.name}" if row.name else ""),
                danger=True,
            ),
            lambda confirmed: self._do_delete(qso_id, confirmed),
        )

    def _do_delete(self, qso_id: int, confirmed: bool | None) -> None:
        panel = self.query_one(EntryPanel)
        if confirmed:
            try:
                QsoService.delete(qso_id)
            except ServiceError as exc:
                panel.feedback(str(exc), "error")
                return
            self._reload_history()
            self._refresh_stats()
            panel.feedback("QSO borrado.", "ok")
        panel.focus_input()

    def action_quit(self) -> None:  # type: ignore[override]
        self._persist_state()
        self.exit()
