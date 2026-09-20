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

from sqlalchemy import Engine, inspect, text
from sqlalchemy.schema import Column

from .models import Base

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
