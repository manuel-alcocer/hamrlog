"""History panel: the QSOs logged so far, with the insert row.

The table is never focused. The entry line keeps the keyboard at all times and
the arrow keys move this cursor from there, so the operator never has to think
about which pane has focus in the middle of a pile-up.

The list always carries one extra row, ``<Insert new>``, sitting where the
next QSO will appear. That row is "I am writing a new one", which makes the
position of the cursor the whole state of the main screen: on the insert row
you are logging, anywhere else you are looking at what is already logged.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable

from ...core import bands, units
from ...core.dto import QsoRow
from ...i18n import N_, _

#: Row key of the insert row. QSO rows are keyed by their id.
INSERT_ROW_KEY = "__insert__"

#: Label of the insert row, translated where it is drawn.
INSERT_LABEL = N_("<Insert new>")

#: Newest last (the log grows downwards) or newest first.
ORDER_OLDEST_FIRST = "asc"
ORDER_NEWEST_FIRST = "desc"

#: (column label, width). None width lets the column take the remaining space.
#: The English label is the column key; the heading shown is its translation.
COLUMNS: tuple[tuple[str, int | None], ...] = (
    # Flags of the row, one letter each (see INFO_FLAGS); empty when there is
    # nothing to say about it.
    (N_("INFO"), 4),
    (N_("DATE TIME"), 16),
    (N_("CALLSIGN"), 12),
    (N_("NAME"), 12),
    (N_("FREQUENCY"), 10),
    (N_("MODE"), 7),
    # The setup rather than the reports: those are in the detail pane.
    (N_("SETUP"), 16),
    (N_("COUNTRY"), 14),
    (N_("QTH"), None),
)

#: Letters of the INFO column, in the order they are written: S for a QSO
#: selected with Space or Ctrl+A, E for one with an error (so far, a setup
#: that cannot work its frequency). A selected QSO with an error reads «SE».
FLAG_SELECTED = "S"
FLAG_ERROR = "E"

#: Date and time without seconds. A strftime pattern, translated like any
#: text: the English order is year first, the Spanish one day first.
DATE_FORMAT = N_("%y/%m/%d %H:%M")


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
        #: Ids of the QSOs selected with Space or Ctrl+A.
        self.marked: set[int] = set()

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        for label, width in COLUMNS:
            self.add_column(Text(self._header(label), style="bold"), width=width, key=label)

    @staticmethod
    def _header(label: str) -> str:
        """Column heading, with the unit where the values carry one.

        Repeating "MHz" on every row wastes the width the number needs, so
        the unit is stated once at the top.
        """
        if label == "FREQUENCY":
            # Abbreviated so the heading with its unit fits the column the
            # numbers need.
            return _("FREQ ({unit})").format(unit=units.active().unit)
        return _(label)

    def refresh_headers(self) -> None:
        """Redraw the headings after the frequency format changed."""
        for label, _width in COLUMNS:
            column = self.columns.get(label)
            if column is not None:
                column.label = Text(self._header(label), style="bold")
        self.refresh()

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
        """True when the cursor is on ``<Insert new>``."""
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
        # A deleted QSO cannot stay selected.
        self.marked &= {row.id for row in self._rows}
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
        cells[0] = Text("▸", style="bold green")
        cells[1] = Text(_(INSERT_LABEL), style="bold green")
        self.add_row(*cells, key=INSERT_ROW_KEY)

    def _append(self, row: QsoRow) -> None:
        self.add_row(*self._cells(row), key=str(row.id))

    # ---------------------------------------------------------- selection --
    def toggle_mark(self, qso_id: int) -> None:
        """Select a QSO, or unselect it if it already was."""
        self.marked ^= {qso_id}
        self._redraw_marks([qso_id])

    def toggle_all(self) -> None:
        """Select every QSO shown, or none when all of them already are."""
        everything = {row.id for row in self._rows}
        changed = everything if self.marked != everything else set(self.marked)
        self.marked = set() if self.marked == everything else everything
        self._redraw_marks(changed)

    def marked_rows(self) -> list[QsoRow]:
        return [row for row in self._rows if row.id in self.marked]

    def _redraw_marks(self, qso_ids: object) -> None:
        by_id = {row.id: row for row in self._rows}
        for qso_id in qso_ids:  # type: ignore[attr-defined]
            if qso_id in by_id:
                self.update_cell(str(qso_id), COLUMNS[0][0], self._cells(by_id[qso_id])[0])

    def replace_row(self, row: QsoRow) -> None:
        """Redraw one QSO after an edit, leaving the cursor where it is."""
        self._rows = [row if known.id == row.id else known for known in self._rows]
        for (label, _width), cell in zip(COLUMNS, self._cells(row), strict=True):
            self.update_cell(str(row.id), label, cell)

    def _cells(self, row: QsoRow) -> list[Text]:
        marker = Text("M ", style="bold yellow") if row.is_manual else Text("")
        info = Text.assemble(
            (FLAG_SELECTED if row.id in self.marked else "", "bold cyan"),
            (FLAG_ERROR if row.equipment_mismatch else "", "bold red"),
        )
        return [
            info,
            Text(row.qso_utc.strftime(_(DATE_FORMAT))),
            marker + Text(row.call, style="bold"),
            Text(row.name or "-"),
            Text(bands.format_frequency(row.freq_hz, with_unit=False)),
            Text(row.mode or "-", style="green"),
            Text(row.equipment_name or "", style="red" if row.equipment_mismatch else ""),
            Text(_(row.country) if row.country else "-", style="dim"),
            Text(row.qth or ""),
        ]
