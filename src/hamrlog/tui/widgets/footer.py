"""Bottom line with aggregate counters and the UTC clock."""

from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...core.dto import LogStats

#: Shown at the right edge: the help shortcut is out of the top menu, so this
#: is where it stays discoverable.
HELP_HINT = "Ctrl+F1 Ayuda"


class StatsFooter(Static):
    """Totals for the current log plus a live UTC clock.

    UTC is what goes into the log and into every ADIF export, so showing local
    time here would invite mistakes.
    """

    stats: reactive[LogStats | None] = reactive(None)

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh)

    def render(self) -> Text:
        now = dt.datetime.now(dt.timezone.utc)
        text = Text(no_wrap=True)
        text.append(f" {now:%Y-%m-%d %H:%M:%S} UTC ", style="bold black on rgb(120,180,255)")

        stats = self.stats
        if stats is not None:

            def chunk(label: str, value: object) -> None:
                text.append("   ")
                text.append(f"{label} ", style="dim")
                text.append(str(value), style="bold")

            chunk("QSO", stats.total)
            chunk("hoy", stats.today)
            chunk("únicos", stats.unique_calls)
            chunk("países", stats.countries)
            if stats.by_band:
                top = sorted(stats.by_band.items(), key=lambda item: -item[1])[:3]
                text.append("   ")
                text.append(
                    " ".join(f"{band}:{count}" for band, count in top), style="dim yellow"
                )

        # Pad so the help hint sits flush against the right edge, dropping it
        # entirely when the terminal is too narrow to hold both.
        width = self.size.width
        padding = width - text.cell_len - len(HELP_HINT) - 1
        if width and padding >= 2:
            text.append(" " * padding)
            text.append(HELP_HINT, style="dim")
            text.append(" ")
        return text

    def on_resize(self) -> None:
        self.refresh()
