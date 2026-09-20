"""Band, frequency and mode selectors (F2 to F5)."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...core import bands, modes
from .base import Choice, SelectionScreen


def band_screen(current: str) -> SelectionScreen:
    """F2: pick a band. Returns the ADIF band name."""
    choices = [
        Choice(value=band.name, label=f"{band.name:<7}", detail=band.label) for band in bands.BANDS
    ]
    return SelectionScreen(
        "F2 · Selector de banda",
        choices,
        subtitle="Al cambiar de banda se ajusta la frecuencia al centro de actividad.",
        current=current,
    )


#: Groups shown in the mode selector, in the order an operator thinks of them.
_MODE_GROUPS: tuple[tuple[str, tuple[modes.Mode, ...]], ...] = (
    ("analógico", modes.ANALOG_MODES),
    ("voz digital", modes.DIGITAL_VOICE_MODES),
    ("datos", modes.DATA_MODES),
)


def mode_screen(current: str) -> SelectionScreen:
    """F4: pick any mode, analogue or digital.

    One list rather than two: an operator choosing how to work thinks "mode",
    not "analogue mode or digital mode". The group name stays searchable, so
    typing "digital" or "datos" narrows the list to those.
    """
    choices: list[Choice] = []
    for group_label, group in _MODE_GROUPS:
        for mode in group:
            detail = f"{group_label} · {mode.adif_mode}"
            if mode.adif_submode:
                detail += f"/{mode.adif_submode}"
            extra = modes.short_fields(mode)
            if extra:
                detail += f" · pide {extra}"
            elif mode.default_rst:
                detail += f" · informe {mode.default_rst}"
            choices.append(
                Choice(
                    value=mode.name,
                    label=f"{mode.name:<9}",
                    detail=detail,
                    search_extra=group_label,
                )
            )
    return SelectionScreen(
        "F4 · Modo",
        choices,
        subtitle="Escribe para filtrar: «dmr», «digital», «datos», «cw»... "
        "Los modos digitales piden sus datos propios al elegirlos.",
        current=current,
        wide=True,
    )


class FrequencyScreen(ModalScreen[int | None]):
    """F3: type a frequency, with live band detection.

    Accepts MHz (14.250), kHz (7130) and Hz, with or without an explicit unit.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("ctrl+s", "save", "Aceptar"),
    ]

    def __init__(self, current_hz: int | None = None) -> None:
        super().__init__()
        self.current_hz = current_hz

    def compose(self) -> ComposeResult:
        initial = bands.format_frequency(self.current_hz) if self.current_hz else ""
        with Vertical(classes="modal modal-small"):
            yield Label("F3 · Frecuencia", classes="modal-title")
            yield Static(
                "Escribe en MHz (14.250), kHz (7130) o con unidad (433.500 MHz).",
                classes="modal-subtitle",
            )
            yield Input(value=initial, placeholder="14.250", id="freq")
            yield Static("", id="freq-preview", classes="modal-preview")
            with Horizontal(classes="modal-buttons"):
                yield Button("Aceptar (Enter)", variant="primary", id="save")
                yield Button("Cancelar (Esc)", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#freq", Input).focus()
        self._update_preview(self.query_one("#freq", Input).value)

    @on(Input.Changed, "#freq")
    def _on_changed(self, event: Input.Changed) -> None:
        self._update_preview(event.value)

    def _update_preview(self, text: str) -> None:
        """Show the parsed frequency and the band it falls in."""
        preview = self.query_one("#freq-preview", Static)
        freq_hz = bands.parse_frequency(text)
        if freq_hz is None:
            preview.update("[dim]Introduce una frecuencia[/dim]")
            return
        band = bands.from_frequency(freq_hz)
        rendered = bands.format_frequency(freq_hz)
        if band is None:
            preview.update(
                f"[yellow]{rendered} Hz — fuera de las bandas de radioaficionado[/yellow]"
            )
        else:
            preview.update(f"[green]{rendered} Hz[/green] → banda [bold]{band.name}[/bold]")

    @on(Input.Submitted, "#freq")
    @on(Button.Pressed, "#save")
    def action_save(self) -> None:
        freq_hz = bands.parse_frequency(self.query_one("#freq", Input).value)
        if freq_hz is None:
            self.query_one("#freq-preview", Static).update(
                "[red]No se reconoce esa frecuencia[/red]"
            )
            return
        self.dismiss(freq_hz)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
