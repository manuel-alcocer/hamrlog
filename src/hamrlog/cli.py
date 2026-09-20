"""Command line entry point.

Beyond launching the TUI, the subcommands make the log usable from a script or
a cron job, which is the same surface a future API would expose.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .core import contacts as contact_files
from .db.session import default_database_url, init_engine
from .paths import config_dir, data_dir, export_dir


def _configure_console() -> None:
    """Make the Windows console speak UTF-8.

    PowerShell and cmd.exe still start in a legacy code page on many systems,
    which mangles accented text and the box drawing characters the interface
    relies on. Switching the console to UTF-8 and reconfiguring the Python
    streams fixes both. On Linux and macOS this is a no-op.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes

        # 65001 is the UTF-8 code page.
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:  # noqa: BLE001 - best effort, never fatal
        pass

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - redirected streams may refuse
                pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hamrlog",
        description="Diario de radioaficionado para consola (Linux, Windows y macOS).",
    )
    parser.add_argument("--version", action="version", version=f"hamrlog {__version__}")
    parser.add_argument(
        "--database",
        metavar="URL",
        help="URL SQLAlchemy de la base de datos (por defecto, SQLite local).",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Abre la interfaz de texto (por defecto).")
    sub.add_parser("info", help="Muestra rutas, base de datos y versión.")

    export = sub.add_parser("export", help="Exporta el log sin abrir la interfaz.")
    export.add_argument("path", nargs="?", help="Fichero de destino.")
    export.add_argument(
        "--format", choices=("adif", "csv"), default="adif", help="Formato de salida."
    )

    importer = sub.add_parser("import", help="Importa un fichero ADIF.")
    importer.add_argument("path", help="Fichero .adi a importar.")
    importer.add_argument(
        "--operator", required=True, help="Indicativo del operador de destino."
    )
    importer.add_argument(
        "--force-operator",
        action="store_true",
        help="Asigna todos los contactos al operador indicado, ignorando el del fichero.",
    )

    metrics = sub.add_parser("metrics", help="Arranca solo el exportador Prometheus.")
    metrics.add_argument("--port", type=int, default=9119, help="Puerto HTTP.")

    contacts = sub.add_parser("contacts", help="Agenda de contactos (listín).")
    contacts_sub = contacts.add_subparsers(dest="contacts_command", required=True)

    contacts_import = contacts_sub.add_parser(
        "import", help="Importa una lista de contactos (CSV o JSON, formato detectado)."
    )
    contacts_import.add_argument("path", help="Fichero a importar.")
    contacts_import.add_argument(
        "--country", default="", help="Importar solo el país indicado, p. ej. Spain."
    )
    contacts_import.add_argument(
        "--no-update",
        action="store_true",
        help="No tocar los contactos que ya están en la agenda.",
    )

    contacts_export = contacts_sub.add_parser("export", help="Exporta la agenda.")
    contacts_export.add_argument("path", nargs="?", help="Fichero de destino.")
    contacts_export.add_argument(
        "--format",
        choices=tuple(contact_files.EXPORT_FORMATS),
        default="hamrlog",
        help="Formato de salida.",
    )

    contacts_list = contacts_sub.add_parser("list", help="Busca en la agenda.")
    contacts_list.add_argument("query", nargs="?", default="", help="Texto a buscar.")
    contacts_list.add_argument("--limit", type=int, default=50, help="Máximo de filas.")

    return parser


def _cmd_info() -> int:
    print(f"hamrlog {__version__}")
    print(f"Base de datos : {default_database_url()}")
    print(f"Datos         : {data_dir()}")
    print(f"Configuración : {config_dir()}")
    print(f"Exportaciones : {export_dir()}")
    return 0


def _cmd_export(path: str | None, output_format: str) -> int:
    from .core import transfer

    if output_format == "adif":
        target, count = transfer.export_adif(path)
    else:
        target, count = transfer.export_csv(path)
    print(f"{count} contactos exportados a {target}")
    return 0


def _cmd_import(path: str, operator: str, force_operator: bool) -> int:
    from .core import transfer
    from .core.services import OperatorService

    found = OperatorService.get_by_callsign(operator)
    if found is None:
        print(f"No existe el operador {operator.upper()}.", file=sys.stderr)
        return 1
    report = transfer.import_adif(
        path, operator_id=found.id, respect_file_operator=not force_operator
    )
    print(report.summary)
    for error in report.errors[:10]:
        print(f"  {error}", file=sys.stderr)
    return 0


def _cmd_contacts(args: argparse.Namespace) -> int:
    """Address book subcommands: import, export and search."""
    from .core import transfer
    from .core.services import ContactService

    if args.contacts_command == "import":
        summary = transfer.import_contacts(
            args.path,
            update_existing=not args.no_update,
            country_filter=args.country,
        )
        print(f"Formato detectado: {summary.format_name}")
        print(summary.text)
        for warning in summary.warnings:
            print(f"  aviso: {warning}", file=sys.stderr)
        return 0 if (summary.created or summary.updated) else 1

    if args.contacts_command == "export":
        target, count = transfer.export_contacts(
            args.path, export_format=args.format
        )
        print(f"{count} contactos exportados a {target}")
        if args.format == "anytone":
            print("Los contactos sin ID DMR no se exportan: la radio los ignora.")
        return 0

    rows = ContactService.search(args.query, limit=args.limit)
    if not rows:
        print("Sin resultados." if args.query else "La agenda está vacía.")
        return 0
    print(f"{'INDICATIVO':<12} {'NOMBRE':<24} {'CIUDAD':<16} {'DMR ID':<10} {'QSO':>4}")
    for row in rows:
        print(
            f"{row.callsign:<12} {row.full_name[:24]:<24} {row.city[:16]:<16} "
            f"{row.dmr_id or '':<10} {row.qso_count or '':>4}"
        )
    print(f"\n{len(rows)} de {ContactService.count()} contactos.")
    return 0


def _cmd_metrics(port: int) -> int:
    from .api.metrics import serve_forever

    return serve_forever(port)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns the process exit code."""
    _configure_console()
    args = _build_parser().parse_args(argv)
    init_engine(args.database)

    command = args.command or "run"
    if command == "info":
        return _cmd_info()
    if command == "export":
        return _cmd_export(args.path, args.format)
    if command == "import":
        return _cmd_import(args.path, args.operator, args.force_operator)
    if command == "metrics":
        return _cmd_metrics(args.port)
    if command == "contacts":
        return _cmd_contacts(args)

    from .tui.app import HamrlogApp

    HamrlogApp(database_url=args.database).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
