"""Lightweight schema migrations.

``create_all`` creates missing tables but never alters existing ones, so a
database written by an older version would be missing the newer columns. This
module adds them in place.

The scope is deliberately narrow: adding columns and tables, which is all the
schema has needed so far and what every supported backend does safely. A
change that renames or drops a column would need a real migration tool.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, insert, inspect, select, text
from sqlalchemy.schema import Column

from .models import (
    Antenna,
    Base,
    Profile,
    Qso,
    Station,
    StationType,
    station_antenna_links,
    station_profile_links,
)

logger = logging.getLogger(__name__)


def _literal_default(column: Column) -> str | None:
    """SQL literal to backfill a NOT NULL column being added.

    SQLite refuses ``ADD COLUMN ... NOT NULL`` without a default, and existing
    rows need a value anyway.
    """
    if column.nullable:
        return None

    python_type: type | None
    try:
        python_type = column.type.python_type
    except NotImplementedError:  # pragma: no cover - exotic types
        python_type = None

    if python_type is str:
        return "''"
    if python_type is bool:
        return "0"
    if python_type in (int, float):
        return "0"
    if python_type is dict or python_type is list:
        return "'{}'" if python_type is dict else "'[]'"
    return None


def add_missing_columns(engine: Engine) -> list[str]:
    """Add columns present in the models but missing in the database.

    Returns:
        The ``table.column`` names that were added, for logging and tests.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            # create_all handles brand new tables.
            continue

        present = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue

            type_sql = column.type.compile(engine.dialect)
            clause = f"{column.name} {type_sql}"
            default = _literal_default(column)
            if default is not None:
                clause += f" NOT NULL DEFAULT {default}"

            statement = f"ALTER TABLE {table.name} ADD COLUMN {clause}"
            with engine.begin() as connection:
                connection.execute(text(statement))
            added.append(f"{table.name}.{column.name}")
            logger.info("schema upgrade: added %s.%s", table.name, column.name)

    return added


#: Types every new or upgraded database starts with. Amateur HF includes 160 m,
#: hence 1.8 MHz rather than the textbook 3 MHz.
DEFAULT_STATION_TYPES: tuple[tuple[str, int, int], ...] = (
    ("HF", 1_800_000, 30_000_000),
    ("CB", 26_965_000, 27_405_000),
    ("VHF", 30_000_000, 300_000_000),
    ("UHF", 300_000_000, 3_000_000_000),
)


def upgrade_data(engine: Engine, previous_version: int | None) -> None:
    """Fill in the data a schema revision expects.

    Args:
        previous_version: Revision the database was at before this start,
            None for a database created just now.
    """
    if previous_version is None or previous_version < 4:
        _seed_station_types(engine)
        _assign_profiles_to_their_station(engine)
    if previous_version is None or previous_version < 5:
        _split_antennas_from_stations(engine)


def _seed_station_types(engine: Engine) -> None:
    """Create the default types, once. Deleting them later is respected."""
    with engine.begin() as connection:
        if connection.execute(select(StationType.id).limit(1)).first() is not None:
            return
        connection.execute(
            insert(StationType),
            [
                {"name": name, "min_hz": low, "max_hz": high}
                for name, low, high in DEFAULT_STATION_TYPES
            ],
        )
    logger.info("schema upgrade: added the default station types")


def _assign_profiles_to_their_station(engine: Engine) -> None:
    """A profile used to carry one station; it becomes an assignment."""
    with engine.begin() as connection:
        rows = connection.execute(
            select(Profile.id, Profile.station_id).where(Profile.station_id.is_not(None))
        ).all()
        for profile_id, station_id in rows:
            connection.execute(
                insert(station_profile_links).values(
                    station_id=station_id, profile_id=profile_id
                )
            )
            connection.execute(
                Profile.__table__.update()
                .where(Profile.id == profile_id)
                .values(station_id=None)
            )
    if rows:
        logger.info("schema upgrade: assigned %d profiles to their station", len(rows))


def _split_antennas_from_stations(engine: Engine) -> None:
    """The antenna text of each station becomes an antenna assigned to it.

    Stations that named the same antenna share it. Their past QSOs take that
    antenna, so MY_ANTENNA keeps coming out in the exports. The bands are
    unknown and left empty, which accepts every configuration.
    """
    with engine.begin() as connection:
        rows = connection.execute(
            select(Station.id, Station.antenna).where(Station.antenna != "")
        ).all()
        antenna_ids: dict[str, int] = {}
        for station_id, text_value in rows:
            name = text_value.strip()
            key = name.lower()
            if key not in antenna_ids:
                existing = connection.execute(
                    select(Antenna.id).where(Antenna.name == name)
                ).first()
                if existing is None:
                    result = connection.execute(
                        insert(Antenna).values(name=name, bands=[], notes="")
                    )
                    antenna_ids[key] = result.inserted_primary_key[0]
                else:
                    antenna_ids[key] = existing[0]
            antenna_id = antenna_ids[key]
            connection.execute(
                insert(station_antenna_links).values(
                    station_id=station_id, antenna_id=antenna_id
                )
            )
            connection.execute(
                Qso.__table__.update()
                .where(Qso.station_id == station_id, Qso.antenna_id.is_(None))
                .values(antenna_id=antenna_id)
            )
            connection.execute(
                Station.__table__.update().where(Station.id == station_id).values(antenna="")
            )
    if rows:
        logger.info("schema upgrade: moved %d station antennas to their own table", len(rows))
