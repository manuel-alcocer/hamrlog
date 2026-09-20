"""Reusable modal screens.

Most shortcuts boil down to "pick one thing from a list" or "fill in a few
fields", so those two shapes are implemented once here and parameterised by
the callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option


@dataclass(frozen=True, slots=True)
class Choice:
    """One selectable entry of a SelectionScreen."""

    value: Any
    label: str
    detail: str = ""
    #: Extra words matched by the filter but not shown, e.g. a group name.
    search_extra: str = ""

    @property
    def search_text(self) -> str:
        return f"{self.label} {self.detail} {self.search_extra}".lower()


class SelectionScreen(ModalScreen[Any]):
    """Filterable list; dismisses with the chosen value or None."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("down", "focus_list", "Bajar", show=False),
    ]

    def __init__(
        self,
        title: str,
        choices: list[Choice],
        *,
        subtitle: str = "",
        current: Any = None,
        allow_filter: bool = True,
        wide: bool = False,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.subtitle_text = subtitle
        self.choices = choices
        self.current = current
        self.allow_filter = allow_filter
        #: Wider box for lists whose detail line needs the room.
        self.wide = wide
        self._visible: list[Choice] = list(choices)

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-wide-list" if self.wide else "modal"):
            yield Label(self.title_text, classes="modal-title")
            if self.subtitle_text:
                yield Static(self.subtitle_text, classes="modal-subtitle")
            if self.allow_filter:
                yield Input(placeholder="Escribe para filtrar...", id="filter")
            yield OptionList(id="choices")
            yield Static(
                "Enter selecciona · ↑↓ navega · Esc cancela", classes="modal-help"
            )

    def on_mount(self) -> None:
        self._refresh_options()
        if self.allow_filter:
            self.query_one("#filter", Input).focus()
        else:
            self.query_one("#choices", OptionList).focus()

    def _refresh_options(self, needle: str = "") -> None:
        """Rebuild the option list, applying the current filter."""
        option_list = self.query_one("#choices", OptionList)
        option_list.clear_options()

        needle = needle.strip().lower()
        self._visible = [c for c in self.choices if not needle or needle in c.search_text]

        highlighted = 0
        for index, choice in enumerate(self._visible):
            marker = "● " if choice.value == self.current else "  "
            prompt = f"{marker}{choice.label}"
            if choice.detail:
                prompt = f"{prompt}   [dim]{choice.detail}[/dim]"
            option_list.add_option(Option(prompt, id=str(index)))
            if choice.value == self.current:
                highlighted = index

        if self._visible:
            option_list.highlighted = highlighted

    @on(Input.Changed, "#filter")
    def _on_filter_changed(self, event: Input.Changed) -> None:
        self._refresh_options(event.value)

    @on(Input.Submitted, "#filter")
    def _on_filter_submitted(self) -> None:
        """Enter in the filter box picks the first (or highlighted) match."""
        option_list = self.query_one("#choices", OptionList)
        index = option_list.highlighted if option_list.highlighted is not None else 0
        if 0 <= index < len(self._visible):
            self.dismiss(self._visible[index].value)

    @on(OptionList.OptionSelected, "#choices")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = int(event.option.id) if event.option.id is not None else -1
        if 0 <= index < len(self._visible):
            self.dismiss(self._visible[index].value)

    def action_focus_list(self) -> None:
        self.query_one("#choices", OptionList).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no confirmation, defaulting to no.

    Three ways to answer, because a confirmation appears at the moment the
    operator is least willing to stop and think: the arrow keys move between
    the buttons as they are laid out, Tab cycles them, and S/N answer outright.
    """

    BINDINGS = [
        Binding("escape", "no", "No"),
        Binding("y", "yes", "Sí", show=False),
        Binding("s", "yes", "Sí", show=False),
        Binding("n", "no", "No", show=False),
        # Positional: Sí is drawn on the left, No on the right. Inputs consume
        # the arrows first, so these only fire once a button holds the focus.
        Binding("left", "focus_yes", "Sí", show=False),
        Binding("right", "focus_no", "No", show=False),
        Binding("up", "focus_yes", "Sí", show=False),
        Binding("down", "focus_no", "No", show=False),
    ]

    def __init__(self, question: str, *, detail: str = "", danger: bool = False) -> None:
        super().__init__()
        self.question = question
        self.detail = detail
        self.danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-small"):
            yield Label(self.question, classes="modal-title")
            if self.detail:
                yield Static(self.detail, classes="modal-subtitle")
            with Horizontal(classes="modal-buttons"):
                yield Button(
                    "Sí (S)", variant="error" if self.danger else "primary", id="yes"
                )
                yield Button("No (Esc)", variant="default", id="no")
            yield Static(
                "←→ elegir · Enter confirma · S sí · N o Esc no",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        # Defaults to No: a confirmation answered by reflex must not destroy
        # anything.
        self.query_one("#no", Button).focus()

    def action_focus_yes(self) -> None:
        self.query_one("#yes", Button).focus()

    def action_focus_no(self) -> None:
        self.query_one("#no", Button).focus()

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


@dataclass(slots=True)
class Field:
    """One input of a FormScreen.

    Attributes:
        key: Name the value is returned under.
        label: Prompt shown to the operator.
        value: Initial value.
        placeholder: Hint shown when empty.
        editable: False renders the value read-only, used by the QSO editor to
            show fields an automatic contact does not allow changing.
        kind: "text", "integer" or "datetime".
    """

    key: str
    label: str
    value: str = ""
    placeholder: str = ""
    editable: bool = True
    kind: str = "text"


class FormScreen(ModalScreen[dict[str, str] | None]):
    """Small vertical form; dismisses with a dict of values or None."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("ctrl+s", "save", "Guardar"),
        # Only reached once a button has the focus: the text fields use the
        # arrows to move the caret.
        Binding("left", "focus_save", "Guardar", show=False),
        Binding("right", "focus_cancel", "Cancelar", show=False),
    ]

    def __init__(
        self,
        title: str,
        fields: list[Field],
        *,
        subtitle: str = "",
        save_label: str = "Guardar",
    ) -> None:
        super().__init__()
        self.title_text = title
        self.subtitle_text = subtitle
        self.fields = fields
        self.save_label = save_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-form"):
            yield Label(self.title_text, classes="modal-title")
            if self.subtitle_text:
                yield Static(self.subtitle_text, classes="modal-subtitle")
            with VerticalScroll(classes="form-body"):
                for field in self.fields:
                    with Horizontal(classes="form-row"):
                        yield Label(field.label, classes="form-label")
                        if field.editable:
                            yield Input(
                                value=field.value,
                                placeholder=field.placeholder,
                                id=f"field-{field.key}",
                                classes="form-input",
                            )
                        else:
                            yield Static(
                                field.value or "-",
                                id=f"field-{field.key}",
                                classes="form-input form-readonly",
                            )
            yield Static("", id="form-error", classes="form-error")
            with Horizontal(classes="modal-buttons"):
                yield Button(f"{self.save_label} (Ctrl+S)", variant="primary", id="save")
                yield Button("Cancelar (Esc)", id="cancel")

    def on_mount(self) -> None:
        for field in self.fields:
            if field.editable:
                self.query_one(f"#field-{field.key}", Input).focus()
                break

    def action_focus_save(self) -> None:
        self.query_one("#save", Button).focus()

    def action_focus_cancel(self) -> None:
        self.query_one("#cancel", Button).focus()

    def show_error(self, message: str) -> None:
        self.query_one("#form-error", Static).update(message)

    def collect(self) -> dict[str, str]:
        """Current values of every editable field."""
        values: dict[str, str] = {}
        for field in self.fields:
            if not field.editable:
                continue
            values[field.key] = self.query_one(f"#field-{field.key}", Input).value.strip()
        return values

    @on(Input.Submitted)
    def _on_submitted(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#save")
    def action_save(self) -> None:
        self.dismiss(self.collect())

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
