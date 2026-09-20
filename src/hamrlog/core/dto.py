"""Plain data objects handed to the UI.

Returning detached ORM instances to a Textual widget invites lazy-load errors,
so read paths return these instead. They are also the natural shape for the
future REST API serialisers.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class QsoRow:
    """One row of the history panel."""

    id: int
    call: str
    name: str
    qso_utc: dt.datetime
    band: str
    freq_hz: int | None
    freq_tx_hz: int | None
    mode: str
    rst_sent: str
    rst_rcvd: str
    qth: str
    gridsquare: str
    country: str
    comment: str
    entry_mode: str
    operator_callsign: str
    station_name: str
    repeater_call: str = ""
    digital_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_manual(self) -> bool:
        return self.entry_mode == "MANUAL"

    @property
    def via_repeater(self) -> bool:
        return bool(self.repeater_call)


@dataclass(frozen=True, slots=True)
class ContactRow:
    """One row of the address book view."""

    id: int
    callsign: str
    first_name: str
    last_name: str
    dmr_id: int | None
    city: str
    state: str
    country: str
    gridsquare: str
    email: str
    notes: str
    source: str
    is_favorite: bool
    #: How many QSOs the log holds with this station, filled on demand.
    qso_count: int = 0

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    @property
    def summary(self) -> str:
        """One line for the entry panel: 'Manuel · Sevilla · DMR 2147001'."""
        parts = [self.full_name, self.city or self.state]
        if self.dmr_id:
            parts.append(f"DMR {self.dmr_id}")
        return " · ".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """Outcome of importing an address book file."""

    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    format_name: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return (
            f"{self.created} nuevos, {self.updated} actualizados, "
            f"{self.skipped} omitidos de {self.total} registros."
        )


@dataclass(frozen=True, slots=True)
class LogStats:
    """Counters shown in the footer and exported to Prometheus."""

    total: int
    today: int
    unique_calls: int
    countries: int
    by_band: dict[str, int] = field(default_factory=dict)
    by_mode: dict[str, int] = field(default_factory=dict)
