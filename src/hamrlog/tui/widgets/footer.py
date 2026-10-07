"""Bottom line with aggregate counters and the UTC clock."""

from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...core.dto import LogStats
from ...i18n import N_, _

#: Shown at the right edge, so the menus and the way out stay discoverable.
#: Translated where it is drawn.
HELP_HINT = N_(
    "F1 Log · F2 Inventory · F3 Address book · F4 Profiles · F5 Repeaters · Ctrl+Q Quit"
)

#: What is left of it when the terminal cannot hold the whole hint.
SHORT_HINTS = (
    N_("F1 Log · F2 Inventory · F3 Address book · F4 Profiles · F5 Repeaters"),
    N_("F1 · F2 · F3 · F4 · F5"),
)


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
            chunk(_("today"), stats.today)
            chunk(_("unique"), stats.unique_calls)
            chunk(_("countries"), stats.countries)
            if stats.by_band:
                top = sorted(stats.by_band.items(), key=lambda item: -item[1])[:3]
                text.append("   ")
                text.append(
                    " ".join(f"{band}:{count}" for band, count in top), style="dim yellow"
                )

        # Pad so the hint sits flush against the right edge. On a narrow
        # terminal it gets shorter, and only goes when even that does not fit.
        width = self.size.width
        for hint in (_(HELP_HINT), *(_(short) for short in SHORT_HINTS)):
            padding = width - text.cell_len - len(hint) - 1
            if width and padding >= 2:
                text.append(" " * padding)
                text.append(hint, style="dim")
                text.append(" ")
                break
        return text

    def on_resize(self) -> None:
        self.refresh()
