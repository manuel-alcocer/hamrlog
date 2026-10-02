"""Alt+E: stations and their antennas; also the station types and antennas lists."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core import bands
from ...core.services import (
    AntennaService,
    ServiceError,
    StationService,
    StationTypeService,
)
from ...db.models import Antenna, Station
from .base import Choice, ConfirmScreen, Field, FormScreen, PanelScreen, SelectionScreen
from .columns import NOTHING, ColumnScreen


@dataclass(frozen=True, slots=True)
class StationPick:
    """The station chosen in Alt+E and the antenna connected to it.

    ``station_id`` None means working with no station at all.
    """

    station_id: int | None
    antenna_id: int | None


class StationScreen(ColumnScreen):
    """Pick the station and its antenna; create, edit and delete stations.

    Dismisses with a StationPick, or None when cancelled.
    """

    TITLE_TEXT = "Alt+E · Equipo"
    COLUMN_COUNT = 2

    BINDINGS = [
        *ColumnScreen.BINDINGS,
        Binding("n", "new", "Nuevo"),
        Binding("e", "edit", "Editar"),
        Binding("a", "assign", "Asignar antena"),
        Binding("delete", "remove", "Borrar"),
        Binding("0", "clear_station", "Ninguno"),
    ]

    def __init__(self, current: int | None = None, antenna: int | None = None) -> None:
        super().__init__()
        self.current = current
        self.current_antenna = antenna

    def fill(self, column: int) -> None:
        if column == 0:
            entries = []
            for station in StationService.list_all():
                marker = "● " if station.id == self.current else "  "
                types = f"  [dim]{station.type_names}[/dim]" if station.types else ""
                entries.append((f"{marker}{station.name}{types}", station.id))
            self.set_column(
                0,
                "Equipo",
                entries,
                empty="No hay equipos. N crea uno.",
                current=self.kept(0, self.current if self.current is not None else NOTHING),
            )
            return

        station_id = self.value(0)
        station = StationService.get(station_id) if station_id is not NOTHING else None
        if station is None:
            self.set_column(1, "Antenas", [])
            return
        # The antenna in use is only a default under the station in use.
        default = NOTHING
        if station.id == self.current and self.current_antenna is not None:
            default = self.current_antenna
        entries = [
            (
                f"{'● ' if a.id == default else '  '}{a.name}  [dim]{a.band_names}[/dim]",
                a.id,
            )
            for a in station.antennas
        ]
        entries.append(("[dim]  Sin antena[/dim]", None))
        self.set_column(
            1, "Antenas", entries, current=self.kept(1, default)
        )

    def help_for(self, column: int) -> str:
        if column == 0:
            return "→ antenas · N nuevo · E editar · Supr borrar · 0 ninguno · Esc salir"
        return "Enter elegir · ← equipo · A asignar antena · Supr quitar · Esc salir"

    def activate(self) -> None:
        self.dismiss(StationPick(self.value(0), self.value(1)))

    def action_clear_station(self) -> None:
        self.dismiss(StationPick(None, None))

    # ------------------------------------------------------------ stations --
    def _station(self) -> Station | None:
        station_id = self.value(0)
        return StationService.get(station_id) if station_id is not NOTHING else None

    def action_new(self) -> None:
        if self.column != 0:
            return
        fields = [
            Field("name", "Nombre", placeholder="ICOM IC-705"),
            Field("rig", "Emisora", placeholder="IC-705"),
            Field("power_w", "Potencia (W)", placeholder="10", kind="integer"),
            _types_field(""),
            Field("notes", "Notas"),
        ]
        self.app.push_screen(
            FormScreen("Nuevo equipo", fields), self._create
        )

    def _create(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            StationService.create(
                name=values["name"],
                rig=values["rig"],
                power_w=_as_int(values["power_w"]),
                notes=values["notes"],
                type_ids=StationTypeService.resolve(values["types"]),
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.refresh_columns()

    def action_edit(self) -> None:
        station = self._station() if self.column == 0 else None
        if station is None:
            return
        fields = [
            Field("name", "Nombre", station.name),
            Field("rig", "Emisora", station.rig),
            Field("power_w", "Potencia (W)", str(station.power_w or ""), kind="integer"),
            _types_field(station.type_names),
            Field("notes", "Notas", station.notes),
        ]
        self.app.push_screen(
            FormScreen(f"Editar equipo · {station.name}", fields),
            lambda values: self._update(station.id, values),
        )

    def _update(self, station_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            StationService.update(
                station_id,
                name=values["name"],
                rig=values["rig"],
                power_w=_as_int(values["power_w"]),
                notes=values["notes"],
                type_ids=StationTypeService.resolve(values["types"]),
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.refresh_columns()

    def action_remove(self) -> None:
        if self.column == 1:
            self._unassign()
            return
        station = self._station()
        if station is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar el equipo «{station.name}»?",
                detail="Los contactos ya registrados se conservan, pero dejarán de "
                "tener equipo asociado. Sus antenas no se borran.",
                danger=True,
            ),
            lambda confirmed: self._delete(station.id, confirmed),
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
        self.refresh_columns()

    # ------------------------------------------------------------ antennas --
    def action_assign(self) -> None:
        station = self._station()
        if station is None:
            return
        mine = {antenna.id for antenna in station.antennas}
        candidates = [a for a in AntennaService.list_all() if a.id not in mine]
        if not candidates:
            self.app.notify(
                "No quedan antenas por asignar. Se crean en Alt+C → Antenas.",
                severity="warning",
            )
            return
        self.app.push_screen(
            SelectionScreen(
                f"Asignar una antena a «{station.name}»",
                [Choice(value=a.id, label=a.name, detail=a.band_names) for a in candidates],
            ),
            lambda antenna_id: self._assign(station.id, antenna_id),
        )

    def _assign(self, station_id: int, antenna_id: object) -> None:
        if antenna_id is None:
            return
        StationService.assign_antenna(station_id, int(antenna_id))  # type: ignore[arg-type]
        self.refresh_columns()

    def _unassign(self) -> None:
        station = self._station()
        antenna_id = self.value(1)
        if station is None or antenna_id in (None, NOTHING):
            return
        antenna = AntennaService.get(antenna_id)
        if antenna is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Quitar «{antenna.name}» de «{station.name}»?",
                detail="La antena no se borra: sigue en los demás equipos y en "
                "Alt+C → Antenas.",
            ),
            lambda confirmed: self._do_unassign(station.id, antenna.id, confirmed),
        )

    def _do_unassign(self, station_id: int, antenna_id: int, confirmed: bool | None) -> None:
        if confirmed:
            StationService.unassign_antenna(station_id, antenna_id)
            self.refresh_columns()


def _types_field(value: str) -> Field:
    # The placeholder lists the types that exist: the field takes them by name.
    known = ", ".join(t.name for t in StationTypeService.list_all())
    return Field("types", "Tipos", value, placeholder=known or "HF, VHF, UHF")


def _format_range(min_hz: int, max_hz: int) -> str:
    return f"{bands.format_frequency(min_hz)} – {bands.format_frequency(max_hz)}"


class StationTypesScreen(PanelScreen[None]):
    """Create, edit and delete station types and their frequency range."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("n", "new", "Nuevo"),
        Binding("e", "edit", "Editar"),
        Binding("delete", "remove", "Borrar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Tipos de equipo", classes="modal-title")
            yield OptionList(id="types")
            yield Static(
                "N nuevo · E o Enter editar · Supr borrar · Esc cierra",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#types", OptionList).focus()

    def _reload(self) -> None:
        option_list = self.query_one("#types", OptionList)
        highlighted = option_list.highlighted or 0
        option_list.clear_options()
        self._ids = []
        for station_type in StationTypeService.list_all():
            option_list.add_option(
                Option(
                    f"  {station_type.name:<10} "
                    f"[dim]{_format_range(station_type.min_hz, station_type.max_hz)}[/dim]"
                )
            )
            self._ids.append(station_type.id)
        if not self._ids:
            option_list.add_option(Option("[dim]No hay tipos. Pulsa N para crear uno.[/dim]"))
            return
        option_list.highlighted = min(highlighted, len(self._ids) - 1)

    def _selected_id(self) -> int | None:
        index = self.query_one("#types", OptionList).highlighted
        if index is None or not (0 <= index < len(self._ids)):
            return None
        return self._ids[index]

    @on(OptionList.OptionSelected, "#types")
    def _on_selected(self) -> None:
        self.action_edit()

    def _form(self, title: str, name: str, low: str, high: str) -> FormScreen:
        return FormScreen(
            title,
            [
                Field("name", "Nombre", name, placeholder="6m"),
                Field("min", "Frecuencia mínima", low, placeholder="50 M"),
                Field("max", "Frecuencia máxima", high, placeholder="54 M"),
            ],
        )

    def action_new(self) -> None:
        self.app.push_screen(self._form("Nuevo tipo de equipo", "", "", ""), self._create)

    def _create(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            StationTypeService.create(
                values["name"],
                bands.parse_frequency(values["min"]),
                bands.parse_frequency(values["max"]),
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_edit(self) -> None:
        type_id = self._selected_id()
        station_type = StationTypeService.get(type_id) if type_id is not None else None
        if station_type is None:
            return
        form = self._form(
            f"Editar tipo · {station_type.name}",
            station_type.name,
            bands.format_frequency(station_type.min_hz),
            bands.format_frequency(station_type.max_hz),
        )
        self.app.push_screen(form, lambda values: self._update(station_type.id, values))

    def _update(self, type_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            StationTypeService.update(
                type_id,
                values["name"],
                bands.parse_frequency(values["min"]),
                bands.parse_frequency(values["max"]),
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_remove(self) -> None:
        type_id = self._selected_id()
        station_type = StationTypeService.get(type_id) if type_id is not None else None
        if station_type is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar el tipo «{station_type.name}»?",
                detail="Los equipos que lo tengan dejarán de tenerlo.",
                danger=True,
            ),
            lambda confirmed: self._delete(station_type.id, confirmed),
        )

    def _delete(self, type_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            StationTypeService.delete(type_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_close(self) -> None:
        self.dismiss(None)


class AntennasScreen(PanelScreen[None]):
    """Create, edit and delete antennas and the bands they work on."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("n", "new", "Nueva"),
        Binding("e", "edit", "Editar"),
        Binding("delete", "remove", "Borrar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Antenas", classes="modal-title")
            yield OptionList(id="antennas")
            yield Static(
                "N nueva · E o Enter editar · Supr borrar · Esc cierra",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#antennas", OptionList).focus()

    def _reload(self) -> None:
        option_list = self.query_one("#antennas", OptionList)
        highlighted = option_list.highlighted or 0
        option_list.clear_options()
        self._ids = []
        for antenna in AntennaService.list_all():
            bands_text = antenna.band_names or "bandas sin indicar"
            option_list.add_option(Option(f"  {antenna.name:<28} [dim]{bands_text}[/dim]"))
            self._ids.append(antenna.id)
        if not self._ids:
            option_list.add_option(Option("[dim]No hay antenas. Pulsa N para crear una.[/dim]"))
            return
        option_list.highlighted = min(highlighted, len(self._ids) - 1)

    def _selected(self) -> Antenna | None:
        index = self.query_one("#antennas", OptionList).highlighted
        if index is None or not (0 <= index < len(self._ids)):
            return None
        return AntennaService.get(self._ids[index])

    @on(OptionList.OptionSelected, "#antennas")
    def _on_selected(self) -> None:
        self.action_edit()

    def _form(self, title: str, antenna: Antenna | None) -> FormScreen:
        return FormScreen(
            title,
            [
                Field(
                    "name", "Nombre", antenna.name if antenna else "",
                    placeholder="Diamond X300N",
                ),
                Field(
                    "bands", "Bandas", antenna.band_names if antenna else "",
                    placeholder="2m, 70cm",
                ),
                Field("notes", "Notas", antenna.notes if antenna else ""),
            ],
        )

    def action_new(self) -> None:
        self.app.push_screen(self._form("Nueva antena", None), self._create)

    def _create(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            AntennaService.create(
                values["name"], AntennaService.resolve_bands(values["bands"]), values["notes"]
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_edit(self) -> None:
        antenna = self._selected()
        if antenna is None:
            return
        self.app.push_screen(
            self._form(f"Editar antena · {antenna.name}", antenna),
            lambda values: self._update(antenna.id, values),
        )

    def _update(self, antenna_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            AntennaService.update(
                antenna_id,
                values["name"],
                AntennaService.resolve_bands(values["bands"]),
                values["notes"],
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_remove(self) -> None:
        antenna = self._selected()
        if antenna is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar la antena «{antenna.name}»?",
                detail="Se quita de todos los equipos. Los contactos ya registrados "
                "se conservan, pero dejarán de tener antena asociada.",
                danger=True,
            ),
            lambda confirmed: self._delete(antenna.id, confirmed),
        )

    def _delete(self, antenna_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            AntennaService.delete(antenna_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_close(self) -> None:
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
