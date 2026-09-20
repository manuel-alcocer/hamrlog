"""F1: the log — the QSOs recorded, with search, edit and delete.

This is the record of what happened on the air. Who those stations are lives
in the address book (F8), which is a different question.

Edit rules live in the service layer; this screen only reflects them. A QSO
timestamped by the application clock (AUTO) shows every field but only lets
the callsign be changed, because the log is evidence of what happened. One
entered with a manual date (MANUAL) is fully editable, since it was
transcribed from paper or imported.
"""

from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label, Static

from ...core import bands, modes, units
from ...core.dto import QsoRow
from ...core.services import QsoService, ServiceError
from ...core.state import SessionState
from .base import ConfirmScreen, Field, FormScreen

_COLUMNS: tuple[tuple[str, int | None], ...] = (
    ("TIPO", 6),
    ("FECHA", 11),
    ("HORA", 9),
    ("INDICATIVO", 13),
    ("NOMBRE", 12),
    ("BANDA", 7),
    ("MODO", 9),
    ("E/R", 9),
    ("VÍA", 9),
    ("QTH", 14),
    ("PAÍS", 14),
    ("NOTAS", None),
)


class LogScreen(ModalScreen[bool]):
    """The recorded QSOs. Dismisses True when anything changed."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("f1", "close", "Cerrar", show=False),
        Binding("ctrl+n", "new_manual", "Añadir manual"),
        Binding("ctrl+e", "edit", "Editar"),
        # Delete works from the table; Ctrl+D is given priority so it also
        # works while the search box has focus, where Delete belongs to the
        # input itself.
        Binding("delete", "remove", "Borrar"),
        Binding("ctrl+d", "remove", "Borrar", priority=True),
        Binding("ctrl+f", "focus_search", "Buscar"),
    ]

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        self._rows: list[QsoRow] = []
        self._changed = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-wide"):
            yield Label("F1 · Registro", classes="modal-title")
            yield Static(
                "Los QSO que llevas hechos. Quién es cada indicativo está en F8.",
                classes="modal-subtitle",
            )
            with Horizontal(classes="search-row"):
                yield Input(
                    placeholder="Buscar por indicativo, nombre, QTH, país o comentario...",
                    id="search",
                )
                yield Static("", id="search-count", classes="search-count")
            yield DataTable(id="log-table")
            yield Static(
                "[yellow]AUTO[/yellow] = fecha puesta por el programa, solo se puede "
                "corregir el indicativo.   [green]MAN[/green] = fecha introducida a "
                "mano, todo editable.",
                classes="modal-legend",
            )
            yield Static(
                "Enter editar · Supr borrar · Ctrl+N añadir con fecha manual · "
                "Ctrl+F buscar · F8 abre los contactos · Esc cerrar",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        table = self.query_one("#log-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        for label, width in _COLUMNS:
            table.add_column(Text(label, style="bold"), width=width, key=label)
        self._reload()
        # Focus the table, not the search box, so Delete works straight away.
        if self._rows:
            table.focus()
        else:
            self.query_one("#search", Input).focus()

    def _reload(self, needle: str = "") -> None:
        table = self.query_one("#log-table", DataTable)
        table.clear()
        self._rows = QsoService.search(needle)
        for row in self._rows:
            kind = (
                Text("MAN", style="bold green")
                if row.is_manual
                else Text("AUTO", style="bold yellow")
            )
            table.add_row(
                kind,
                Text(row.qso_utc.strftime("%Y-%m-%d")),
                Text(row.qso_utc.strftime("%H:%M:%S")),
                Text(row.call, style="bold"),
                Text(row.name or "-"),
                Text(row.band or "-", style="yellow"),
                Text(row.mode or "-", style="green"),
                Text(f"{row.rst_sent}/{row.rst_rcvd}".strip("/") or "-"),
                Text(
                    row.repeater_call or "directo",
                    style="bright_red" if row.via_repeater else "dim",
                ),
                Text(row.qth or "-"),
                Text(row.country or "-", style="dim"),
                Text(row.comment or "", style="dim"),
                key=str(row.id),
            )
        self.query_one("#search-count", Static).update(
            Text(f" {len(self._rows)} QSO ", style="bold")
        )

    @on(Input.Changed, "#search")
    def _on_search(self, event: Input.Changed) -> None:
        self._reload(event.value)

    @on(Input.Submitted, "#search")
    def _on_search_submitted(self) -> None:
        self.query_one("#log-table", DataTable).focus()

    @on(DataTable.RowSelected, "#log-table")
    def _on_row_selected(self) -> None:
        self.action_edit()

    def _selected(self) -> QsoRow | None:
        table = self.query_one("#log-table", DataTable)
        if table.row_count == 0:
            return None
        index = table.cursor_row
        if not (0 <= index < len(self._rows)):
            return None
        return self._rows[index]

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    # ---------------------------------------------------------------- edit --
    def action_edit(self) -> None:
        row = self._selected()
        if row is None:
            return
        editable = QsoService.editable_fields(row.id)
        fields = _edit_fields(row, editable)
        subtitle = (
            "QSO MANUAL: puedes modificar cualquier valor."
            if row.is_manual
            else "QSO AUTOMÁTICO: solo se puede corregir el indicativo. "
            "El resto se muestra como referencia."
        )
        self.app.push_screen(
            FormScreen(f"Editar QSO · {row.call}", fields, subtitle=subtitle),
            lambda values: self._apply_edit(row, values),
        )

    def _apply_edit(self, row: QsoRow, values: dict[str, str] | None) -> None:
        if values is None:
            return
        try:
            changes = _build_changes(row, values)
        except ValueError as exc:
            self.app.notify(str(exc), severity="error")
            return
        if not changes:
            return
        try:
            QsoService.update(row.id, changes)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._changed = True
        self.app.notify("QSO actualizado.", severity="information")
        self._reload(self.query_one("#search", Input).value)

    # ----------------------------------------------------------- new manual --
    def action_new_manual(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        fields = [
            Field("call", "Indicativo", placeholder="EA7WM"),
            Field("date", "Fecha UTC", now.strftime("%Y-%m-%d"), placeholder="AAAA-MM-DD"),
            Field("time", "Hora UTC", now.strftime("%H:%M:%S"), placeholder="HH:MM:SS"),
            Field("name", "Nombre"),
            Field("band", "Banda", self.state.band, placeholder="40m"),
            Field(
                "freq",
                f"Frecuencia ({units.active().unit})",
                bands.format_frequency(self.state.freq_hz, with_unit=False),
                placeholder=units.active().format(7_130_000, with_unit=False),
            ),
            Field("mode", "Modo", self.state.mode, placeholder="SSB"),
            Field("rst_sent", "RST enviado", modes.default_rst(self.state.mode)),
            Field("rst_rcvd", "RST recibido", modes.default_rst(self.state.mode)),
            Field("qth", "QTH"),
            Field("gridsquare", "Locator"),
            Field("comment", "Comentario"),
        ]
        self.app.push_screen(
            FormScreen(
                "Añadir QSO con fecha manual",
                fields,
                subtitle="Al indicar la fecha a mano el QSO se marca como MANUAL "
                "y quedará totalmente editable.",
                save_label="Añadir",
            ),
            self._create_manual,
        )

    def _create_manual(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        if not values.get("call"):
            self.app.notify("Falta el indicativo.", severity="error")
            return
        timestamp = _parse_datetime(values.get("date", ""), values.get("time", ""))
        if timestamp is None:
            self.app.notify("Fecha u hora no válidas. Usa AAAA-MM-DD y HH:MM:SS.", severity="error")
            return

        fields: dict[str, object] = {
            "call": values["call"],
            "name": values.get("name", ""),
            "rst_sent": values.get("rst_sent", ""),
            "rst_rcvd": values.get("rst_rcvd", ""),
            "qth": values.get("qth", ""),
            "gridsquare": values.get("gridsquare", ""),
            "comment": values.get("comment", ""),
        }
        freq_hz = bands.parse_frequency(values.get("freq", ""))
        if freq_hz:
            fields["freq_hz"] = freq_hz
        band = bands.get(values.get("band", ""))
        if band:
            fields["band"] = band.name
        mode = modes.get(values.get("mode", ""))
        if mode:
            fields["mode"] = mode.name

        try:
            QsoService.log(fields, self.state, qso_utc=timestamp)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._changed = True
        self.app.notify(f"QSO manual con {values['call'].upper()} añadido.")
        self._reload(self.query_one("#search", Input).value)

    # -------------------------------------------------------------- delete --
    def action_remove(self) -> None:
        row = self._selected()
        if row is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar el QSO con {row.call}?",
                detail=f"{row.qso_utc:%Y-%m-%d %H:%M:%S} UTC · {row.band} · {row.mode}",
                danger=True,
            ),
            lambda confirmed: self._delete(row.id, confirmed),
        )

    def _delete(self, qso_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            QsoService.delete(qso_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._changed = True
        self._reload(self.query_one("#search", Input).value)

    def action_close(self) -> None:
        self.dismiss(self._changed)


def _edit_fields(row: QsoRow, editable: frozenset[str]) -> list[Field]:
    """Build the edit form, disabling whatever the rules forbid."""

    def make(key: str, label: str, value: str, rule_key: str | None = None) -> Field:
        return Field(key, label, value, editable=(rule_key or key) in editable)

    return [
        make("call", "Indicativo", row.call),
        make("date", "Fecha UTC", row.qso_utc.strftime("%Y-%m-%d"), "qso_utc"),
        make("time", "Hora UTC", row.qso_utc.strftime("%H:%M:%S"), "qso_utc"),
        make("name", "Nombre", row.name),
        make("band", "Banda", row.band),
        make(
            "freq",
            f"Frecuencia ({units.active().unit})",
            bands.format_frequency(row.freq_hz, with_unit=False),
            "freq_hz",
        ),
        make("mode", "Modo", row.mode),
        make("repeater_call", "Repetidor", row.repeater_call),
        make("rst_sent", "RST enviado", row.rst_sent),
        make("rst_rcvd", "RST recibido", row.rst_rcvd),
        make("qth", "QTH", row.qth),
        make("gridsquare", "Locator", row.gridsquare),
        make("country", "País", row.country),
        make("comment", "Comentario", row.comment),
    ]


def _build_changes(row: QsoRow, values: dict[str, str]) -> dict[str, object]:
    """Diff the form against the stored QSO, converting types.

    Only fields the form actually offered are present in ``values``, so a
    read-only field can never reach the service layer.
    """
    changes: dict[str, object] = {}

    if "call" in values and values["call"].upper() != row.call.upper():
        changes["call"] = values["call"]

    if "date" in values or "time" in values:
        timestamp = _parse_datetime(
            values.get("date", row.qso_utc.strftime("%Y-%m-%d")),
            values.get("time", row.qso_utc.strftime("%H:%M:%S")),
        )
        if timestamp is None:
            raise ValueError("Fecha u hora no válidas. Usa AAAA-MM-DD y HH:MM:SS.")
        if timestamp != row.qso_utc:
            changes["qso_utc"] = timestamp

    if "freq" in values:
        freq_hz = bands.parse_frequency(values["freq"])
        if freq_hz != row.freq_hz:
            changes["freq_hz"] = freq_hz

    if "band" in values and values["band"] != row.band:
        band = bands.get(values["band"])
        if values["band"] and band is None:
            raise ValueError(f"Banda desconocida: «{values['band']}».")
        changes["band"] = band.name if band else ""

    if "mode" in values and values["mode"].upper() != row.mode.upper():
        mode = modes.get(values["mode"])
        if values["mode"] and mode is None:
            raise ValueError(f"Modo desconocido: «{values['mode']}».")
        changes["mode"] = mode.name if mode else ""

    for key, current in (
        ("name", row.name),
        ("repeater_call", row.repeater_call),
        ("rst_sent", row.rst_sent),
        ("rst_rcvd", row.rst_rcvd),
        ("qth", row.qth),
        ("gridsquare", row.gridsquare),
        ("country", row.country),
        ("comment", row.comment),
    ):
        if key in values and values[key] != current:
            changes[key] = values[key]

    return changes


def _parse_datetime(date_text: str, time_text: str) -> dt.datetime | None:
    """Parse the form's date and time fields into a naive UTC datetime."""
    date_text = date_text.strip()
    time_text = time_text.strip() or "00:00:00"
    if time_text.count(":") == 1:
        time_text += ":00"
    for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            parsed_date = dt.datetime.strptime(date_text, date_format).date()
            break
        except ValueError:
            continue
    else:
        return None
    try:
        parsed_time = dt.datetime.strptime(time_text, "%H:%M:%S").time()
    except ValueError:
        return None
    return dt.datetime.combine(parsed_date, parsed_time)
