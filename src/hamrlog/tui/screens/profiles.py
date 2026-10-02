"""Alt+P: stations, their antennas and the configurations for each.

Three columns, like a file manager: stations, the antennas connected to the
highlighted one, and the configurations of that station on the antenna's
bands. The right arrow steps in, the left arrow steps back and Enter loads the
three at once, so the rig, the antenna and what is tuned change together.

A configuration is a snapshot of the working setup (band, frequency, mode,
digital data, repeater and fast entry layout). Configurations are shared: the
same one can be assigned to several stations, and they are managed as a whole
in Alt+C → Configuraciones.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core import bands
from ...core.services import AntennaService, ProfileService, ServiceError, StationService
from ...core.state import SessionState
from ...db.models import Profile, Station
from .base import Choice, ConfirmScreen, Field, FormScreen, PanelScreen, SelectionScreen
from .columns import NOTHING, ColumnScreen


@dataclass(frozen=True, slots=True)
class ProfilePick:
    """What the operator did in Alt+P.

    Attributes:
        action: "load" or "saved".
        profile_id: The configuration loaded or saved.
        station_id: The station it was picked under, None for the
            configurations no station has.
        antenna_id: The antenna it was picked under, None for none.
    """

    action: str
    profile_id: int
    station_id: int | None
    antenna_id: int | None = None


def describe(profile: Profile) -> str:
    """Band, frequency, mode and digital data of a configuration."""
    parts = [
        profile.band or "",
        bands.format_frequency(profile.freq_hz) if profile.freq_hz else "",
        profile.mode or "",
    ]
    if profile.repeater is not None:
        parts.append(f"vía {profile.repeater.callsign}")
    return " · ".join(part for part in parts if part)


def summarize_state(state: SessionState) -> str:
    """One line describing what saving the current setup would store."""
    parts = [
        state.band or "sin banda",
        bands.format_frequency(state.freq_hz),
        state.mode or "sin modo",
    ]
    if state.digital_data:
        parts.append(" ".join(f"{k}={v}" for k, v in sorted(state.digital_data.items()) if v))
    return "Configuración actual: " + " · ".join(part for part in parts if part)


def suggest_name(state: SessionState) -> str:
    """Propose a configuration name from the current band and mode."""
    parts = [part for part in (state.band, state.mode) if part]
    return " ".join(parts) if parts else "configuración"


class ProfileScreen(ColumnScreen):
    """Pick a station, one of its antennas, then a configuration."""

    TITLE_TEXT = "Alt+P · Perfiles"
    COLUMN_COUNT = 3

    BINDINGS = [
        *ColumnScreen.BINDINGS,
        Binding("g", "save_new", "Guardar actual"),
        Binding("s", "overwrite", "Sobrescribir"),
        Binding("a", "assign", "Asignar"),
        Binding("delete", "unassign", "Quitar"),
    ]

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        #: Profiles shown in the last column, by id, for the key actions.
        self._profiles: dict[int, Profile] = {}

    # ------------------------------------------------------------ columns --
    def fill(self, column: int) -> None:
        if column == 0:
            entries = []
            for station in StationService.list_all():
                marker = "● " if station.id == self.state.station_id else "  "
                types = f"  [dim]{station.type_names}[/dim]" if station.types else ""
                entries.append((f"{marker}{station.name}{types}", station.id))
            entries.append(("[dim]  Sin equipo[/dim]", None))
            in_use = self.state.station_id if self.state.station_id is not None else NOTHING
            self.set_column(0, "Equipo", entries, current=self.kept(0, in_use))
            return

        station = self._station()
        if column == 1:
            self._fill_antennas(station)
        else:
            self._fill_profiles(station)

    def _fill_antennas(self, station: Station | None) -> None:
        if station is None:
            self.set_column(1, "Antenas", [("[dim]  Sin antena[/dim]", None)])
            return
        entries = []
        # The antenna in use is only a default under the station in use.
        default = NOTHING
        if station.id == self.state.station_id and self.state.antenna_id is not None:
            default = self.state.antenna_id
        for antenna in station.antennas:
            marker = "● " if antenna.id == default else "  "
            entries.append((f"{marker}{antenna.name}  [dim]{antenna.band_names}[/dim]", antenna.id))
        entries.append(("[dim]  Sin antena[/dim]", None))
        self.set_column(
            1, "Antenas", entries, current=self.kept(1, default)
        )

    def _fill_profiles(self, station: Station | None) -> None:
        antenna_id = self.value(1)
        antenna_id = None if antenna_id is NOTHING else antenna_id
        if station is None:
            profiles = ProfileService.unassigned()
        else:
            profiles = ProfileService.for_station(station.id, antenna_id)
        self._profiles = {profile.id: profile for profile in profiles}

        entries = []
        current = NOTHING
        for profile in profiles:
            marker = "● " if profile.name == self.state.profile_name else "  "
            detail = describe(profile)
            if station is not None and not station.covers(profile.freq_hz):
                detail += " [yellow]· fuera de sus tipos[/yellow]"
            entries.append((f"{marker}{profile.name}  [dim]{detail}[/dim]", profile.id))
            if profile.name == self.state.profile_name:
                current = profile.id
        self.set_column(2, "Configuraciones", entries, current=self.kept(2, current))

    def help_for(self, column: int) -> str:
        if column == 0:
            return "→ antenas · G guardar la actual · Esc salir"
        if column == 1:
            return "→ configuraciones · ← equipo · Esc salir"
        return (
            "Enter cargar · ← antenas · G guardar la actual · S sobrescribir · "
            "A asignar · Supr quitar · Esc salir"
        )

    def _station(self) -> Station | None:
        station_id = self.value(0)
        if station_id in (None, NOTHING):
            return None
        return StationService.get(station_id)

    def _antenna_id(self) -> int | None:
        antenna_id = self.value(1)
        return None if antenna_id is NOTHING else antenna_id

    def _current_profile(self) -> Profile | None:
        if self.column != 2:
            return None
        return self._profiles.get(self.value(2))

    def activate(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        station = self._station()
        self.dismiss(
            ProfilePick(
                "load",
                profile.id,
                station.id if station else None,
                self._antenna_id() if station else None,
            )
        )

    # ------------------------------------------------------------ actions --
    def action_save_new(self) -> None:
        station = self._station()
        antenna_id = self._antenna_id() if station else None
        where = f" en «{station.name}»" if station else ""
        self.app.push_screen(
            FormScreen(
                f"Guardar la configuración actual{where}",
                [
                    Field(
                        "name",
                        "Nombre",
                        self.state.profile_name or suggest_name(self.state),
                        placeholder="Terminal Mode INT",
                    )
                ],
                subtitle=summarize_state(self.state),
            ),
            lambda values: self._save_new(station, antenna_id, values),
        )

    def _save_new(
        self, station: Station | None, antenna_id: int | None, values: dict[str, str] | None
    ) -> None:
        if not values or not values.get("name"):
            return
        station_id = station.id if station else None
        try:
            profile = ProfileService.save_from_state(
                values["name"], self.state, station_id=station_id, antenna_id=antenna_id
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.dismiss(ProfilePick("saved", profile.id, station_id, antenna_id))

    def action_overwrite(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        detail = summarize_state(self.state)
        if len(profile.stations) > 1:
            names = ", ".join(station.name for station in profile.stations)
            detail += f"\nLa usan también otros equipos: {names}."
        self.app.push_screen(
            ConfirmScreen(f"¿Sobrescribir «{profile.name}»?", detail=detail),
            lambda confirmed: self._overwrite(profile.name, confirmed),
        )

    def _overwrite(self, name: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            ProfileService.save_from_state(name, self.state, overwrite=True)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.app.notify(f"Configuración «{name}» actualizada.", severity="information")
        self.refresh_columns()

    def action_assign(self) -> None:
        station = self._station()
        if station is None:
            return
        antenna = AntennaService.get(self._antenna_id()) if self._antenna_id() else None
        assigned = {profile.id for profile in ProfileService.for_station(station.id)}
        candidates = [
            profile
            for profile in ProfileService.list_all()
            if profile.id not in assigned
            and station.covers(profile.freq_hz)
            and (antenna is None or antenna.covers_band(profile.band))
        ]
        if not candidates:
            self.app.notify(
                f"No quedan configuraciones que «{station.name}» pueda usar"
                + (f" con «{antenna.name}»" if antenna else "")
                + ". G guarda la actual.",
                severity="warning",
            )
            return
        self.app.push_screen(
            SelectionScreen(
                f"Asignar a «{station.name}»",
                [Choice(value=p.id, label=p.name, detail=describe(p)) for p in candidates],
            ),
            lambda profile_id: self._assign(station.id, profile_id),
        )

    def _assign(self, station_id: int, profile_id: object) -> None:
        if profile_id is None:
            return
        try:
            ProfileService.assign(int(profile_id), station_id)  # type: ignore[arg-type]
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.refresh_columns()

    def action_unassign(self) -> None:
        station = self._station()
        profile = self._current_profile()
        if station is None or profile is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Quitar «{profile.name}» de «{station.name}»?",
                detail="La configuración no se borra: sigue en los demás equipos y "
                "en Alt+C → Configuraciones.",
            ),
            lambda confirmed: self._unassign(profile.id, station.id, confirmed),
        )

    def _unassign(self, profile_id: int, station_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        ProfileService.unassign(profile_id, station_id)
        self.refresh_columns()


class ConfigurationsScreen(PanelScreen[None]):
    """Every configuration, whichever station it is assigned to."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("g", "save_new", "Guardar actual"),
        Binding("s", "overwrite", "Sobrescribir"),
        Binding("r", "rename", "Renombrar"),
        Binding("d", "make_default", "Por defecto"),
        Binding("delete", "remove", "Borrar"),
    ]

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        self._profiles: list[Profile] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Configuraciones", classes="modal-title")
            yield OptionList(id="configurations")
            yield Static(
                "G guarda la actual · S sobrescribe · R renombra · D por defecto al "
                "arrancar · Supr borra · Esc cierra",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#configurations", OptionList).focus()

    def _reload(self) -> None:
        option_list = self.query_one("#configurations", OptionList)
        previous = option_list.highlighted or 0
        option_list.clear_options()
        self._profiles = ProfileService.list_all()
        for profile in self._profiles:
            flag = "★ " if profile.is_default else "  "
            used_by = ", ".join(station.name for station in profile.stations) or "sin equipo"
            option_list.add_option(
                Option(
                    f"{flag}{profile.name}   [dim]{describe(profile)} · {used_by}[/dim]"
                )
            )
        if not self._profiles:
            option_list.add_option(
                Option("[dim]No hay configuraciones. G guarda la actual.[/dim]")
            )
            return
        option_list.highlighted = min(previous, len(self._profiles) - 1)

    def _selected(self) -> Profile | None:
        index = self.query_one("#configurations", OptionList).highlighted
        if index is None or not (0 <= index < len(self._profiles)):
            return None
        return self._profiles[index]

    def action_save_new(self) -> None:
        self.app.push_screen(
            FormScreen(
                "Guardar la configuración actual",
                [Field("name", "Nombre", suggest_name(self.state))],
                subtitle=summarize_state(self.state),
            ),
            self._save_new,
        )

    def _save_new(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("name"):
            return
        try:
            ProfileService.save_from_state(values["name"], self.state)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_overwrite(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Sobrescribir «{profile.name}»?", detail=summarize_state(self.state)
            ),
            lambda confirmed: self._overwrite(profile.name, confirmed),
        )

    def _overwrite(self, name: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            ProfileService.save_from_state(name, self.state, overwrite=True)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    def action_rename(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        self.app.push_screen(
            FormScreen(
                f"Renombrar «{profile.name}»", [Field("name", "Nombre", profile.name)]
            ),
            lambda values: self._rename(profile.id, values),
        )

    def _rename(self, profile_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            profile = ProfileService.rename(profile_id, values["name"])
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()
        self.app.notify(f"Ahora se llama «{profile.name}».", severity="information")

    def action_make_default(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        ProfileService.set_default(profile.id)
        self._reload()

    def action_remove(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        detail = ""
        if profile.stations:
            names = ", ".join(station.name for station in profile.stations)
            detail = f"Desaparecerá también de: {names}."
        self.app.push_screen(
            ConfirmScreen(f"¿Borrar «{profile.name}»?", detail=detail, danger=True),
            lambda confirmed: self._delete(profile.id, confirmed),
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

    def action_close(self) -> None:
        self.dismiss(None)
