"""F7: profile manager.

A profile is a snapshot of the working configuration (operator, station, band,
frequency, mode, digital data and fast entry layout). Loading one puts the
operator straight back into a known setup.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core import bands
from ...core.services import ProfileService, ServiceError
from ...core.state import SessionState
from .base import ConfirmScreen, Field, FormScreen


class ProfileScreen(ModalScreen[tuple[str, int | None] | None]):
    """Load, save, overwrite and delete profiles.

    Dismisses with ``(action, profile_id)`` where action is "load" or
    "saved", so the application knows whether to refresh its state.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("g", "save_new", "Guardar actual"),
        Binding("s", "overwrite", "Sobrescribir"),
        Binding("d", "make_default", "Por defecto"),
        Binding("delete", "remove", "Borrar"),
    ]

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        self._ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("F7 · Perfiles", classes="modal-title")
            yield Static(self._current_summary(), classes="modal-subtitle")
            yield OptionList(id="profiles")
            yield Static(
                "Enter carga · G guarda la configuración actual · S sobrescribe · "
                "D marca por defecto · Supr borra · Esc cancela",
                classes="modal-help",
            )

    def _current_summary(self) -> str:
        """One line describing what pressing G would store."""
        parts = [
            self.state.band or "sin banda",
            bands.format_frequency(self.state.freq_hz),
            self.state.mode or "sin modo",
        ]
        if self.state.digital_data:
            parts.append(
                " ".join(f"{k}={v}" for k, v in sorted(self.state.digital_data.items()) if v)
            )
        return "Configuración actual: " + " · ".join(part for part in parts if part)

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#profiles", OptionList).focus()

    def _reload(self) -> None:
        option_list = self.query_one("#profiles", OptionList)
        option_list.clear_options()
        self._ids = []
        for profile in ProfileService.list_all():
            flags = "★ " if profile.is_default else "  "
            detail_parts = [
                profile.band or "-",
                bands.format_frequency(profile.freq_hz),
                profile.mode or "-",
            ]
            if profile.station is not None:
                detail_parts.append(profile.station.name)
            if profile.operator is not None:
                detail_parts.append(profile.operator.callsign)
            detail = " · ".join(part for part in detail_parts if part and part != "-")
            option_list.add_option(Option(f"{flags}{profile.name:<20} [dim]{detail}[/dim]"))
            self._ids.append(profile.id)
        if not self._ids:
            option_list.add_option(
                Option("[dim]No hay perfiles guardados. Pulsa G para guardar el actual.[/dim]")
            )
            return
        option_list.highlighted = 0

    def _selected_id(self) -> int | None:
        index = self.query_one("#profiles", OptionList).highlighted
        if index is None or not (0 <= index < len(self._ids)):
            return None
        return self._ids[index]

    @on(OptionList.OptionSelected, "#profiles")
    def _on_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id is not None:
            self.dismiss(("load", profile_id))

    def action_save_new(self) -> None:
        suggestion = self.state.profile_name or _suggest_name(self.state)
        self.app.push_screen(
            FormScreen(
                "Guardar configuración como perfil",
                [Field("name", "Nombre del perfil", suggestion, placeholder="HF-Casa-40m")],
                subtitle=self._current_summary(),
            ),
            self._save_new,
        )

    def _save_new(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("name"):
            return
        try:
            profile = ProfileService.save_from_state(values["name"], self.state)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.app.notify(f"Perfil «{profile.name}» guardado.", severity="information")
        self.dismiss(("saved", profile.id))

    def action_overwrite(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        profile = ProfileService.get(profile_id)
        if profile is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Sobrescribir el perfil «{profile.name}»?",
                detail=self._current_summary(),
            ),
            lambda confirmed: self._overwrite(profile.name, confirmed),
        )

    def _overwrite(self, name: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            profile = ProfileService.save_from_state(name, self.state, overwrite=True)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.app.notify(f"Perfil «{profile.name}» actualizado.", severity="information")
        self._reload()

    def action_make_default(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        try:
            ProfileService.set_default(profile_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_remove(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        profile = ProfileService.get(profile_id)
        if profile is None:
            return
        self.app.push_screen(
            ConfirmScreen(f"¿Borrar el perfil «{profile.name}»?", danger=True),
            lambda confirmed: self._delete(profile_id, confirmed),
        )

    def _delete(self, profile_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            ProfileService.delete(profile_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_cancel(self) -> None:
        self.dismiss(None)


def _suggest_name(state: SessionState) -> str:
    """Propose a profile name from the current band and mode."""
    parts = [part for part in (state.band, state.mode) if part]
    return "-".join(parts) if parts else "perfil"
