"""Side by side columns walked with the cursor keys, like a file manager.

Each column lists what belongs to the entry highlighted in the one before:
stations, then their antennas, then their configurations. ↑↓ move inside a
column, → steps into the next, ← steps back, and Enter on the last one picks
the whole path at once.
"""

from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from .base import PanelScreen

#: Returned by ``value`` when the column has nothing highlighted.
NOTHING: Any = object()


class ColumnScreen(PanelScreen[Any]):
    """Base for Alt+E and Alt+P.

    Subclasses set ``TITLE``, ``SUBTITLE`` and ``COLUMN_COUNT`` and implement
    ``fill`` (what a column lists), ``help_for`` (the key line for a column)
    and ``activate`` (Enter on the last column).
    """

    TITLE_TEXT = ""
    COLUMN_COUNT = 2

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("right", "next_column", "Entrar", show=False),
        Binding("left", "previous_column", "Volver", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._values: list[list[Any]] = [[] for _ in range(self.COLUMN_COUNT)]
        #: Value of the previous column each column was last filled for.
        self._filled_for: list[Any] = [NOTHING] * self.COLUMN_COUNT
        self._column = 0

    # ------------------------------------------------------------ layout --
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(self.TITLE_TEXT, classes="modal-title")
            with Horizontal(classes="columns"):
                for index in range(self.COLUMN_COUNT):
                    # A vertical rule before every column but the first.
                    with Vertical(classes="column" if index == 0 else "column column-ruled"):
                        yield Label("", id=f"column-title-{index}", classes="column-title")
                        yield OptionList(id=f"column-{index}")

    def on_mount(self) -> None:
        self.fill(0)
        self._focus_column(0)

    # ---------------------------------------------------- for subclasses --
    def fill(self, column: int) -> None:
        """Populate ``column`` from the values highlighted before it.

        Implementations call ``set_column`` and must not touch later columns:
        filling one refills the next automatically.
        """
        raise NotImplementedError

    def help_for(self, column: int) -> str:
        raise NotImplementedError

    def activate(self) -> None:
        """Enter on the last column."""
        raise NotImplementedError

    def set_column(
        self,
        column: int,
        title: str,
        entries: list[tuple[str, Any]],
        *,
        empty: str = "",
        current: Any = NOTHING,
    ) -> None:
        """Show ``entries`` (prompt, value) in a column and refill the next.

        ``current`` is highlighted when present, the first entry otherwise;
        None is a real value (the «Sin equipo» rows), so pass NOTHING rather
        than None to mean no preference. ``empty`` is shown, and selects
        nothing, when there are no entries.
        """
        self._filled_for[column] = self.value(column - 1) if column else NOTHING
        self.query_one(f"#column-title-{column}", Label).update(title)
        option_list = self.column_list(column)
        option_list.clear_options()
        self._values[column] = [value for _prompt, value in entries]
        for prompt, _value in entries:
            option_list.add_option(Option(prompt))
        if not entries:
            if empty:
                option_list.add_option(Option(f"[dim]{empty}[/dim]"))
        else:
            values = self._values[column]
            option_list.highlighted = values.index(current) if current in values else 0
        if column + 1 < self.COLUMN_COUNT:
            self.fill(column + 1)

    def value(self, column: int) -> Any:
        """Value highlighted in a column, or NOTHING."""
        index = self.column_list(column).highlighted
        values = self._values[column]
        if index is None or not (0 <= index < len(values)):
            return NOTHING
        return values[index]

    def kept(self, column: int, default: Any) -> Any:
        """The value highlighted now, so a refill does not move the cursor.

        Only while the column still lists the same parent: after moving to
        another station, its antennas start from ``default``.
        """
        parent = self.value(column - 1) if column else NOTHING
        current = self.value(column)
        if current is NOTHING or parent != self._filled_for[column]:
            return default
        return current

    def column_list(self, column: int) -> OptionList:
        return self.query_one(f"#column-{column}", OptionList)

    @property
    def column(self) -> int:
        """Column holding the keyboard."""
        return self._column

    def refresh_columns(self) -> None:
        """Reload everything, keeping the highlights where they were."""
        self.fill(0)

    # -------------------------------------------------------- navigation --
    def _focus_column(self, column: int) -> None:
        self._column = column
        self.column_list(column).focus()
        self.set_keys(self.help_for(column))

    def action_next_column(self) -> None:
        if self._column + 1 < self.COLUMN_COUNT and self.value(self._column) is not NOTHING:
            self._focus_column(self._column + 1)

    def action_previous_column(self) -> None:
        if self._column > 0:
            self._focus_column(self._column - 1)

    @on(OptionList.OptionHighlighted)
    def _on_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        column = self._column_of(event.option_list)
        if column is not None and column + 1 < self.COLUMN_COUNT:
            self.fill(column + 1)

    @on(OptionList.OptionSelected)
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        column = self._column_of(event.option_list)
        if column is None or self.value(column) is NOTHING:
            return
        if column + 1 < self.COLUMN_COUNT:
            self._focus_column(column + 1)
        else:
            self.activate()

    def _column_of(self, option_list: OptionList) -> int | None:
        widget_id = option_list.id or ""
        if not widget_id.startswith("column-"):
            return None
        return int(widget_id.removeprefix("column-"))

    def action_cancel(self) -> None:
        self.dismiss(None)
