"""F8: the contacts — the address book.

Who each callsign belongs to: name, town, DMR ID and how many QSOs the log
holds with them. What was worked and when is the log (F1); this answers who
they are.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label, Static

from ...core import contacts as contact_files
from ...core import transfer
from ...core.dto import ContactRow
from ...core.services import ContactService, ServiceError
from ...paths import export_dir
from .base import ConfirmScreen, Field, FormScreen

_COLUMNS: tuple[tuple[str, int | None], ...] = (
    ("INDICATIVO", 13),
    ("NOMBRE", 22),
    ("CIUDAD", 16),
    ("PROVINCIA", 14),
    ("DMR ID", 10),
    ("PAÍS", 14),
    ("QSO", 5),
    ("ORIGEN", None),
)


class ContactsScreen(ModalScreen[bool]):
    """The address book. Dismisses True when anything changed."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("f8", "close", "Cerrar", show=False),
        Binding("ctrl+n", "new", "Nuevo"),
        Binding("ctrl+e", "edit", "Editar"),
        Binding("delete", "remove", "Borrar"),
        Binding("ctrl+d", "remove", "Borrar", priority=True),
        Binding("ctrl+f", "focus_search", "Buscar"),
        Binding("ctrl+i", "import_book", "Importar", priority=True),
        Binding("ctrl+o", "export_book", "Exportar", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[ContactRow] = []
        self.changed = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-wide"):
            yield Label("F8 · Contactos", classes="modal-title")
            with Horizontal(classes="search-row"):
                yield Input(
                    placeholder="Buscar por indicativo, nombre, ciudad, país o ID DMR...",
                    id="book-search",
                )
                yield Static("", id="book-count", classes="search-count")
            yield DataTable(id="book-table")
            yield Static("", id="book-result", classes="modal-preview")
            yield Static(
                "Enter editar · Supr borrar · Ctrl+N nuevo · Ctrl+I importar · "
                "Ctrl+O exportar · F1 abre el registro · Esc cerrar",
                classes="modal-help",
            )

    def on_mount(self) -> None:
        table = self.query_one("#book-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        for label, width in _COLUMNS:
            table.add_column(Text(label, style="bold"), width=width, key=label)
        self.reload()
        self.focus_table()

    def action_close(self) -> None:
        self.dismiss(self.changed)

    # ------------------------------------------------------------- listing --
    def reload(self, needle: str | None = None) -> None:
        """Refresh the table, keeping the current search when none is given."""
        if needle is None:
            needle = self.query_one("#book-search", Input).value
        table = self.query_one("#book-table", DataTable)
        table.clear()
        self._rows = ContactService.search(needle)
        for row in self._rows:
            table.add_row(
                Text(row.callsign, style="bold"),
                Text(row.full_name or "-"),
                Text(row.city or "-"),
                Text(row.state or "-"),
                Text(str(row.dmr_id) if row.dmr_id else "-", style="magenta"),
                Text(row.country or "-", style="dim"),
                Text(str(row.qso_count) if row.qso_count else "–",
                     style="bold green" if row.qso_count else "dim"),
                Text(row.source or "-", style="dim"),
                key=str(row.id),
            )
        total = ContactService.count()
        shown = len(self._rows)
        label = f" {shown} de {total:,} " if needle else f" {total:,} contactos "
        self.query_one("#book-count", Static).update(Text(label, style="bold"))

    def selected(self) -> ContactRow | None:
        table = self.query_one("#book-table", DataTable)
        if table.row_count == 0:
            return None
        index = table.cursor_row
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def result(self, message: str) -> None:
        self.query_one("#book-result", Static).update(message)

    def focus_table(self) -> None:
        table = self.query_one("#book-table", DataTable)
        table.focus() if table.row_count else self.query_one("#book-search", Input).focus()

    def focus_search(self) -> None:
        self.query_one("#book-search", Input).focus()

    @on(Input.Changed, "#book-search")
    def _on_search(self, event: Input.Changed) -> None:
        self.reload(event.value)

    @on(Input.Submitted, "#book-search")
    def _on_submit(self) -> None:
        self.focus_table()

    # --------------------------------------------------------------- edit --
    def action_new(self) -> None:
        self.app.push_screen(FormScreen("Nuevo contacto", _fields()), self._create)

    def _create(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("callsign"):
            return
        try:
            ContactService.create(values["callsign"], **_parse(values))
        except (ServiceError, ValueError) as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.changed = True
        self.reload()

    def action_edit(self) -> None:
        row = self.selected()
        if row is None:
            return
        self.app.push_screen(
            FormScreen(f"Editar contacto · {row.callsign}", _fields(row)),
            lambda values: self._update(row.id, values),
        )

    def _update(self, contact_id: int, values: dict[str, str] | None) -> None:
        if not values:
            return
        try:
            ContactService.update(
                contact_id, callsign=values["callsign"], **_parse(values)
            )
        except (ServiceError, ValueError) as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.changed = True
        self.reload()

    def action_remove(self) -> None:
        row = self.selected()
        if row is None:
            return
        self.app.push_screen(
            ConfirmScreen(
                f"¿Borrar a {row.callsign} de la agenda?",
                detail=row.summary or "Sin datos adicionales.",
                danger=True,
            ),
            lambda confirmed: self._delete(row.id, confirmed),
        )

    def _delete(self, contact_id: int, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            ContactService.delete(contact_id)
        except ServiceError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.changed = True
        self.reload()

    # ------------------------------------------------------------- import --
    def action_import_book(self) -> None:
        self.app.push_screen(
            FormScreen(
                "Importar contactos",
                [
                    Field("path", "Fichero", placeholder="~/Descargas/user.csv"),
                    Field("country", "Solo el país", "", placeholder="Spain (vacío = todos)"),
                    Field("update", "Actualizar existentes", "si", placeholder="si / no"),
                ],
                subtitle="Se reconocen CSV y JSON de RadioID.net, BrandMeister, el CPS "
                "de la radio y el propio hamrlog. El formato se detecta solo.",
                save_label="Importar",
            ),
            self._run_import,
        )

    def _run_import(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("path"):
            return
        path = Path(values["path"]).expanduser()
        if not path.is_file():
            self.result(f"[red]No existe el fichero {path}[/red]")
            return
        update = values.get("update", "si").strip().lower() not in ("no", "n", "off")
        self.result("[dim]Importando...[/dim]")
        self._import_worker(str(path), values.get("country", ""), update)

    @work(thread=True)
    def _import_worker(self, path: str, country: str, update: bool) -> None:
        """A national list is tens of thousands of rows; keep the UI alive."""
        try:
            summary = transfer.import_contacts(
                path, update_existing=update, country_filter=country
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            self.app.call_from_thread(self.result, f"[red]Error al importar: {exc}[/red]")
            return

        message = f"[green]{summary.text}[/green]\n[dim]Formato: {summary.format_name}[/dim]"
        if summary.warnings:
            message += f"\n[yellow]{' '.join(summary.warnings)}[/yellow]"
        self.changed = True
        self.app.call_from_thread(self.result, message)
        self.app.call_from_thread(self.reload)

    # ------------------------------------------------------------- export --
    def action_export_book(self) -> None:
        options = "\n".join(
            f"  {name}: {description}" for name, description in contact_files.EXPORT_FORMATS.items()
        )
        self.app.push_screen(
            FormScreen(
                "Exportar contactos",
                [
                    Field("format", "Formato", "anytone", placeholder="hamrlog, radioid o anytone"),
                    Field("path", "Fichero", str(export_dir() / "contactos.csv")),
                ],
                subtitle=f"Formatos disponibles:\n{options}",
                save_label="Exportar",
            ),
            self._run_export,
        )

    def _run_export(self, values: dict[str, str] | None) -> None:
        if not values or not values.get("path"):
            return
        export_format = values.get("format", "hamrlog").strip().lower()
        if export_format not in contact_files.EXPORT_FORMATS:
            self.app.notify(f"Formato desconocido: «{export_format}».", severity="error")
            return
        self._export_worker(str(Path(values["path"]).expanduser()), export_format)

    @work(thread=True)
    def _export_worker(self, path: str, export_format: str) -> None:
        try:
            target, count = transfer.export_contacts(path, export_format=export_format)
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            self.app.call_from_thread(self.result, f"[red]Error al exportar: {exc}[/red]")
            return
        note = ""
        if export_format == "anytone":
            note = "\n[dim]Los contactos sin ID DMR no se exportan: la radio los ignora.[/dim]"
        self.app.call_from_thread(
            self.result,
            f"[green]{count:,} contactos exportados a[/green] [bold]{target}[/bold]{note}",
        )


def _fields(row: ContactRow | None = None) -> list[Field]:
    """Form fields for creating or editing an address book entry."""
    return [
        Field("callsign", "Indicativo", row.callsign if row else "", placeholder="EA7WM"),
        Field("first_name", "Nombre", row.first_name if row else ""),
        Field("last_name", "Apellidos", row.last_name if row else ""),
        Field("dmr_id", "ID DMR", str(row.dmr_id) if row and row.dmr_id else "",
              placeholder="2147001"),
        Field("city", "Ciudad", row.city if row else ""),
        Field("state", "Provincia", row.state if row else ""),
        Field("country", "País", row.country if row else ""),
        Field("gridsquare", "Locator", row.gridsquare if row else "", placeholder="IM76"),
        Field("email", "Correo", row.email if row else ""),
        Field("notes", "Notas", row.notes if row else ""),
    ]


def _parse(values: dict[str, str]) -> dict[str, object]:
    """Convert the contact form into service arguments.

    Raises:
        ValueError: When the DMR ID is not a number.
    """
    dmr_text = values.get("dmr_id", "").strip()
    dmr_id = None
    if dmr_text:
        if not dmr_text.isdigit():
            raise ValueError(f"El ID DMR debe ser un número: «{dmr_text}».")
        dmr_id = int(dmr_text)
    return {
        "first_name": values.get("first_name", ""),
        "last_name": values.get("last_name", ""),
        "dmr_id": dmr_id,
        "city": values.get("city", ""),
        "state": values.get("state", ""),
        "country": values.get("country", ""),
        "gridsquare": values.get("gridsquare", ""),
        "email": values.get("email", ""),
        "notes": values.get("notes", ""),
    }
