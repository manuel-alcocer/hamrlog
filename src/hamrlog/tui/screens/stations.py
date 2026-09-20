"""F6: station manager (rig plus antenna)."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core.services import ServiceError, StationService
from .base import ConfirmScreen, Field, FormScreen


class StationScreen(ModalScreen[int | None]):
    """Pick the station in use, or create, edit and delete stations.

    Dismisses with the selected station id, 0 to mean "no station", or None
    when cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("n", "new", "Nuevo"),
        Binding("e", "edit", "Editar"),
        Binding("delete", "remove", "Borrar"),
        Binding("0", "clear_station", "Ninguno"),
    ]

    def __init__(self, current: int | None = None) -> None:
        super().__init__()
        self.current = current
        self._ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("F6 · Equipo (emisora y antena)", classes="modal-title")
            yield Static(
                "El equipo se guarda en cada contacto y se exporta como MY_RIG / MY_ANTENNA.",
                classes="modal-subtitle",
            )
            yield OptionList(id="stations")
            yield Static(
                "Enter selecciona · N nuevo · E editar · Supr borrar · 0 ninguno · Esc cancela",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#stations", OptionList).focus()

    def _reload(self) -> None:
        option_list = self.query_one("#stations", OptionList)
        option_list.clear_options()
        self._ids = []
        for station in StationService.list_all():
            marker = "● " if station.id == self.current else "  "
            detail = station.summary
            option_list.add_option(Option(f"{marker}{station.name:<18} [dim]{detail}[/dim]"))
            self._ids.append(station.id)
        if not self._ids:
            option_list.add_option(Option("[dim]No hay equipos. Pulsa N para crear uno.[/dim]"))
            return
        # Highlight something so the first Enter always selects.
        option_list.highlighted = (
            self._ids.index(self.current) if self.current in self._ids else 0
        )

    def _selected_id(self) -> int | None:
        index = self.query_one("#stations", OptionList).highlighted
        if index is None or not (0 <= index < len(self._ids)):
            return None
        return self._ids[index]

    @on(OptionList.OptionSelected, "#stations")
    def _on_selected(self) -> None:
        station_id = self._selected_id()
        if station_id is not None:
            self.dismiss(station_id)

    def action_clear_station(self) -> None:
        self.dismiss(0)

    def action_new(self) -> None:
        fields = [
            Field("name", "Nombre", placeholder="HF-Casa"),
            Field("rig", "Emisora", placeholder="IC-7300"),
            Field("antenna", "Antena", placeholder="Dipolo G5RV"),
            Field("power_w", "Potencia (W)", placeholder="100", kind="integer"),
            Field("notes", "Notas"),
        ]
        self.app.push_screen(FormScreen("Nuevo equipo", fields), self._create)

    def _create(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            StationService.create(
                name=values["name"],
                rig=values["rig"],
                antenna=values["antenna"],
                power_w=_as_int(values["power_w"]),
                notes=values["notes"],
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_edit(self) -> None:
        station_id = self._selected_id()
        if station_id is None:
            return
        station = StationService.get(station_id)
        if station is None:
            return
        fields = [
            Field("name", "Nombre", station.name),
            Field("rig", "Emisora", station.rig),
            Field("antenna", "Antena", station.antenna),
            Field("power_w", "Potencia (W)", str(station.power_w or ""), kind="integer"),
            Field("notes", "Notas", station.notes),
        ]
        self.app.push_screen(
            FormScreen(f"Editar equipo · {station.name}", fields),
            lambda values: self._update(station_id, values),
        )

    def _update(self, station_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            StationService.update(
                station_id,
                name=values["name"],
                rig=values["rig"],
                antenna=values["antenna"],
                power_w=_as_int(values["power_w"]),
                notes=values["notes"],
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_remove(self) -> None:
        station_id = self._selected_id()
        if station_id is None:
            return
        station = StationService.get(station_id)
        if station is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar el equipo «{station.name}»?",
                detail="Los contactos ya registrados se conservan, pero dejarán de "
                "tener equipo asociado.",
                danger=True,
            ),
            lambda confirmed: self._delete(station_id, confirmed),
        )

    def _delete(self, station_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            StationService.delete(station_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        if self.current == station_id:
            self.current = None
        self._reload()

    def action_cancel(self) -> None:
        self.dismiss(None)


def _as_int(text: str) -> int | None:
    """Parse an optional integer field, tolerating empty and decimal input."""
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None
