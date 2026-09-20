"""Detail pane: everything the history row has no room for.

The table shows what fits on one line; this shows the rest of whatever the
cursor is on. On the insert row it shows what a new QSO is about to inherit
instead, so the pane is useful in both states rather than blank half the time.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from ...core import bands, modes
from ...core.dto import QsoRow
from ...core.state import SessionState


class DetailPanel(Static):
    """Three lines describing the selected QSO, or the one being written."""

    def on_mount(self) -> None:
        self.show_nothing()

    # ----------------------------------------------------------- selected --
    def show_qso(self, row: QsoRow) -> None:
        """Expand a logged QSO: everything the table had to leave out."""
        text = Text(no_wrap=True, overflow="ellipsis")

        kind = ("MANUAL", "bold green") if row.is_manual else ("AUTO", "bold yellow")
        text.append(row.call, style="bold white")
        _chunk(text, row.name)
        _chunk(text, _place(row))
        _chunk(text, row.country, "dim")
        text.append("   ")
        text.append(f" {kind[0]} ", style=kind[1])
        text.append("\n")

        text.append(f"{row.qso_utc:%Y-%m-%d %H:%M:%S} UTC", style="bold")
        _chunk(text, row.band, "yellow")
        _chunk(text, _frequencies(row), "yellow")
        _chunk(text, row.mode, "green")
        _chunk(text, f"{row.rst_sent}/{row.rst_rcvd}".strip("/"))
        if row.repeater_call:
            _chunk(text, f"vía {row.repeater_call}", "bold bright_red")
        text.append("\n")

        third = Text(no_wrap=True, overflow="ellipsis")
        if row.operator_callsign:
            _chunk(third, f"Op {row.operator_callsign}", "cyan")
        if row.station_name:
            _chunk(third, row.station_name)
        digital = modes.status_summary(row.digital_data or {}, has_repeater=bool(row.repeater_call))
        if digital:
            _chunk(third, digital, "magenta")
        if row.comment:
            _chunk(third, f"«{row.comment}»", "italic")
        if not third.plain:
            third.append("—", style="dim")
        text.append(third)

        self.update(text)

    # -------------------------------------------------------------- insert --
    def show_session(
        self,
        state: SessionState,
        *,
        operator: str = "",
        station: str = "",
        stats_line: str = "",
    ) -> None:
        """Show what a QSO written now would inherit."""
        text = Text(no_wrap=True, overflow="ellipsis")

        text.append("NUEVO CONTACTO", style="bold green")
        text.append("   ")
        text.append("la fecha y la hora UTC se ponen al pulsar Enter", style="dim italic")
        text.append("\n")

        second = Text(no_wrap=True, overflow="ellipsis")
        _chunk(second, operator or "sin operador", "bold cyan")
        _chunk(second, state.band or "sin banda", "bold yellow")
        _chunk(second, bands.format_frequency(state.freq_hz), "yellow")
        if state.via_repeater:
            _chunk(second, f"vía {state.repeater_call}", "bold bright_red")
            if state.freq_tx_hz:
                _chunk(second, f"TX {bands.format_frequency(state.freq_tx_hz)}", "dim")
        _chunk(second, state.mode or "sin modo", "bold green")
        digital = modes.status_summary(state.digital_data, has_repeater=state.via_repeater)
        if digital:
            _chunk(second, digital, "magenta")
        text.append(second)
        text.append("\n")

        third = Text(no_wrap=True, overflow="ellipsis")
        if station:
            _chunk(third, station)
        _chunk(third, f"informe por defecto {modes.default_rst(state.mode)}", "dim")
        if state.autofill_from_book:
            _chunk(third, "nombre y QTH se rellenan desde la agenda", "dim")
        if stats_line:
            _chunk(third, stats_line, "dim")
        text.append(third)

        self.update(text)

    def show_nothing(self) -> None:
        self.update(Text("—", style="dim"))


def _chunk(text: Text, value: str, style: str = "white") -> None:
    """Append a value preceded by a separator, skipping empties."""
    if not value:
        return
    if text.plain:
        text.append(" · ", style="dim")
    text.append(value, style=style)


def _place(row: QsoRow) -> str:
    """QTH with the locator in brackets, when both are known."""
    if row.qth and row.gridsquare:
        return f"{row.qth} ({row.gridsquare})"
    return row.qth or row.gridsquare


def _frequencies(row: QsoRow) -> str:
    """Working frequency, plus the transmit one when they differ."""
    if not row.freq_hz:
        return ""
    rendered = bands.format_frequency(row.freq_hz)
    if row.freq_tx_hz and row.freq_tx_hz != row.freq_hz:
        rendered += f" (TX {bands.format_frequency(row.freq_tx_hz)})"
    return rendered
