"""F9: log import and export (ADIF and CSV)."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ...core import transfer
from ...core.services import QsoService, ServiceError
from ...core.state import SessionState
from ...paths import export_dir
from .base import Choice, Field, FormScreen, SelectionScreen


class TransferScreen(ModalScreen[bool]):
    """Export and import menu. Dismisses True when the log changed."""

    BINDINGS = [Binding("escape", "close", "Cerrar")]

    _ACTIONS: tuple[tuple[str, str, str], ...] = (
        ("export_adif", "Exportar ADIF", "Formato estándar para LoTW, eQSL, QRZ y otros logs"),
        ("export_csv", "Exportar CSV", "Hoja de cálculo con separador ';'"),
        ("import_adif", "Importar ADIF", "Añade contactos desde un fichero .adi"),
        ("stats", "Estadísticas", "Resumen por banda, modo y país"),
    )

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        self._changed = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("Registro: importar y exportar", classes="modal-title")
            yield Static(
                f"Carpeta de exportación: [bold]{export_dir()}[/bold]", classes="modal-subtitle"
            )
            yield OptionList(id="actions")
            yield Static("", id="transfer-result", classes="modal-preview")
            yield Static("Enter ejecuta · Esc cierra", classes="modal-help")

    def on_mount(self) -> None:
        option_list = self.query_one("#actions", OptionList)
        for key, label, detail in self._ACTIONS:
            option_list.add_option(Option(f"  {label:<20} [dim]{detail}[/dim]", id=key))
        option_list.highlighted = 0
        option_list.focus()

    @on(OptionList.OptionSelected, "#actions")
    def _on_action(self, event: OptionList.OptionSelected) -> None:
        action = event.option.id
        if action == "export_adif":
            self._export("adi")
        elif action == "export_csv":
            self._export("csv")
        elif action == "import_adif":
            self._ask_import_path()
        elif action == "stats":
            self._show_stats()

    def _result(self, message: str) -> None:
        self.query_one("#transfer-result", Static).update(message)

    # -------------------------------------------------------------- export --
    def _export(self, extension: str) -> None:
        default = transfer.default_export_path(extension)
        self.app.push_screen(
            FormScreen(
                f"Exportar {extension.upper()}",
                [Field("path", "Fichero de destino", str(default))],
                subtitle="Se exporta el log completo.",
                save_label="Exportar",
            ),
            lambda values: self._run_export(extension, values),
        )

    def _run_export(self, extension: str, values: dict[str, str] | None) -> None:
        if not values or not values.get("path"):
            return
        self._export_worker(extension, values["path"])

    @work(thread=True)
    def _export_worker(self, extension: str, path: str) -> None:
        """Exports run in a thread: a large log would block the event loop."""
        try:
            if extension == "adi":
                target, count = transfer.export_adif(path)
            else:
                target, count = transfer.export_csv(path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            self.app.call_from_thread(self._result, f"[red]Error al exportar: {exc}[/red]")
            return
        self.app.call_from_thread(
            self._result, f"[green]{count} contactos exportados a[/green] [bold]{target}[/bold]"
        )

    # -------------------------------------------------------------- import --
    def _ask_import_path(self) -> None:
        candidates = sorted(export_dir().glob("*.adi"))
        hint = str(candidates[-1]) if candidates else str(Path.home() / "log.adi")
        self.app.push_screen(
            FormScreen(
                "Importar ADIF",
                [
                    Field("path", "Fichero .adi", hint),
                    Field(
                        "mode",
                        "Asignar a (propio/destino)",
                        "propio",
                        placeholder="propio = respeta el operador del fichero",
                    ),
                ],
                subtitle="Los contactos importados se marcan como MANUAL y quedan editables.",
                save_label="Importar",
            ),
            self._run_import,
        )

    def _run_import(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("path"):
            return
        if self.state.operator_id is None:
            self.app.notify("Selecciona un operador antes de importar (F10).", severity="error")
            return
        path = Path(values["path"]).expanduser()
        if not path.is_file():
            self._result(f"[red]No existe el fichero {path}[/red]")
            return
        respect = values.get("mode", "propio").strip().lower().startswith("p")
        self._import_worker(str(path), self.state.operator_id, respect)

    @work(thread=True)
    def _import_worker(self, path: str, operator_id: int, respect: bool) -> None:
        try:
            report = transfer.import_adif(
                path, operator_id=operator_id, respect_file_operator=respect
            )
        except (ServiceError, OSError) as exc:
            self.app.call_from_thread(self._result, f"[red]Error al importar: {exc}[/red]")
            return
        self._changed = report.imported > 0
        message = f"[green]{report.summary}[/green]"
        if report.errors:
            message += f"\n[yellow]Primeros errores: {'; '.join(report.errors[:3])}[/yellow]"
        self.app.call_from_thread(self._result, message)

    # --------------------------------------------------------------- stats --
    def _show_stats(self) -> None:
        stats = QsoService.stats()
        lines = [
            f"Total {stats.total} · hoy {stats.today} · indicativos únicos "
            f"{stats.unique_calls} · países {stats.countries}",
        ]
        if stats.by_band:
            lines.append(
                "Bandas: "
                + ", ".join(
                    f"{band} {count}"
                    for band, count in sorted(stats.by_band.items(), key=lambda i: -i[1])
                )
            )
        if stats.by_mode:
            lines.append(
                "Modos: "
                + ", ".join(
                    f"{mode} {count}"
                    for mode, count in sorted(stats.by_mode.items(), key=lambda i: -i[1])
                )
            )
        self._result("\n".join(lines))

    def action_close(self) -> None:
        self.dismiss(self._changed)


def operator_choices(operators: list) -> list[Choice]:  # pragma: no cover - helper
    """Adapt operators to SelectionScreen choices."""
    return [Choice(value=op.id, label=op.callsign, detail=op.name) for op in operators]


__all__ = ["TransferScreen", "SelectionScreen", "operator_choices"]
