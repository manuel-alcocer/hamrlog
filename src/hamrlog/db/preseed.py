"""The bundled catalog of current radios, antennas and power supplies.

Every JSON file under ``hamrlog/data/preseed`` is read, whatever its name,
so adding a catalog is dropping a file there. The files are written in
Spanish, like the equipment they describe: each one is an object
``{"tipo": "emisoras" | "antenas" | "fuentes", "elementos": [...]}``, or a
bare list when the file is named after its kind (``emisoras.json``).

Entries are loaded as ``preset`` rows: the services refuse to change or
delete them, and they exist so that building an equipment set does not start
with typing in every radio by hand.

Loading runs on every start and is idempotent: it only adds what is missing,
matched by name regardless of case, so a newer catalog adds its new models
and an item the operator registered under the same name keeps theirs.
"""

from __future__ import annotations

import json
import logging
import os
from importlib import resources
from typing import Any

from sqlalchemy import Engine, func, insert, select

from ..core import bands
from .models import Antenna, PowerSupply, Station, StationType, station_type_links

logger = logging.getLogger(__name__)

#: Set to "0" to start without the catalog (the tests do).
PRESEED_ENV = "HAMRLOG_PRESEED"


def brand_of(entry: dict[str, Any]) -> str:
    """The entry's brand, or the first word of its name."""
    return str(entry.get("brand") or "").strip() or str(entry["name"]).split()[0]


#: Kinds a catalog file may hold, by the Spanish name the files use.
KINDS = ("emisoras", "antenas", "fuentes")


def load_catalogs(folder: Any = None) -> dict[str, list[dict[str, Any]]]:
    """Entries of every catalog file, grouped by kind.

    A file that cannot be read or does not say its kind is skipped with a
    warning rather than stopping the application.
    """
    found: dict[str, list[dict[str, Any]]] = {kind: [] for kind in KINDS}
    try:
        if folder is None:
            folder = resources.files("hamrlog").joinpath("data", "preseed")
        files = sorted(
            (entry for entry in folder.iterdir() if entry.name.endswith(".json")),
            key=lambda entry: entry.name,
        )
    except (FileNotFoundError, NotADirectoryError, OSError):
        return found
    for source in files:
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            logger.warning("preseed: could not read %s", source.name)
            continue
        if isinstance(data, dict):
            kind = str(data.get("tipo", "")).lower()
            entries = data.get("elementos", [])
        else:
            kind = source.name.removesuffix(".json").lower()
            entries = data
        if kind not in found or not isinstance(entries, list):
            logger.warning("preseed: %s does not say what it holds", source.name)
            continue
        found[kind].extend(
            entry for entry in entries if isinstance(entry, dict) and entry.get("name")
        )
    return found


def apply_preseed(engine: Engine, folder: Any = None) -> int:
    """Add the catalog entries the database does not have yet.

    Args:
        folder: Where the catalog files are; the bundled ones by default.

    Returns:
        How many rows were added.
    """
    if os.environ.get(PRESEED_ENV, "1") == "0":
        return 0
    catalogs = load_catalogs(folder)
    added = 0
    with engine.begin() as connection:

        def known(model: Any) -> set[str]:
            return set(connection.execute(select(func.lower(model.name))).scalars())

        type_ids = {
            name.lower(): type_id
            for type_id, name in connection.execute(select(StationType.id, StationType.name))
        }
        present = known(Station)
        for entry in catalogs["emisoras"]:
            name = str(entry["name"]).strip()
            if name.lower() in present:
                continue
            power = entry.get("power_w")
            station_id = connection.execute(
                insert(Station).values(
                    name=name,
                    brand=brand_of(entry),
                    rig=str(entry.get("rig") or ""),
                    power_w=int(power) if power else None,
                    notes=str(entry.get("notes") or ""),
                    preset=True,
                )
            ).inserted_primary_key[0]
            for type_name in entry.get("types") or []:
                type_id = type_ids.get(str(type_name).lower())
                if type_id is not None:
                    connection.execute(
                        insert(station_type_links).values(
                            station_id=station_id, type_id=type_id
                        )
                    )
            present.add(name.lower())
            added += 1

        present = known(Antenna)
        for entry in catalogs["antenas"]:
            name = str(entry["name"]).strip()
            if name.lower() in present:
                continue
            valid = [band.name for raw in entry.get("bands") or [] if (band := bands.get(raw))]
            connection.execute(
                insert(Antenna).values(
                    name=name,
                    brand=brand_of(entry),
                    bands=valid,
                    notes=str(entry.get("notes") or ""),
                    preset=True,
                )
            )
            present.add(name.lower())
            added += 1

        present = known(PowerSupply)
        for entry in catalogs["fuentes"]:
            name = str(entry["name"]).strip()
            if name.lower() in present:
                continue
            connection.execute(
                insert(PowerSupply).values(
                    name=name,
                    brand=brand_of(entry),
                    voltage_v=entry.get("voltage_v"),
                    current_a=entry.get("current_a"),
                    notes=str(entry.get("notes") or ""),
                    preset=True,
                )
            )
            present.add(name.lower())
            added += 1
    if added:
        logger.info("preseed: added %d catalog items", added)
    return added
