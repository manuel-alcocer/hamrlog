"""Top shortcut menu and the active configuration line below it.

The menu is a reminder of the Alt+letter shortcuts. Letters rather than
function keys because several terminal emulators keep F-keys for themselves.
Each letter belongs to its word and is highlighted inside it, as in classic
menu bars, so the bar needs no key column of its own.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...core import bands, modes

#: (letter, full label, short label, action). The short label is used on
#: narrow terminals so the whole menu always fits: an operator must never have
#: to guess whether a shortcut exists because it scrolled off the edge. Both
#: labels must contain the letter; where two words start alike, the second
#: takes another of its letters (cOntactos, rpTr).
SHORTCUTS: tuple[tuple[str, str, str, str], ...] = (
    ("R", "Registro", "Reg", "log"),
    ("B", "Banda", "Ban", "band"),
    ("F", "Frec", "Frec", "frequency"),
    ("M", "Modo", "Mod", "mode"),
    ("C", "Config", "Cfg", "config"),
    ("E", "Equipo", "Equ", "station"),
    ("P", "Perfiles", "Perf", "profiles"),
    ("O", "Contactos", "Cont", "contacts"),
    ("T", "Rptr", "Rptr", "repeater"),
)

KEY_STYLE = "bold black on rgb(120,180,255)"


def split_label(label: str, letter: str) -> tuple[str, str, str]:
    """Split ``label`` around the first occurrence of ``letter``."""
    index = label.lower().index(letter.lower())
    return label[:index], label[index], label[index + 1 :]


class MenuBar(Static):
    """Single line listing every Alt+letter shortcut."""

    def on_resize(self) -> None:
        self.refresh()

    def render(self) -> Text:
        available = self.size.width or 120
        # Try full labels, then short ones, then letters alone.
        for label_index, separator in ((1, "  "), (2, "  "), (2, " "), (None, " ")):
            text = self._build(label_index, separator)
            if text.cell_len <= available:
                return text
        return text

    def _build(self, label_index: int | None, separator: str) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        for index, shortcut in enumerate(SHORTCUTS):
            if index:
                text.append(separator)
            if label_index is None:
                text.append(shortcut[0], style=KEY_STYLE)
                continue
            before, key, after = split_label(shortcut[label_index], shortcut[0])
            text.append(before, style="bold")
            text.append(key, style=KEY_STYLE)
            text.append(after, style="bold")
        return text


class StatusLine(Static):
    """One line summarising the configuration every new QSO inherits."""

    operator: reactive[str] = reactive("")
    repeater: reactive[str] = reactive("")
    band: reactive[str] = reactive("")
    freq_hz: reactive[int | None] = reactive(None)
    mode: reactive[str] = reactive("")
    digital_summary: reactive[str] = reactive("")
    station: reactive[str] = reactive("")
    profile: reactive[str] = reactive("")

    def render(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")

        def chunk(label: str, value: str, style: str = "bold white") -> None:
            if not value:
                return
            if text.plain:
                text.append(" · ", style="dim")
            if label:
                text.append(f"{label} ", style="dim")
            text.append(value, style=style)

        chunk("OP", self.operator or "sin operador", "bold cyan")
        chunk("BANDA", self.band or "-", "bold yellow")
        chunk("QRG", bands.format_frequency(self.freq_hz), "bold yellow")
        # Working through a repeater changes where the signal goes, so it is
        # shown right next to the frequency it applies to.
        chunk("VÍA", self.repeater, "bold bright_red")

        mode = modes.get(self.mode)
        mode_style = "bold magenta" if mode and mode.is_digital else "bold green"
        chunk("MODO", self.mode or "-", mode_style)
        chunk("", self.digital_summary, "magenta")
        chunk("EQUIPO", self.station, "white")
        chunk("CONFIG", self.profile or "(sin guardar)", "bold blue")
        return text
