"""History panel: the QSOs logged so far, with the insert row.

The table is never focused. The entry line keeps the keyboard at all times and
the arrow keys move this cursor from there, so the operator never has to think
about which pane has focus in the middle of a pile-up.

The list always carries one extra row, ``<Insertar nuevo>``, sitting where the
next QSO will appear. That row is "I am writing a new one", which makes the
position of the cursor the whole state of the main screen: on the insert row
you are logging, anywhere else you are looking at what is already logged.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable

from ...core import bands
from ...core.dto import QsoRow

#: Row key of the insert row. QSO rows are keyed by their id.
INSERT_ROW_KEY = "__insert__"

#: Label of the insert row.
INSERT_LABEL = "<Insertar nuevo>"

#: Newest last (the log grows downwards) or newest first.
ORDER_OLDEST_FIRST = "asc"
ORDER_NEWEST_FIRST = "desc"

#: (column label, width). None width lets the column take the remaining space.
COLUMNS: tuple[tuple[str, int | None], ...] = (
    ("FECHA HORA", 19),
    ("INDICATIVO", 12),
    ("NOMBRE", 11),
    ("BANDA", 6),
    ("FRECUENCIA", 11),
    ("MODO", 7),
    ("E/R", 8),
    ("PAÍS", 14),
    ("NOTAS", None),
)


class HistoryPanel(DataTable):
    """Read-only log view with an insert row at the writing end."""

    # The entry line owns the keyboard; Tab must not land here.
    can_focus = False

    @dataclass
    class SelectionChanged(Message):
        """The cursor moved. ``qso_id`` is None on the insert row."""

        qso_id: int | None

    def __init__(self, *, order: str = ORDER_OLDEST_FIRST, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.order = order
        self._rows: list[QsoRow] = []

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        for label, width in COLUMNS:
            self.add_column(Text(label, style="bold"), width=width, key=label)

    # -------------------------------------------------------------- state --
    @property
    def _insert_index(self) -> int:
        """Where the insert row sits: with the newest QSOs, at either end."""
        return self.row_count - 1 if self.order == ORDER_OLDEST_FIRST else 0

    @property
    def qso_count(self) -> int:
        """Logged QSOs shown, not counting the insert row."""
        return len(self._rows)

    @property
    def on_insert_row(self) -> bool:
        """True when the cursor is on ``<Insertar nuevo>``."""
        return self.selected_qso_id() is None

    def set_order(self, order: str) -> None:
        """Change the direction and redraw, staying on the insert row."""
        if order == self.order:
            return
        self.order = order
        self.load(self._rows)

    # ------------------------------------------------------------ loading --
    def load(self, rows: list[QsoRow]) -> None:
        """Replace the whole table and park the cursor on the insert row.

        Args:
            rows: QSOs oldest first, as the service returns them.
        """
        self._rows = list(rows)
        self.clear()

        ordered = (
            self._rows if self.order == ORDER_OLDEST_FIRST else list(reversed(self._rows))
        )
        if self.order == ORDER_NEWEST_FIRST:
            self._add_insert_row()
        for row in ordered:
            self._append(row)
        if self.order == ORDER_OLDEST_FIRST:
            self._add_insert_row()

        self.go_to_insert_row()

    def append_row_for(self, row: QsoRow) -> None:
        """Add one QSO next to the insert row, used right after logging."""
        self._rows.append(row)
        self.load(self._rows)

    def go_to_insert_row(self) -> None:
        """Put the cursor back where new QSOs are written."""
        if self.row_count:
            # move_cursor scrolls the row into view on its own.
            self.move_cursor(row=self._insert_index, scroll=True)
        self.post_message(self.SelectionChanged(None))

    # --------------------------------------------------------- navigation --
    def move_selection(self, delta: int) -> None:
        """Move the cursor, clamped to the table.

        Called from the entry line, which keeps the focus.
        """
        if not self.row_count:
            return
        target = max(0, min(self.row_count - 1, self.cursor_row + delta))
        if target != self.cursor_row:
            self.move_cursor(row=target, scroll=True)
        self.post_message(self.SelectionChanged(self.selected_qso_id()))

    def selected_qso_id(self) -> int | None:
        """QSO id under the cursor, or None on the insert row."""
        if self.row_count == 0:
            return None
        try:
            row_key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key
        except Exception:  # noqa: BLE001 - cursor may be stale after a reload
            return None
        value = row_key.value
        if value is None or value == INSERT_ROW_KEY:
            return None
        return int(value)

    def selected_row(self) -> QsoRow | None:
        """The QSO under the cursor, or None on the insert row."""
        qso_id = self.selected_qso_id()
        if qso_id is None:
            return None
        return next((row for row in self._rows if row.id == qso_id), None)

    # ------------------------------------------------------------ drawing --
    def _add_insert_row(self) -> None:
        """Draw the row that stands for the QSO about to be written.

        The label goes in the first column, the only one wide enough to hold
        it without truncating.
        """
        cells = [Text("") for _ in COLUMNS]
        cells[0] = Text(f"▸ {INSERT_LABEL}", style="bold green")
        self.add_row(*cells, key=INSERT_ROW_KEY)

    def _append(self, row: QsoRow) -> None:
        marker = Text("M ", style="bold yellow") if row.is_manual else Text("")
        call = marker + Text(row.call, style="bold")
        self.add_row(
            Text(row.qso_utc.strftime("%Y-%m-%d %H:%M:%S")),
            call,
            Text(row.name or "-"),
            Text(row.band or "-", style="yellow"),
            Text(bands.format_frequency(row.freq_hz)),
            Text(row.mode or "-", style="green"),
            Text(f"{row.rst_sent}/{row.rst_rcvd}".strip("/") or "-"),
            Text(row.country or "-", style="dim"),
            Text(self._notes(row), style="dim"),
            key=str(row.id),
        )

    @staticmethod
    def _notes(row: QsoRow) -> str:
        """Comment plus any detail worth showing inline."""
        parts = []
        if row.repeater_call:
            parts.append(f"vía {row.repeater_call}")
        if row.qth:
            parts.append(row.qth)
        digital = row.digital_data or {}
        for key in ("talkgroup", "reflector", "room"):
            if digital.get(key):
                parts.append(f"{key[:2].upper()}:{digital[key]}")
        if row.comment:
            parts.append(row.comment)
        return " · ".join(parts)
