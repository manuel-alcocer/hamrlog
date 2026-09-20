"""SQLAlchemy models.

Design notes:

* Frequencies are integer hertz; reports (RST) are text because digital modes
  use dB values such as ``-12``.
* Timestamps are naive UTC. SQLite has no timezone storage, so normalising on
  write keeps SQLite and PostgreSQL behaviour identical.
* ``Qso.entry_mode`` drives the edit rules: an automatically timestamped QSO
  only allows the callsign to be corrected, a manually dated one allows
  everything.
* Anything the model has no column for lands in the ``extra`` JSON blob, which
  keeps ADIF imports lossless.
"""

from __future__ import annotations

import datetime as dt
import enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    """Current UTC time as a naive datetime, truncated to the second."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)


class Base(DeclarativeBase):
    """Declarative base with a shared JSON type map."""

    type_annotation_map = {dict[str, Any]: JSON, list[str]: JSON}


class EntryMode(str, enum.Enum):
    """How a QSO acquired its timestamp."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class Operator(Base):
    """A person logging QSOs. Local identity only, no password."""

    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    gridsquare: Mapped[str] = mapped_column(String(12), default="")
    qth: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    qsos: Mapped[list[Qso]] = relationship(back_populates="operator")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Operator {self.callsign}>"

    @property
    def display(self) -> str:
        return f"{self.callsign} ({self.name})" if self.name else self.callsign


class Station(Base):
    """A radio setup: rig plus antenna, selected with F6."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    rig: Mapped[str] = mapped_column(String(120), default="")
    antenna: Mapped[str] = mapped_column(String(120), default="")
    power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Station {self.name}>"

    @property
    def summary(self) -> str:
        parts = [part for part in (self.rig, self.antenna) if part]
        if self.power_w:
            parts.append(f"{self.power_w} W")
        return " / ".join(parts) if parts else self.name


class Contact(Base):
    """An address book entry.

    Separate from ``Qso``: the log records what happened on the air, while
    this is who somebody is. Entries usually arrive in bulk from a DMR user
    list, so the table is indexed for lookups by callsign and by DMR ID and
    carries no foreign keys.
    """

    __tablename__ = "contacts"
    __table_args__ = (Index("ix_contacts_country_call", "country", "callsign"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String(32), index=True)
    #: Callsign without portable prefixes/suffixes, used for lookups.
    base_call: Mapped[str] = mapped_column(String(32), index=True, default="")
    #: DMR radio ID. Unique when present; a person may hold none.
    dmr_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)

    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")

    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    gridsquare: Mapped[str] = mapped_column(String(12), default="")

    email: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    #: Where the entry came from: an import format name, "manual" or "log".
    source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Contact {self.callsign} {self.dmr_id}>"

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    @property
    def display(self) -> str:
        return f"{self.callsign} · {self.full_name}" if self.full_name else self.callsign


class Repeater(Base):
    """A repeater the operator works through.

    A repeater is used in split: you listen on ``output_hz`` and transmit on
    ``input_hz``, which is ``output_hz + shift_hz``. Analogue repeaters need a
    CTCSS tone to open them; digital ones carry their parameters in
    ``digital_data`` (color code, talkgroup, reflector, room).
    """

    __tablename__ = "repeaters"

    id: Mapped[int] = mapped_column(primary_key=True)
    callsign: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")

    band: Mapped[str] = mapped_column(String(16), default="")
    #: Repeater output: what you tune and listen to.
    output_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Repeater input: what you actually transmit on.
    input_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Signed offset from output to input, negative below.
    shift_hz: Mapped[int] = mapped_column(Integer, default=0)

    mode: Mapped[str] = mapped_column(String(24), default="")
    #: Sub-audible tone sent to open the repeater, as text ("88.5").
    ctcss_tx: Mapped[str] = mapped_column(String(8), default="")
    #: Tone expected on the output, when it differs from the transmit one.
    ctcss_rx: Mapped[str] = mapped_column(String(8), default="")
    #: Digital coded squelch, as an alternative to CTCSS.
    dcs: Mapped[str] = mapped_column(String(8), default="")

    qth: Mapped[str] = mapped_column(String(120), default="")
    gridsquare: Mapped[str] = mapped_column(String(12), default="")

    #: Mode specific defaults: color_code, talkgroup, reflector, room, network.
    digital_data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Repeater {self.callsign} {self.output_hz}>"

    @property
    def display(self) -> str:
        return f"{self.callsign} · {self.name}" if self.name else self.callsign


class Profile(Base):
    """A saved snapshot of the working configuration, recalled with F7."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"), nullable=True)
    repeater_id: Mapped[int | None] = mapped_column(ForeignKey("repeaters.id"), nullable=True)

    band: Mapped[str] = mapped_column(String(16), default="")
    freq_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(24), default="")
    digital_data: Mapped[dict[str, Any]] = mapped_column(default=dict)

    # Fast entry behaviour, so a contest profile can differ from a ragchew one.
    field_order: Mapped[list[str]] = mapped_column(default=list)
    separator: Mapped[str] = mapped_column(String(4), default=",")

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    operator: Mapped[Operator | None] = relationship()
    station: Mapped[Station | None] = relationship()
    repeater: Mapped[Repeater | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Profile {self.name}>"


class Qso(Base):
    """A logged contact."""

    __tablename__ = "qsos"
    __table_args__ = (
        Index("ix_qsos_operator_time", "operator_id", "qso_utc"),
        Index("ix_qsos_base_call_band", "base_call", "band"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), index=True)
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"), nullable=True)
    repeater_id: Mapped[int | None] = mapped_column(ForeignKey("repeaters.id"), nullable=True)
    #: Repeater callsign copied here so the contact keeps its history even if
    #: the repeater is later deleted from the list.
    repeater_call: Mapped[str] = mapped_column(String(32), default="", index=True)

    call: Mapped[str] = mapped_column(String(32), index=True)
    #: Callsign without portable prefixes/suffixes, used for duplicate checks.
    base_call: Mapped[str] = mapped_column(String(32), index=True, default="")
    name: Mapped[str] = mapped_column(String(80), default="")

    qso_utc: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)

    band: Mapped[str] = mapped_column(String(16), default="")
    #: Frequency as the operator tunes it: the repeater output when working
    #: through one, the single working frequency otherwise.
    freq_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Actual transmit frequency when it differs from ``freq_hz``, that is the
    #: repeater input. Exported as ADIF FREQ, with ``freq_hz`` as FREQ_RX.
    freq_tx_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(24), default="")

    rst_sent: Mapped[str] = mapped_column(String(16), default="")
    rst_rcvd: Mapped[str] = mapped_column(String(16), default="")

    qth: Mapped[str] = mapped_column(String(120), default="")
    gridsquare: Mapped[str] = mapped_column(String(12), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)

    entry_mode: Mapped[EntryMode] = mapped_column(
        Enum(EntryMode, native_enum=False, length=8), default=EntryMode.AUTO, index=True
    )

    #: Mode specific values: talkgroup, reflector, room, network, ...
    digital_data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    #: ADIF fields with no dedicated column, preserved on import/export.
    extra: Mapped[dict[str, Any]] = mapped_column(default=dict)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    operator: Mapped[Operator] = relationship(back_populates="qsos")
    station: Mapped[Station | None] = relationship()
    repeater: Mapped[Repeater | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Qso {self.call} {self.qso_utc:%Y-%m-%d %H:%M} {self.band} {self.mode}>"

    @property
    def is_manual(self) -> bool:
        return self.entry_mode is EntryMode.MANUAL

    @property
    def via_repeater(self) -> bool:
        return bool(self.repeater_call)


class Setting(Base):
    """Application level key/value settings shared by every operator."""

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("key", name="uq_settings_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[dict[str, Any]] = mapped_column(default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SchemaVersion(Base):
    """Single-row table recording the schema revision for future migrations."""

    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    applied_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


#: Bumped whenever models change in a way that needs a data migration.
#: 2 added the repeaters table and the repeater columns on qsos and profiles.
#: 3 added the contacts address book.
CURRENT_SCHEMA_VERSION = 3
