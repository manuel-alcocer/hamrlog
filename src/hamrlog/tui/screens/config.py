"""F10: configuration.

Sections are deliberately flat: pick one, edit it, come back. During a radio
session the operator should never need to dig through nested menus.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from ... import __version__
from ...core import entry as entry_parser
from ...core.services import OperatorService, ServiceError, SettingsService
from ...core.state import SessionState
from ...db.session import default_database_url
from ...paths import config_dir, data_dir, export_dir
from ..widgets.history import ORDER_NEWEST_FIRST, ORDER_OLDEST_FIRST
from .base import Choice, ConfirmScreen, Field, FormScreen, SelectionScreen

#: Accepted spellings for the callsign validation mode, in both languages.
_VALIDATION_WORDS: dict[str, str] = {
    "estricta": "strict", "estricto": "strict", "strict": "strict", "si": "strict",
    "sí": "strict", "s": "strict",
    "avisar": "warn", "aviso": "warn", "warn": "warn", "advertir": "warn",
    "no": "off", "off": "off", "desactivada": "off", "ninguna": "off", "n": "off",
}
_VALIDATION_LABELS: dict[str, str] = {
    "strict": "estricta (rechaza indicativos mal formados)",
    "warn": "avisar (registra con advertencia)",
    "off": "desactivada",
}


def _parse_validation(text: str) -> str | None:
    """Resolve what the operator typed into a validation mode."""
    return _VALIDATION_WORDS.get(text.strip().lower())


#: Settings key holding the Prometheus exporter configuration.
METRICS_KEY = "metrics"
DEFAULT_METRICS = {"enabled": False, "port": 9119}


class ConfigScreen(ModalScreen[bool]):
    """Configuration menu. Dismisses True when the session state changed."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("f5", "close", "Cerrar", show=False),
    ]

    _SECTIONS: tuple[tuple[str, str, str], ...] = (
        ("operator", "Operador activo", "Quién registra los contactos de esta sesión"),
        ("operators", "Gestionar operadores", "Crear, editar y desactivar operadores"),
        ("entry", "Entrada rápida", "Orden de los campos y separador de la línea"),
        ("history", "Histórico y agenda", "Dirección de la lista y enlace con los contactos"),
        ("transfer", "Importar y exportar", "Registro en ADIF y CSV (o /exportar)"),
        ("metrics", "Métricas Prometheus", "Exportador HTTP para monitorización"),
        ("info", "Información del sistema", "Rutas, base de datos y versión"),
    )

    def __init__(self, state: SessionState) -> None:
        super().__init__()
        self.state = state
        self._changed = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("F5 · Configuración", classes="modal-title")
            yield Static("", id="config-info", classes="modal-subtitle")
            yield OptionList(id="sections")
            yield Static("", id="config-result", classes="modal-preview")
            yield Static("Enter abre · Esc cierra", classes="modal-help")

    def on_mount(self) -> None:
        option_list = self.query_one("#sections", OptionList)
        for key, label, detail in self._SECTIONS:
            option_list.add_option(Option(f"  {label:<24} [dim]{detail}[/dim]", id=key))
        option_list.highlighted = 0
        option_list.focus()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        operator = (
            OperatorService.get(self.state.operator_id) if self.state.operator_id else None
        )
        self.query_one("#config-info", Static).update(
            f"Operador activo: [bold]{operator.display if operator else 'ninguno'}[/bold]"
        )

    def _result(self, message: str) -> None:
        self.query_one("#config-result", Static).update(message)

    @on(OptionList.OptionSelected, "#sections")
    def _on_section(self, event: OptionList.OptionSelected) -> None:
        handler = {
            "operator": self._pick_operator,
            "operators": self._manage_operators,
            "entry": self._edit_entry_format,
            "history": self._edit_history,
            "transfer": self._open_transfer,
            "metrics": self._edit_metrics,
            "info": self._show_info,
        }.get(event.option.id or "")
        if handler:
            handler()

    # ------------------------------------------------------------ operator --
    def _pick_operator(self) -> None:
        operators = OperatorService.list_all()
        if not operators:
            self._new_operator()
            return
        choices = [
            Choice(value=op.id, label=op.callsign, detail=op.name or "") for op in operators
        ]
        choices.append(Choice(value="__new__", label="+ Nuevo operador", detail=""))
        self.app.push_screen(
            SelectionScreen(
                "Operador activo", choices, current=self.state.operator_id
            ),
            self._set_operator,
        )

    def _set_operator(self, operator_id: object) -> None:
        if operator_id is None:
            return
        if operator_id == "__new__":
            self._new_operator()
            return
        self.state.operator_id = int(operator_id)  # type: ignore[arg-type]
        self._changed = True
        self._refresh_summary()
        operator = OperatorService.get(self.state.operator_id)
        self._result(f"[green]Operador activo: {operator.display if operator else ''}[/green]")

    def _new_operator(self) -> None:
        fields = [
            Field("callsign", "Indicativo", placeholder="EA7WM"),
            Field("name", "Nombre"),
            Field("gridsquare", "Locator", placeholder="IM76"),
            Field("qth", "QTH"),
        ]
        self.app.push_screen(FormScreen("Nuevo operador", fields), self._create_operator)

    def _create_operator(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("callsign"):
            return
        try:
            operator = OperatorService.create(
                values["callsign"], values["name"], values["gridsquare"], values["qth"]
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.state.operator_id = operator.id
        self._changed = True
        self._refresh_summary()
        self._result(f"[green]Operador {operator.callsign} creado y activado.[/green]")

    def _manage_operators(self) -> None:
        operators = OperatorService.list_all(include_inactive=True)
        choices = [
            Choice(
                value=op.id,
                label=op.callsign + ("" if op.is_active else "  (inactivo)"),
                detail=" · ".join(part for part in (op.name, op.qth, op.gridsquare) if part),
            )
            for op in operators
        ]
        choices.append(Choice(value="__new__", label="+ Nuevo operador", detail=""))
        self.app.push_screen(
            SelectionScreen(
                "Gestionar operadores",
                choices,
                subtitle="Selecciona uno para editarlo o desactivarlo.",
            ),
            self._edit_operator,
        )

    def _edit_operator(self, operator_id: object) -> None:
        if operator_id is None:
            return
        if operator_id == "__new__":
            self._new_operator()
            return
        operator = OperatorService.get(int(operator_id))  # type: ignore[arg-type]
        if operator is None:
            return
        fields = [
            Field("callsign", "Indicativo", operator.callsign),
            Field("name", "Nombre", operator.name),
            Field("gridsquare", "Locator", operator.gridsquare),
            Field("qth", "QTH", operator.qth),
            Field(
                "active", "Activo (si/no)", "si" if operator.is_active else "no",
                placeholder="si",
            ),
        ]
        self.app.push_screen(
            FormScreen(f"Editar operador · {operator.callsign}", fields),
            lambda values: self._save_operator(operator.id, values),
        )

    def _save_operator(self, operator_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            OperatorService.update(
                operator_id,
                callsign=values["callsign"].strip().upper(),
                name=values["name"],
                gridsquare=values["gridsquare"].strip().upper(),
                qth=values["qth"],
                is_active=values.get("active", "si").strip().lower() in ("si", "sí", "s", "yes"),
            )
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self._refresh_summary()
        self._result("[green]Operador actualizado.[/green]")

    # --------------------------------------------------------------- entry --
    def _edit_entry_format(self) -> None:
        known = ", ".join(sorted(set(entry_parser.FIELD_ALIASES.values())))
        fields = [
            Field("order", "Orden de campos", ",".join(self.state.field_order)),
            Field(
                "validation",
                "Validar indicativos",
                self.state.callsign_validation,
                placeholder="estricta, avisar o no",
            ),
        ]
        self.app.push_screen(
            FormScreen(
                "Entrada rápida",
                fields,
                subtitle=f"Campos disponibles: {known}\n"
                "Cada campo tendrá su propia casilla en la línea de entrada, en "
                "este orden; se pasa de una a otra con Tab.\n"
                "Validación: «estricta» rechaza indicativos mal formados, «avisar» "
                "los registra con una advertencia, «no» no comprueba nada. "
                "Con la estricta, terminar el indicativo en «!» lo fuerza.",
                save_label="Aplicar",
            ),
            self._save_entry_format,
        )

    def _save_entry_format(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        raw_order = [part.strip() for part in values["order"].split(",") if part.strip()]
        resolved: list[str] = []
        for name in raw_order:
            canonical = entry_parser.FIELD_ALIASES.get(name.lower())
            if canonical is None:
                self.app.notify(f"Campo desconocido: «{name}».", severity="error")
                return
            if canonical not in resolved:
                resolved.append(canonical)
        if "call" not in resolved:
            self.app.notify("El orden debe incluir el indicativo (call).", severity="error")
            return

        validation = _parse_validation(values.get("validation", ""))
        if validation is None:
            self.app.notify(
                "La validación debe ser «estricta», «avisar» o «no».", severity="error"
            )
            return

        self.state.field_order = tuple(resolved)
        self.state.callsign_validation = validation
        self._changed = True
        self._result(
            "[green]Casillas de entrada:[/green] "
            + " → ".join(resolved)
            + f"\n[green]Validación de indicativos:[/green] {_VALIDATION_LABELS[validation]}"
        )

    # ------------------------------------------------------------- history --
    def _edit_history(self) -> None:
        current = (
            "abajo" if self.state.history_order == ORDER_OLDEST_FIRST else "arriba"
        )
        fields = [
            Field(
                "direction",
                "Los nuevos van",
                current,
                placeholder="abajo o arriba",
            ),
            Field(
                "autofill",
                "Rellenar desde la agenda",
                "si" if self.state.autofill_from_book else "no",
                placeholder="si / no",
            ),
            Field(
                "addbook",
                "Dar de alta al trabajar",
                "si" if self.state.add_to_book else "no",
                placeholder="si / no",
            ),
        ]
        self.app.push_screen(
            FormScreen(
                "Histórico",
                fields,
                subtitle="«abajo»: el más antiguo arriba y la lista crece hacia abajo. "
                "«arriba»: el más reciente primero. La fila «<Insertar nuevo>» "
                "acompaña siempre al extremo por el que crece.\n"
                "«Dar de alta al trabajar»: al registrar un indicativo que no "
                "esté en la agenda, se añade solo.",
                save_label="Aplicar",
            ),
            self._save_history,
        )

    def _save_history(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        direction = values.get("direction", "").strip().lower()
        if direction in ("abajo", "asc", "ascendente", "antiguos", "down"):
            order = ORDER_OLDEST_FIRST
        elif direction in ("arriba", "desc", "descendente", "nuevos", "up"):
            order = ORDER_NEWEST_FIRST
        else:
            self.app.notify(
                "La dirección debe ser «abajo» o «arriba».", severity="error"
            )
            return

        def is_on(key: str) -> bool:
            return values.get(key, "si").strip().lower() not in ("no", "n", "off")

        self.state.history_order = order
        self.state.autofill_from_book = is_on("autofill")
        self.state.add_to_book = is_on("addbook")
        self._changed = True
        self._result(
            "[green]Histórico:[/green] los nuevos QSO van "
            + ("abajo" if order == ORDER_OLDEST_FIRST else "arriba")
            + "\n[green]Agenda:[/green] relleno "
            + ("activado" if self.state.autofill_from_book else "desactivado")
            + " · alta automática "
            + ("activada" if self.state.add_to_book else "desactivada")
        )

    # ------------------------------------------------------------ transfer --
    def _open_transfer(self) -> None:
        """Import and export of the QSO log. The address book has its own
        import in F8, since the file formats are unrelated."""
        from .transfer import TransferScreen

        self.app.push_screen(TransferScreen(self.state), self._after_transfer)

    def _after_transfer(self, changed: bool | None) -> None:
        if changed:
            self._changed = True

    # ------------------------------------------------------------- metrics --
    def _edit_metrics(self) -> None:
        current = {**DEFAULT_METRICS, **(SettingsService.get(METRICS_KEY, {}) or {})}
        fields = [
            Field(
                "enabled", "Activar exportador (si/no)",
                "si" if current["enabled"] else "no",
            ),
            Field("port", "Puerto HTTP", str(current["port"]), kind="integer"),
        ]
        self.app.push_screen(
            FormScreen(
                "Métricas Prometheus",
                fields,
                subtitle="Expone /metrics con los contadores del log. Requiere "
                "instalar el extra: pip install hamrlog[metrics]. "
                "El cambio se aplica al reiniciar.",
                save_label="Guardar",
            ),
            self._save_metrics,
        )

    def _save_metrics(self, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            port = int(values["port"])
        except ValueError:
            self.app.notify("El puerto debe ser un número.", severity="error")
            return
        enabled = values["enabled"].strip().lower() in ("si", "sí", "s", "yes", "true", "1")
        SettingsService.set(METRICS_KEY, {"enabled": enabled, "port": port})
        self._result(
            f"[green]Métricas {'activadas' if enabled else 'desactivadas'} "
            f"en el puerto {port}. Se aplicará al reiniciar.[/green]"
        )

    # ---------------------------------------------------------------- info --
    def _show_info(self) -> None:
        lines = [
            f"hamrlog {__version__}",
            f"Base de datos : {default_database_url()}",
            f"Datos         : {data_dir()}",
            f"Configuración : {config_dir()}",
            f"Exportaciones : {export_dir()}",
            "",
            "Variables de entorno: HAMRLOG_HOME (carpeta de datos), "
            "HAMRLOG_DATABASE_URL (base de datos).",
        ]
        self._result("\n".join(lines))

    def action_close(self) -> None:
        self.dismiss(self._changed)


__all__ = ["ConfigScreen", "ConfirmScreen", "METRICS_KEY", "DEFAULT_METRICS"]
