"""F9: repeater manager.

Selecting a repeater adopts everything it defines — output and input
frequencies, band, mode and digital parameters — so the operator can go back
to logging immediately. Choosing "direct" returns to simplex.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core import bands, modes, repeaters
from ...core.services import RepeaterService, ServiceError
from ...core.state import SessionState
from .base import ConfirmScreen, Field, FormScreen

#: Sentinel returned when the operator chooses to work direct.
DIRECT = 0


class RepeaterScreen(ModalScreen[int | None]):
    """Pick the repeater in use, or manage the list.

    Dismisses with the repeater id, ``DIRECT`` for simplex, or None when
    cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("n", "new", "Nuevo"),
        Binding("e", "edit", "Editar"),
        Binding("d", "direct", "Directo"),
        Binding("delete", "remove", "Borrar"),
        Binding("ctrl+d", "remove", "Borrar", priority=True),
    ]

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        self._ids: list[int] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-wide-list"):
            yield Label("F9 · Repetidor", classes="modal-title")
            yield Static("", id="repeater-current", classes="modal-subtitle")
            yield OptionList(id="repeaters")
            yield Static(
                "Enter selecciona · N nuevo · E editar · Supr borrar · D directo · Esc cancela",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        self._reload()
        self.query_one("#repeaters", OptionList).focus()

    def _refresh_current(self) -> None:
        if self.state.via_repeater:
            text = f"Sale por: [bold]{self.state.repeater_call}[/bold]"
            if self.state.freq_tx_hz:
                text += (
                    f"  ·  escucha {bands.format_frequency(self.state.freq_hz)}"
                    f"  ·  transmite {bands.format_frequency(self.state.freq_tx_hz)}"
                )
        else:
            text = "Sale por: [bold]directo[/bold] (simplex, sin repetidor)"
        self.query_one("#repeater-current", Static).update(text)

    def _reload(self) -> None:
        option_list = self.query_one("#repeaters", OptionList)
        option_list.clear_options()
        self._ids = []

        marker = "  " if self.state.via_repeater else "● "
        option_list.add_option(
            Option(f"{marker}{'DIRECTO':<11} [dim]Simplex, sin repetidor[/dim]")
        )
        self._ids.append(DIRECT)

        for repeater in RepeaterService.list_all():
            selected = "● " if repeater.id == self.state.repeater_id else "  "
            option_list.add_option(
                Option(f"{selected}{repeater.callsign:<11} [dim]{_summary(repeater)}[/dim]")
            )
            self._ids.append(repeater.id)

        if len(self._ids) == 1:
            option_list.add_option(
                Option("[dim]No hay repetidores dados de alta. Pulsa N para añadir uno.[/dim]")
            )
        option_list.highlighted = (
            self._ids.index(self.state.repeater_id)
            if self.state.repeater_id in self._ids
            else 0
        )
        self._refresh_current()

    def _selected_id(self) -> int | None:
        index = self.query_one("#repeaters", OptionList).highlighted
        if index is None or not (0 <= index < len(self._ids)):
            return None
        return self._ids[index]

    @on(OptionList.OptionSelected, "#repeaters")
    def _on_selected(self) -> None:
        repeater_id = self._selected_id()
        if repeater_id is not None:
            self.dismiss(repeater_id)

    def action_direct(self) -> None:
        self.dismiss(DIRECT)

    # ----------------------------------------------------------------- new --
    def action_new(self) -> None:
        self.app.push_screen(
            FormScreen(
                "Nuevo repetidor",
                _repeater_fields(),
                subtitle="El desplazamiento se calcula solo a partir de la banda "
                "si lo dejas vacío (-600 kHz en 2 m, -7,6 MHz en 70 cm).",
                save_label="Dar de alta",
            ),
            self._create,
        )

    def _create(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        parsed = _parse_form(values)
        if isinstance(parsed, str):
            self.app.notify(parsed, severity="error")
            return
        try:
            repeater = RepeaterService.create(values["callsign"], **parsed)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()
        self._ask_digital(repeater.id, repeater.mode)

    # ---------------------------------------------------------------- edit --
    def action_edit(self) -> None:
        repeater_id = self._selected_id()
        if not repeater_id:  # DIRECT has nothing to edit
            return
        repeater = RepeaterService.get(repeater_id)
        if repeater is None:
            return
        self.app.push_screen(
            FormScreen(
                f"Editar repetidor · {repeater.callsign}",
                _repeater_fields(repeater),
                subtitle=f"Entrada actual: {bands.format_frequency(repeater.input_hz)}",
            ),
            lambda values: self._update(repeater_id, values),
        )

    def _update(self, repeater_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        parsed = _parse_form(values)
        if isinstance(parsed, str):
            self.app.notify(parsed, severity="error")
            return
        try:
            repeater = RepeaterService.update(
                repeater_id, callsign=values["callsign"], **parsed
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()
        self._ask_digital(repeater.id, repeater.mode)

    def _ask_digital(self, repeater_id: int, mode_name: str) -> None:
        """Ask for the digital parameters the repeater's mode requires."""
        mode = modes.get(mode_name)
        if mode is None or not mode.digital_fields:
            return
        repeater = RepeaterService.get(repeater_id)
        current = dict(repeater.digital_data or {}) if repeater else {}
        fields = [
            Field(key, label, current.get(key, "")) for key, label in mode.digital_fields
        ]
        self.app.push_screen(
            FormScreen(
                f"Datos {mode.name} del repetidor",
                fields,
                subtitle="Se aplicarán a los contactos hechos por este repetidor.",
                save_label="Guardar",
            ),
            lambda values: self._save_digital(repeater_id, values),
        )

    def _save_digital(self, repeater_id: int, values: dict[str, str] | None) -> None:
        if values is None:
            return
        try:
            RepeaterService.update(
                repeater_id, digital_data={k: v for k, v in values.items() if v}
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._reload()

    # -------------------------------------------------------------- delete --
    def action_remove(self) -> None:
        repeater_id = self._selected_id()
        if not repeater_id:
            return
        repeater = RepeaterService.get(repeater_id)
        if repeater is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar el repetidor {repeater.callsign}?",
                detail="Los contactos hechos por él se conservan y siguen indicando "
                "su indicativo.",
                danger=True,
            ),
            lambda confirmed: self._delete(repeater_id, confirmed),
        )

    def _delete(self, repeater_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            RepeaterService.delete(repeater_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        if self.state.repeater_id == repeater_id:
            self.state.clear_repeater()
        self._reload()

    def action_cancel(self) -> None:
        self.dismiss(None)


def _summary(repeater) -> str:  # type: ignore[no-untyped-def]
    """One line describing a repeater, as shown in the list."""
    parts = [
        bands.format_frequency(repeater.output_hz),
        repeaters.format_shift(repeater.shift_hz),
    ]
    if repeater.ctcss_tx:
        parts.append(f"T{repeater.ctcss_tx}")
    if repeater.dcs:
        parts.append(f"DCS{repeater.dcs}")
    digital = repeater.digital_data or {}
    if digital.get("color_code"):
        parts.append(f"CC{digital['color_code']}")
    for key, prefix in (("talkgroup", "TG"), ("reflector", ""), ("room", "")):
        if digital.get(key):
            parts.append(f"{prefix}{digital[key]}")
    parts.append(repeater.mode or "FM")
    if repeater.qth:
        parts.append(repeater.qth)
    elif repeater.name:
        parts.append(repeater.name)
    return "  ".join(part for part in parts if part)


def _repeater_fields(repeater=None) -> list[Field]:  # type: ignore[no-untyped-def]
    """Form fields for creating or editing a repeater."""
    return [
        Field("callsign", "Indicativo", repeater.callsign if repeater else "",
              placeholder="ED7ZAE"),
        Field("name", "Nombre / ubicación", repeater.name if repeater else "",
              placeholder="Sevilla - Cerro del Águila"),
        Field("output_hz", "Frecuencia de salida",
              bands.format_frequency(repeater.output_hz) if repeater else "",
              placeholder="145.600 (la que sintonizas)"),
        Field("shift", "Desplazamiento",
              repeaters.format_shift(repeater.shift_hz) if repeater else "",
              placeholder="-600 kHz (vacío = el de la banda)"),
        Field("mode", "Modo", repeater.mode if repeater else "FM",
              placeholder="FM, C4FM, DMR, DSTAR"),
        Field("ctcss_tx", "Subtono CTCSS", repeater.ctcss_tx if repeater else "",
              placeholder="88.5"),
        Field("ctcss_rx", "Subtono de salida", repeater.ctcss_rx if repeater else "",
              placeholder="solo si es distinto"),
        Field("dcs", "DCS", repeater.dcs if repeater else "", placeholder="opcional"),
        Field("qth", "QTH", repeater.qth if repeater else ""),
        Field("gridsquare", "Locator", repeater.gridsquare if repeater else "",
              placeholder="IM76"),
        Field("notes", "Notas", repeater.notes if repeater else ""),
    ]


def _parse_form(values: dict[str, str]) -> dict[str, object] | str:
    """Validate and convert the repeater form.

    Returns:
        The keyword arguments for the service, or an error message.
    """
    output_hz = bands.parse_frequency(values.get("output_hz", ""))
    if output_hz is None:
        return "Falta la frecuencia de salida del repetidor."

    shift_text = values.get("shift", "").strip()
    if shift_text and not shift_text.startswith("simplex"):
        shift_hz = repeaters.parse_shift(shift_text)
        if shift_hz is None:
            return f"No se entiende el desplazamiento «{shift_text}»."
    elif shift_text.startswith("simplex"):
        shift_hz = 0
    else:
        shift_hz = None  # the service applies the band default

    mode_name = values.get("mode", "FM").strip() or "FM"
    if modes.get(mode_name) is None:
        return f"Modo desconocido: «{mode_name}»."

    tone = repeaters.normalize_tone(values.get("ctcss_tx", ""))
    if tone and not repeaters.is_standard_tone(tone):
        return f"«{tone}» no es un subtono CTCSS estándar."

    return {
        "name": values.get("name", ""),
        "output_hz": output_hz,
        "shift_hz": shift_hz,
        "mode": mode_name,
        "ctcss_tx": tone,
        "ctcss_rx": values.get("ctcss_rx", ""),
        "dcs": values.get("dcs", ""),
        "qth": values.get("qth", ""),
        "gridsquare": values.get("gridsquare", ""),
        "notes": values.get("notes", ""),
    }
