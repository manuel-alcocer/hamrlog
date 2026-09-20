"""Top shortcut menu and the active configuration line below it.

The menu is normally just a reminder of the function keys, but F10 turns it
into a navigable bar in the style of Midnight Commander: left and right walk
the entries, Enter opens one and Escape returns to the entry line. That gives
a way in for anybody whose terminal swallows a function key.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from ...core import bands, modes

#: (key, full label, short label, action). The short label is used on narrow
#: terminals so the whole menu always fits: an operator must never have to
#: guess whether a shortcut exists because it scrolled off the edge.
SHORTCUTS: tuple[tuple[str, str, str, str], ...] = (
    ("F1", "Registro", "Reg", "log"),
    ("F2", "Banda", "Ban", "band"),
    ("F3", "Frec", "Frec", "frequency"),
    ("F4", "Modo", "Mod", "mode"),
    ("F5", "Config", "Cfg", "config"),
    ("F6", "Equipo", "Equ", "station"),
    ("F7", "Perfiles", "Perf", "profiles"),
    ("F8", "Contactos", "Cont", "contacts"),
    ("F9", "Rptr", "Rptr", "repeater"),
    ("F10", "Menú", "Menú", "menu"),
)

#: Entries the cursor walks. F10 is left out: it is the way in, so selecting
#: it would only loop back here.
NAVIGABLE = tuple(range(len(SHORTCUTS) - 1))

KEY_STYLE = "bold black on rgb(120,180,255)"
ACTIVE_KEY_STYLE = "bold black on rgb(255,210,90)"
ACTIVE_LABEL_STYLE = "bold black on rgb(255,210,90)"


class MenuBar(Static):
    """Single line listing every function key shortcut.

    Focusable only while the menu is active, so Tab never lands here.
    """

    can_focus = False

    #: Index into SHORTCUTS while navigating, None when the menu is idle.
    active_index: reactive[int | None] = reactive(None)

    BINDINGS = [
        Binding("left", "previous", "Anterior", show=False),
        Binding("right", "next", "Siguiente", show=False),
        Binding("home", "first", "Primero", show=False),
        Binding("end", "last", "Último", show=False),
        Binding("enter", "activate", "Abrir", show=False),
        Binding("escape", "leave", "Salir del menú", show=False),
        Binding("f10", "leave", "Salir del menú", show=False, priority=True),
    ]

    @dataclass
    class Activated(Message):
        """An entry was chosen. ``action`` is the app action to run."""

        action: str

    class Left(Message):
        """The menu was dismissed without choosing anything."""

    # --------------------------------------------------------- menu mode --
    def enter_menu(self) -> None:
        """Take the keyboard and start navigating."""
        self.can_focus = True
        self.active_index = NAVIGABLE[0]
        self.focus()

    def action_leave(self) -> None:
        self.active_index = None
        self.can_focus = False
        self.post_message(self.Left())

    def action_previous(self) -> None:
        self._step(-1)

    def action_next(self) -> None:
        self._step(1)

    def action_first(self) -> None:
        self.active_index = NAVIGABLE[0]

    def action_last(self) -> None:
        self.active_index = NAVIGABLE[-1]

    def _step(self, delta: int) -> None:
        """Move the highlight, wrapping around the ends."""
        if self.active_index is None:
            self.active_index = NAVIGABLE[0]
            return
        position = NAVIGABLE.index(self.active_index)
        self.active_index = NAVIGABLE[(position + delta) % len(NAVIGABLE)]

    def action_activate(self) -> None:
        if self.active_index is None:
            return
        action = SHORTCUTS[self.active_index][3]
        self.active_index = None
        self.can_focus = False
        self.post_message(self.Activated(action))

    # ---------------------------------------------------------- rendering --
    def on_resize(self) -> None:
        self.refresh()

    def render(self) -> Text:
        available = self.size.width or 120
        # Try full labels, then short ones, then keys alone.
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
            active = index == self.active_index
            text.append(
                f"{shortcut[0]} ", style=ACTIVE_KEY_STYLE if active else KEY_STYLE
            )
            if label_index is not None:
                text.append(
                    shortcut[label_index],
                    style=ACTIVE_LABEL_STYLE if active else "bold",
                )
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
        chunk("PERFIL", self.profile or "(sin guardar)", "bold blue")
        return text
