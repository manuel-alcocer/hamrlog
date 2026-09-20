"""Fast entry panel: the only widget the operator touches during a session.

Each field of the active profile gets its own box, laid out on one line. Tab
moves to the next, Shift+Tab to the previous, Enter logs the QSO from
wherever the cursor is. Splitting the line into boxes means the operator sees
which value goes where instead of counting separators.

The panel has two states. On the insert row it is this form. On a logged QSO
it becomes a bar of actions (delete, edit, repeat), because the arrows have
turned the screen into a log browser and letters would otherwise be ambiguous.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, Label, Static

#: Keys that act on the QSO under the cursor while browsing the log.
BROWSE_ACTIONS: dict[str, str] = {"d": "delete", "e": "edit", "r": "repeat"}

#: What the entry line offers while the cursor sits on a logged QSO.
BROWSE_PROMPT = "D suprimir · E editar · R repetir · ↓ volver a escribir"

#: Short label and box width per field. Width None means "take what is left",
#: so the free-text field grows with the terminal.
FIELD_LAYOUT: dict[str, tuple[str, int | None]] = {
    "call": ("IND", 13),
    "name": ("NOMBRE", 14),
    "rst_sent": ("ENV", 5),
    "rst_rcvd": ("REC", 5),
    "qth": ("QTH", 14),
    "gridsquare": ("LOC", 8),
    "comment": ("NOTAS", None),
    "band": ("BANDA", 7),
    "mode": ("MODO", 8),
    "freq_hz": ("FREC", 12),
    "power_w": ("POT", 5),
    "talkgroup": ("TG", 8),
    "reflector": ("REFL", 10),
    "room": ("ROOM", 10),
    "network": ("RED", 10),
}

DEFAULT_LAYOUT: tuple[str, int | None] = ("CAMPO", 12)


class EntryField(Input):
    """One box of the entry line.

    The arrow keys drive the history panel from here, so browsing the log
    never requires leaving the form or moving the focus out of it.
    """

    BINDINGS = [
        Binding("up", "move_history(-1)", "Subir en el histórico", show=False),
        Binding("down", "move_history(1)", "Bajar en el histórico", show=False),
        Binding("page_up", "move_history(-10)", "Subir 10", show=False),
        Binding("page_down", "move_history(10)", "Bajar 10", show=False),
        Binding("ctrl+up", "recall(-1)", "Entrada anterior", show=False),
        Binding("ctrl+down", "recall(1)", "Entrada siguiente", show=False),
    ]

    @dataclass
    class Recall(Message):
        """Request for the previous (-1) or next (+1) entry typed."""

        direction: int

    @dataclass
    class MoveHistory(Message):
        """Request to move the history cursor by ``delta`` rows."""

        delta: int

    def __init__(self, field_name: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.field_name = field_name

    def action_recall(self, direction: int) -> None:
        self.post_message(self.Recall(direction))

    def action_move_history(self, delta: int) -> None:
        self.post_message(self.MoveHistory(delta))


class BrowseBar(Static, can_focus=True):
    """Action bar shown in place of the form while browsing a logged QSO."""

    BINDINGS = [
        Binding("up", "move_history(-1)", "Subir", show=False),
        Binding("down", "move_history(1)", "Bajar", show=False),
        Binding("page_up", "move_history(-10)", "Subir 10", show=False),
        Binding("page_down", "move_history(10)", "Bajar 10", show=False),
        # This bar holds the keyboard while browsing, so it owns these too.
        Binding("enter", "run('edit')", "Editar", show=False),
        Binding("delete", "run('delete')", "Suprimir", show=False),
    ]

    @dataclass
    class Action(Message):
        """A key was pressed while browsing: delete, edit or repeat."""

        action: str

    class UnknownKey(Message):
        """A printable key with no meaning while browsing."""

    def action_move_history(self, delta: int) -> None:
        self.post_message(EntryField.MoveHistory(delta))

    def action_run(self, action: str) -> None:
        self.post_message(self.Action(action))

    def render(self) -> Text:
        return Text(f"  {BROWSE_PROMPT}", style="bold")

    async def _on_key(self, event: events.Key) -> None:
        """Letters are actions here, never text.

        D, E and R are ordinary letters in a callsign, so a bar that sometimes
        typed and sometimes deleted would be a trap. Typing stays off and an
        unrecognised key explains where you are.
        """
        character = (event.character or "").lower()
        action = BROWSE_ACTIONS.get(character)
        if action is not None:
            event.prevent_default()
            event.stop()
            self.post_message(self.Action(action))
        elif event.is_printable:
            event.prevent_default()
            event.stop()
            self.post_message(self.UnknownKey())


class EntryPanel(Vertical):
    """The form, the action bar and the two lines of guidance below them."""

    class Submitted(Message):
        """Enter was pressed: log what the form holds."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._field_order: tuple[str, ...] = ()
        #: Values put aside while browsing, so it never costs a half-typed QSO.
        self._draft: dict[str, str] = {}
        self._browsing = False
        #: Pending rebuild of the field boxes, awaited by ``ready()`` so the
        #: caller can focus them without racing the layout.
        self._pending_mount: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Horizontal(id="entry-fields")
        yield BrowseBar(id="entry-browse")
        yield Static("", id="entry-hint")
        yield Static("", id="entry-feedback")

    def on_mount(self) -> None:
        self.query_one("#entry-browse", BrowseBar).display = False

    # -------------------------------------------------------------- fields --
    @property
    def fields(self) -> list[EntryField]:
        return list(self.query(EntryField))

    @property
    def browsing(self) -> bool:
        return self._browsing

    def build_fields(self, field_order: tuple[str, ...]) -> None:
        """Lay out one box per field of the active profile.

        Rebuilt only when the order actually changes, so a status refresh does
        not throw away what is being typed.
        """
        if field_order == self._field_order:
            return
        self._field_order = field_order
        # Removing is asynchronous, so the new boxes must wait for the old
        # ones to go or their ids would collide.
        self._pending_mount = asyncio.ensure_future(self._rebuild(field_order))

    async def _rebuild(self, field_order: tuple[str, ...]) -> None:
        """Replace the boxes with one per field, in order.

        Deliberately does not grab the focus: this runs on every status
        refresh, and stealing the keyboard from a menu or a modal would be a
        bug. The application focuses the form when it means to.
        """
        row = self.query_one("#entry-fields", Horizontal)
        await row.remove_children()

        widgets: list[Label | EntryField] = []
        for name in field_order:
            label, width = FIELD_LAYOUT.get(name, DEFAULT_LAYOUT)
            box = EntryField(name, id=f"entry-{name}", classes="entry-field")
            box.styles.width = width if width is not None else "1fr"
            widgets.append(Label(label, classes="entry-label"))
            widgets.append(box)
        await row.mount_all(widgets)

    async def ready(self) -> None:
        """Wait until the field boxes exist, so they can be focused."""
        pending = self._pending_mount
        self._pending_mount = None
        if pending is not None:
            await pending

    def focus_first(self) -> None:
        """Put the cursor in the first box, which is where a QSO starts."""
        boxes = self.fields
        if boxes:
            boxes[0].focus()

    def values(self) -> dict[str, str]:
        """Current contents, keyed by field name."""
        return {box.field_name: box.value.strip() for box in self.fields}

    def set_values(self, values: dict[str, str]) -> None:
        """Fill the boxes, used by repeat and by entry recall.

        Leaves browse mode first and drops the saved draft: the values being
        written are what the operator asked for, and restoring the draft
        afterwards would undo them.
        """
        self._draft = {}
        self.set_browsing(False)
        for box in self.fields:
            box.value = values.get(box.field_name, "")
        self.focus_first()

    def clear(self) -> None:
        for box in self.fields:
            box.value = ""
        self.focus_first()

    @property
    def first_value(self) -> str:
        """Contents of the leading box, where callsigns and commands go."""
        boxes = self.fields
        return boxes[0].value.strip() if boxes else ""

    def set_first_value(self, text: str) -> None:
        boxes = self.fields
        if boxes:
            boxes[0].value = text

    # ------------------------------------------------------------ browsing --
    def set_browsing(self, browsing: bool) -> None:
        """Switch between filling in a QSO and acting on one."""
        if browsing == self._browsing:
            return
        self._browsing = browsing

        form = self.query_one("#entry-fields", Horizontal)
        bar = self.query_one("#entry-browse", BrowseBar)

        if browsing:
            self._draft = self.values()
            form.display = False
            bar.display = True
            bar.focus()
        else:
            bar.display = False
            form.display = True
            for box in self.fields:
                box.value = self._draft.get(box.field_name, "")
            self._draft = {}
            self.focus_first()

    def focus_input(self) -> None:
        """Return the keyboard to wherever input belongs right now."""
        if self._browsing:
            self.query_one("#entry-browse", BrowseBar).focus()
        else:
            self.focus_first()

    # -------------------------------------------------------------- hints --
    def set_hint(self, field_order: tuple[str, ...]) -> None:
        """Rebuild the form for this field order and refresh the help line."""
        self.build_fields(field_order)
        self.query_one("#entry-hint", Static).update(
            Text.assemble(
                ("  Tab", "dim"),
                (" campo siguiente  ·  ", "dim italic"),
                ("Mayús+Tab", "dim"),
                (" anterior  ·  ", "dim italic"),
                ("Enter", "dim"),
                (" registra  ·  ", "dim italic"),
                ("↑↓", "dim"),
                (" histórico  ·  ", "dim italic"),
                ("/ayuda", "dim"),
                (" comandos", "dim italic"),
            )
        )

    def feedback(self, message: str, level: str = "info") -> None:
        """Show a transient message under the form.

        Args:
            message: Text to show; empty clears the line.
            level: One of "info", "ok", "warning", "error", "dup".
        """
        styles = {
            "info": "dim",
            "ok": "bold green",
            "warning": "bold yellow",
            "error": "bold red",
            "dup": "bold black on yellow",
        }
        widget = self.query_one("#entry-feedback", Static)
        widget.update(Text(f"  {message}" if message else "", style=styles.get(level, "dim")))

    @on(Input.Submitted)
    def _on_any_submitted(self, event: Input.Submitted) -> None:
        """Enter logs the QSO from any box, not just the last one."""
        event.stop()
        self.post_message(self.Submitted())
