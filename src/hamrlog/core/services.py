"""Application services.

Every write and every query goes through this module. The TUI holds no SQL and
no ORM objects, so the same services can back a REST API or a web frontend
without changes.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from ..db.models import (
    Contact,
    EntryMode,
    Operator,
    Profile,
    Qso,
    Repeater,
    Setting,
    Station,
)
from ..db.session import session_scope
from . import bands, modes, repeaters
from . import callsign as callsign_module
from .dto import ContactRow, LogStats, QsoRow
from .state import SessionState

#: Fields an automatically timestamped QSO still allows editing.
AUTO_EDITABLE_FIELDS: frozenset[str] = frozenset({"call"})

#: Fields a manually dated QSO allows editing.
MANUAL_EDITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "call", "name", "qso_utc", "band", "freq_hz", "freq_tx_hz", "mode", "rst_sent",
        "rst_rcvd", "qth", "gridsquare", "country", "comment", "power_w", "station_id",
        "operator_id", "digital_data", "repeater_id", "repeater_call",
    }
)


class ServiceError(Exception):
    """Raised when a request is rejected by a business rule."""


# --------------------------------------------------------------------------- #
# Operators
# --------------------------------------------------------------------------- #

class OperatorService:
    """Local operators. No authentication: a shack is a trusted environment."""

    @staticmethod
    def list_all(include_inactive: bool = False) -> list[Operator]:
        with session_scope() as session:
            stmt = select(Operator).order_by(Operator.callsign)
            if not include_inactive:
                stmt = stmt.where(Operator.is_active.is_(True))
            return list(session.scalars(stmt))

    @staticmethod
    def get(operator_id: int) -> Operator | None:
        with session_scope() as session:
            return session.get(Operator, operator_id)

    @staticmethod
    def get_by_callsign(call: str) -> Operator | None:
        with session_scope() as session:
            normalized = callsign_module.normalize(call)
            return session.scalars(
                select(Operator).where(Operator.callsign == normalized)
            ).first()

    @staticmethod
    def create(call: str, name: str = "", gridsquare: str = "", qth: str = "") -> Operator:
        normalized = callsign_module.normalize(call)
        if not normalized:
            raise ServiceError("El indicativo del operador no puede estar vacío.")
        with session_scope() as session:
            existing = session.scalars(
                select(Operator).where(Operator.callsign == normalized)
            ).first()
            if existing is not None:
                raise ServiceError(f"El operador {normalized} ya existe.")
            operator = Operator(
                callsign=normalized,
                name=name.strip(),
                gridsquare=gridsquare.strip().upper(),
                qth=qth.strip(),
            )
            session.add(operator)
            session.flush()
            return operator

    @staticmethod
    def update(operator_id: int, **changes: Any) -> Operator:
        with session_scope() as session:
            operator = session.get(Operator, operator_id)
            if operator is None:
                raise ServiceError("Operador no encontrado.")
            for key, value in changes.items():
                if hasattr(operator, key):
                    setattr(operator, key, value)
            session.flush()
            return operator

    @staticmethod
    def deactivate(operator_id: int) -> None:
        """Operators are never deleted: their QSOs must keep a valid owner."""
        with session_scope() as session:
            operator = session.get(Operator, operator_id)
            if operator is None:
                raise ServiceError("Operador no encontrado.")
            operator.is_active = False


# --------------------------------------------------------------------------- #
# Stations
# --------------------------------------------------------------------------- #

class StationService:
    """Rig and antenna combinations, selected with F6."""

    @staticmethod
    def list_all() -> list[Station]:
        with session_scope() as session:
            return list(session.scalars(select(Station).order_by(Station.name)))

    @staticmethod
    def get(station_id: int) -> Station | None:
        with session_scope() as session:
            return session.get(Station, station_id)

    @staticmethod
    def create(
        name: str, rig: str = "", antenna: str = "", power_w: int | None = None, notes: str = ""
    ) -> Station:
        clean = name.strip()
        if not clean:
            raise ServiceError("El nombre del equipo no puede estar vacío.")
        with session_scope() as session:
            if session.scalars(select(Station).where(Station.name == clean)).first():
                raise ServiceError(f"Ya existe un equipo llamado «{clean}».")
            station = Station(
                name=clean, rig=rig.strip(), antenna=antenna.strip(),
                power_w=power_w, notes=notes.strip(),
            )
            session.add(station)
            session.flush()
            return station

    @staticmethod
    def update(station_id: int, **changes: Any) -> Station:
        with session_scope() as session:
            station = session.get(Station, station_id)
            if station is None:
                raise ServiceError("Equipo no encontrado.")
            for key, value in changes.items():
                if hasattr(station, key):
                    setattr(station, key, value)
            session.flush()
            return station

    @staticmethod
    def delete(station_id: int) -> None:
        with session_scope() as session:
            station = session.get(Station, station_id)
            if station is None:
                raise ServiceError("Equipo no encontrado.")
            # Detach the station from past QSOs instead of losing the contacts.
            session.query(Qso).filter(Qso.station_id == station_id).update({"station_id": None})
            session.query(Profile).filter(Profile.station_id == station_id).update(
                {"station_id": None}
            )
            session.delete(station)


# --------------------------------------------------------------------------- #
# Repeaters
# --------------------------------------------------------------------------- #

class RepeaterService:
    """Repeaters the operator works through, selected with F9."""

    @staticmethod
    def list_all(include_inactive: bool = False) -> list[Repeater]:
        with session_scope() as session:
            stmt = select(Repeater).order_by(Repeater.band, Repeater.output_hz)
            if not include_inactive:
                stmt = stmt.where(Repeater.is_active.is_(True))
            return list(session.scalars(stmt))

    @staticmethod
    def get(repeater_id: int) -> Repeater | None:
        with session_scope() as session:
            return session.get(Repeater, repeater_id)

    @staticmethod
    def get_by_callsign(call: str) -> Repeater | None:
        with session_scope() as session:
            return session.scalars(
                select(Repeater).where(Repeater.callsign == callsign_module.normalize(call))
            ).first()

    @staticmethod
    def create(
        callsign_text: str,
        *,
        name: str = "",
        output_hz: int | None = None,
        shift_hz: int | None = None,
        mode: str = "FM",
        ctcss_tx: str = "",
        ctcss_rx: str = "",
        dcs: str = "",
        qth: str = "",
        gridsquare: str = "",
        digital_data: dict[str, str] | None = None,
        notes: str = "",
    ) -> Repeater:
        """Register a repeater.

        Args:
            callsign_text: Repeater callsign, e.g. "ED7ZAE".
            output_hz: Frequency it transmits on, the one you tune.
            shift_hz: Offset to its input. When omitted, the conventional
                shift for the band is used.

        Raises:
            ServiceError: On a duplicate callsign or a missing frequency.
        """
        normalized = callsign_module.normalize(callsign_text)
        if not normalized:
            raise ServiceError("El indicativo del repetidor no puede estar vacío.")
        if not output_hz:
            raise ServiceError("Falta la frecuencia de salida del repetidor.")

        band = bands.from_frequency(output_hz)
        band_name = band.name if band else ""
        if shift_hz is None:
            shift_hz = repeaters.default_shift(band_name)

        with session_scope() as session:
            if session.scalars(select(Repeater).where(Repeater.callsign == normalized)).first():
                raise ServiceError(f"El repetidor {normalized} ya existe.")
            repeater = Repeater(
                callsign=normalized,
                name=name.strip(),
                band=band_name,
                output_hz=output_hz,
                input_hz=repeaters.input_frequency(output_hz, shift_hz),
                shift_hz=shift_hz,
                mode=(modes.get(mode).name if modes.get(mode) else "FM"),
                ctcss_tx=repeaters.normalize_tone(ctcss_tx),
                ctcss_rx=repeaters.normalize_tone(ctcss_rx),
                dcs=dcs.strip(),
                qth=qth.strip(),
                gridsquare=gridsquare.strip().upper(),
                digital_data=dict(digital_data or {}),
                notes=notes.strip(),
            )
            session.add(repeater)
            session.flush()
            return repeater

    @staticmethod
    def update(repeater_id: int, **changes: Any) -> Repeater:
        """Update a repeater, keeping band, input and shift consistent."""
        with session_scope() as session:
            repeater = session.get(Repeater, repeater_id)
            if repeater is None:
                raise ServiceError("Repetidor no encontrado.")

            if "callsign" in changes:
                changes["callsign"] = callsign_module.normalize(str(changes["callsign"]))
            for key in ("ctcss_tx", "ctcss_rx"):
                if key in changes:
                    changes[key] = repeaters.normalize_tone(str(changes[key]))

            for key, value in changes.items():
                if hasattr(repeater, key):
                    setattr(repeater, key, value)

            if repeater.output_hz:
                band = bands.from_frequency(repeater.output_hz)
                repeater.band = band.name if band else ""
                repeater.input_hz = repeaters.input_frequency(
                    repeater.output_hz, repeater.shift_hz or 0
                )
            session.flush()
            return repeater

    @staticmethod
    def delete(repeater_id: int) -> None:
        """Remove a repeater, leaving logged contacts intact.

        Contacts keep ``repeater_call``, so the log still records which
        repeater was used even after the entry is gone.
        """
        with session_scope() as session:
            repeater = session.get(Repeater, repeater_id)
            if repeater is None:
                raise ServiceError("Repetidor no encontrado.")
            session.query(Qso).filter(Qso.repeater_id == repeater_id).update(
                {"repeater_id": None}
            )
            session.query(Profile).filter(Profile.repeater_id == repeater_id).update(
                {"repeater_id": None}
            )
            session.delete(repeater)

    @staticmethod
    def apply_to_state(repeater_id: int, state: SessionState) -> SessionState:
        """Put the session on a repeater, adopting all of its settings."""
        repeater = RepeaterService.get(repeater_id)
        if repeater is None:
            raise ServiceError("Repetidor no encontrado.")
        state.set_repeater(
            repeater.id,
            repeater.callsign,
            output_hz=repeater.output_hz,
            input_hz=repeater.input_hz,
            band=repeater.band,
            mode=repeater.mode,
            digital_data=dict(repeater.digital_data or {}),
        )
        return state


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #

class ProfileService:
    """Saved configurations recalled with F7."""

    @staticmethod
    def list_all() -> list[Profile]:
        with session_scope() as session:
            return list(
                session.scalars(
                    select(Profile)
                    .options(
                        joinedload(Profile.operator),
                        joinedload(Profile.station),
                        joinedload(Profile.repeater),
                    )
                    .order_by(Profile.is_default.desc(), Profile.name)
                )
            )

    @staticmethod
    def get(profile_id: int) -> Profile | None:
        with session_scope() as session:
            return session.scalars(
                select(Profile)
                .options(
                    joinedload(Profile.operator),
                    joinedload(Profile.station),
                    joinedload(Profile.repeater),
                )
                .where(Profile.id == profile_id)
            ).first()

    @staticmethod
    def get_default() -> Profile | None:
        with session_scope() as session:
            return session.scalars(select(Profile).where(Profile.is_default.is_(True))).first()

    @staticmethod
    def save_from_state(name: str, state: SessionState, *, overwrite: bool = False) -> Profile:
        """Store the current working configuration under ``name``."""
        clean = name.strip()
        if not clean:
            raise ServiceError("El nombre del perfil no puede estar vacío.")
        with session_scope() as session:
            profile = session.scalars(select(Profile).where(Profile.name == clean)).first()
            if profile is not None and not overwrite:
                raise ServiceError(f"Ya existe el perfil «{clean}».")
            if profile is None:
                profile = Profile(name=clean)
                session.add(profile)
            profile.operator_id = state.operator_id
            profile.station_id = state.station_id
            profile.repeater_id = state.repeater_id
            profile.band = state.band
            profile.freq_hz = state.freq_hz
            profile.mode = state.mode
            profile.digital_data = dict(state.digital_data)
            profile.field_order = list(state.field_order)
            profile.separator = state.separator
            session.flush()
            return profile

    @staticmethod
    def apply_to_state(profile_id: int, state: SessionState) -> SessionState:
        """Overwrite ``state`` in place with a stored profile."""
        profile = ProfileService.get(profile_id)
        if profile is None:
            raise ServiceError("Perfil no encontrado.")
        state.operator_id = profile.operator_id or state.operator_id
        state.station_id = profile.station_id
        state.band = profile.band
        state.freq_hz = profile.freq_hz
        state.mode = profile.mode or modes.DEFAULT_MODE
        state.digital_data = dict(profile.digital_data or {})
        # The repeater is restored last so it is not cleared by the fields
        # above, and only when it still exists.
        state.clear_repeater()
        if profile.repeater_id is not None:
            repeater = RepeaterService.get(profile.repeater_id)
            if repeater is not None:
                state.repeater_id = repeater.id
                state.repeater_call = repeater.callsign
                state.freq_tx_hz = repeater.input_hz
        state.field_order = tuple(profile.field_order) if profile.field_order else state.field_order
        state.separator = profile.separator or ","
        state.profile_name = profile.name
        return state

    @staticmethod
    def set_default(profile_id: int) -> None:
        with session_scope() as session:
            session.query(Profile).update({"is_default": False})
            profile = session.get(Profile, profile_id)
            if profile is None:
                raise ServiceError("Perfil no encontrado.")
            profile.is_default = True

    @staticmethod
    def delete(profile_id: int) -> None:
        with session_scope() as session:
            profile = session.get(Profile, profile_id)
            if profile is None:
                raise ServiceError("Perfil no encontrado.")
            session.delete(profile)


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

class SettingsService:
    """Key/value store for anything that is not a first class entity."""

    STATE_KEY = "session_state"

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        with session_scope() as session:
            row = session.scalars(select(Setting).where(Setting.key == key)).first()
            return row.value if row is not None else default

    @staticmethod
    def set(key: str, value: Any) -> None:
        with session_scope() as session:
            row = session.scalars(select(Setting).where(Setting.key == key)).first()
            if row is None:
                session.add(Setting(key=key, value=value))
            else:
                row.value = value

    @classmethod
    def load_state(cls) -> SessionState:
        return SessionState.from_dict(cls.get(cls.STATE_KEY, {}) or {})

    @classmethod
    def save_state(cls, state: SessionState) -> None:
        cls.set(cls.STATE_KEY, state.to_dict())


# --------------------------------------------------------------------------- #
# QSOs
# --------------------------------------------------------------------------- #

def _to_row(qso: Qso) -> QsoRow:
    """Convert an eagerly loaded QSO into the UI/API shape."""
    return QsoRow(
        id=qso.id,
        call=qso.call,
        name=qso.name,
        qso_utc=qso.qso_utc,
        band=qso.band,
        freq_hz=qso.freq_hz,
        freq_tx_hz=qso.freq_tx_hz,
        mode=qso.mode,
        rst_sent=qso.rst_sent,
        rst_rcvd=qso.rst_rcvd,
        qth=qso.qth,
        gridsquare=qso.gridsquare,
        country=qso.country,
        comment=qso.comment,
        entry_mode=qso.entry_mode.value if qso.entry_mode else EntryMode.AUTO.value,
        operator_callsign=qso.operator.callsign if qso.operator else "",
        station_name=qso.station.name if qso.station else "",
        repeater_call=qso.repeater_call or "",
        digital_data=dict(qso.digital_data or {}),
    )


def _fill_from_address_book(fields: dict[str, Any], call: str) -> None:
    """Complete blank fields from the address book.

    What the operator typed always wins: the book only supplies values that
    were left empty, so a name heard on air is never replaced by a stale one
    from a downloaded list.
    """
    wanted = ("name", "qth", "gridsquare", "country")
    if all(str(fields.get(key, "")).strip() for key in wanted):
        return

    entry = ContactService.lookup(call)
    if entry is None:
        return

    if not str(fields.get("name", "")).strip():
        name = entry.first_name or entry.full_name
        if name:
            fields["name"] = name
    if not str(fields.get("qth", "")).strip() and (entry.city or entry.state):
        fields["qth"] = entry.city or entry.state
    if not str(fields.get("gridsquare", "")).strip() and entry.gridsquare:
        fields["gridsquare"] = entry.gridsquare
    if not str(fields.get("country", "")).strip() and entry.country:
        fields["country"] = entry.country


def _remember_in_address_book(row: QsoRow) -> None:
    """Add a station to the address book the first time it is worked.

    Only ever creates: an entry already there is left exactly as it is, since
    what the operator typed into it is worth more than what a single QSO
    happens to carry. The entry is filed under the home callsign, so working
    the same person portable does not produce a second one.

    A failure here must never cost the operator the QSO, so it is swallowed.
    """
    base = callsign_module.base_call(row.call)
    if not base:
        return
    try:
        if ContactService.lookup(base) is not None:
            return
        first_name, _, last_name = row.name.partition(" ")
        ContactService.create(
            base,
            first_name=first_name,
            last_name=last_name.strip(),
            city=row.qth,
            country=row.country,
            gridsquare=row.gridsquare,
            source="log",
        )
    except ServiceError:
        # Someone else got there first, or the callsign is unusable.
        return


class QsoService:
    """Logging, searching and editing contacts."""

    @staticmethod
    def log(
        fields: dict[str, Any],
        state: SessionState,
        *,
        digital: dict[str, str] | None = None,
        qso_utc: dt.datetime | None = None,
    ) -> QsoRow:
        """Create a contact from parsed entry fields plus the session defaults.

        Args:
            fields: Values coming from the fast entry parser.
            state: Working configuration supplying band, mode, operator, rig.
            digital: Mode specific values overriding the session ones.
            qso_utc: Explicit timestamp. Supplying it marks the QSO as manual,
                which is what unlocks full editing later.

        Returns:
            The stored contact as a QsoRow.
        """
        if state.operator_id is None:
            raise ServiceError("No hay operador seleccionado. Configúralo con F10.")

        call_raw = str(fields.get("call", "")).strip()
        if not call_raw:
            raise ServiceError("Falta el indicativo.")

        entry_mode = EntryMode.MANUAL if qso_utc is not None else EntryMode.AUTO
        timestamp = qso_utc or dt.datetime.now(dt.timezone.utc).replace(
            tzinfo=None, microsecond=0
        )

        merged_digital = dict(state.digital_data)
        merged_digital.update(digital or {})

        if state.autofill_from_book:
            _fill_from_address_book(fields, call_raw)

        freq_hz = fields.get("freq_hz", state.freq_hz)
        band = str(fields.get("band") or state.band or "")
        if not band and freq_hz:
            found = bands.from_frequency(int(freq_hz))
            band = found.name if found else ""

        # An explicit frequency on the entry line means simplex on that
        # frequency, so it overrides the repeater rather than contradicting it.
        overridden = "freq_hz" in fields or "band" in fields
        repeater_id = None if overridden else state.repeater_id
        repeater_call = "" if overridden else state.repeater_call
        freq_tx_hz = None if overridden else state.freq_tx_hz

        with session_scope() as session:
            qso = Qso(
                operator_id=state.operator_id,
                station_id=state.station_id,
                repeater_id=repeater_id,
                repeater_call=repeater_call,
                call=callsign_module.normalize(call_raw),
                base_call=callsign_module.base_call(call_raw),
                name=str(fields.get("name", "")),
                qso_utc=timestamp,
                band=band,
                freq_hz=int(freq_hz) if freq_hz else None,
                freq_tx_hz=freq_tx_hz,
                mode=str(fields.get("mode") or state.mode or ""),
                rst_sent=str(fields.get("rst_sent", "")),
                rst_rcvd=str(fields.get("rst_rcvd", "")),
                qth=str(fields.get("qth", "")),
                gridsquare=str(fields.get("gridsquare", "")),
                country=str(fields.get("country") or callsign_module.country_for(call_raw)),
                comment=str(fields.get("comment", "")),
                power_w=fields.get("power_w"),
                entry_mode=entry_mode,
                digital_data=merged_digital,
                extra=dict(fields.get("extra", {}) or {}),
            )
            session.add(qso)
            session.flush()
            loaded = session.scalars(
                select(Qso)
                .options(
                    joinedload(Qso.operator),
                    joinedload(Qso.station),
                    joinedload(Qso.repeater),
                )
                .where(Qso.id == qso.id)
            ).one()
            row = _to_row(loaded)

        if state.add_to_book:
            _remember_in_address_book(row)
        return row

    @staticmethod
    def recent(limit: int = 200, operator_id: int | None = None) -> list[QsoRow]:
        """Most recent contacts, newest last so the panel reads top to bottom."""
        with session_scope() as session:
            stmt = (
                select(Qso)
                .options(
                    joinedload(Qso.operator),
                    joinedload(Qso.station),
                    joinedload(Qso.repeater),
                )
                .order_by(Qso.qso_utc.desc(), Qso.id.desc())
                .limit(limit)
            )
            if operator_id is not None:
                stmt = stmt.where(Qso.operator_id == operator_id)
            rows = list(session.scalars(stmt))
            return [_to_row(qso) for qso in reversed(rows)]

    @staticmethod
    def search(
        text: str = "",
        *,
        band: str | None = None,
        mode: str | None = None,
        operator_id: int | None = None,
        limit: int = 500,
    ) -> list[QsoRow]:
        """Free text search over callsign, name, QTH, country and comment."""
        with session_scope() as session:
            stmt = (
                select(Qso)
                .options(
                    joinedload(Qso.operator),
                    joinedload(Qso.station),
                    joinedload(Qso.repeater),
                )
                .order_by(Qso.qso_utc.desc(), Qso.id.desc())
                .limit(limit)
            )
            needle = text.strip()
            if needle:
                pattern = f"%{needle}%"
                stmt = stmt.where(
                    or_(
                        Qso.call.ilike(pattern),
                        Qso.name.ilike(pattern),
                        Qso.qth.ilike(pattern),
                        Qso.country.ilike(pattern),
                        Qso.comment.ilike(pattern),
                    )
                )
            if band:
                stmt = stmt.where(Qso.band == band)
            if mode:
                stmt = stmt.where(Qso.mode == mode)
            if operator_id is not None:
                stmt = stmt.where(Qso.operator_id == operator_id)
            return [_to_row(qso) for qso in session.scalars(stmt)]

    @staticmethod
    def get(qso_id: int) -> QsoRow | None:
        with session_scope() as session:
            qso = session.scalars(
                select(Qso)
                .options(
                    joinedload(Qso.operator),
                    joinedload(Qso.station),
                    joinedload(Qso.repeater),
                )
                .where(Qso.id == qso_id)
            ).first()
            return _to_row(qso) if qso else None

    @staticmethod
    def editable_fields(qso_id: int) -> frozenset[str]:
        """Which fields the edit screen may offer for this QSO."""
        with session_scope() as session:
            qso = session.get(Qso, qso_id)
            if qso is None:
                raise ServiceError("QSO no encontrado.")
            return MANUAL_EDITABLE_FIELDS if qso.is_manual else AUTO_EDITABLE_FIELDS

    @staticmethod
    def update(qso_id: int, changes: dict[str, Any]) -> QsoRow:
        """Apply changes, enforcing the automatic/manual edit rules.

        A QSO logged with the automatic clock is evidence of when the contact
        happened, so only the callsign may be corrected. A manually dated one
        was typed from paper and stays fully editable.
        """
        with session_scope() as session:
            qso = session.get(Qso, qso_id)
            if qso is None:
                raise ServiceError("QSO no encontrado.")

            allowed = MANUAL_EDITABLE_FIELDS if qso.is_manual else AUTO_EDITABLE_FIELDS
            rejected = sorted(set(changes) - allowed)
            if rejected:
                raise ServiceError(
                    "Este QSO es automático: solo se puede modificar el indicativo. "
                    f"Campos rechazados: {', '.join(rejected)}."
                )

            for key, value in changes.items():
                setattr(qso, key, value)

            if "call" in changes:
                qso.call = callsign_module.normalize(str(changes["call"]))
                qso.base_call = callsign_module.base_call(qso.call)
                detected = callsign_module.country_for(qso.call)
                if detected:
                    qso.country = detected
            if "freq_hz" in changes and changes["freq_hz"]:
                band = bands.from_frequency(int(changes["freq_hz"]))
                if band:
                    qso.band = band.name

            session.flush()
            loaded = session.scalars(
                select(Qso)
                .options(
                    joinedload(Qso.operator),
                    joinedload(Qso.station),
                    joinedload(Qso.repeater),
                )
                .where(Qso.id == qso.id)
            ).one()
            return _to_row(loaded)

    @staticmethod
    def delete(qso_id: int) -> None:
        with session_scope() as session:
            qso = session.get(Qso, qso_id)
            if qso is None:
                raise ServiceError("QSO no encontrado.")
            session.delete(qso)

    @staticmethod
    def find_duplicates(
        call: str, band: str, mode: str, *, within_minutes: int = 0
    ) -> list[QsoRow]:
        """Previous contacts with the same station on the same band and mode.

        ``within_minutes`` restricts the search to a recent window, which is
        the usual contest rule; zero means the whole log.
        """
        base = callsign_module.base_call(call)
        with session_scope() as session:
            stmt = (
                select(Qso)
                .options(
                    joinedload(Qso.operator),
                    joinedload(Qso.station),
                    joinedload(Qso.repeater),
                )
                .where(Qso.base_call == base)
                .order_by(Qso.qso_utc.desc())
            )
            if band:
                stmt = stmt.where(Qso.band == band)
            if mode:
                stmt = stmt.where(Qso.mode == mode)
            if within_minutes > 0:
                since = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(
                    minutes=within_minutes
                )
                stmt = stmt.where(Qso.qso_utc >= since)
            return [_to_row(qso) for qso in session.scalars(stmt)]

    @staticmethod
    def stats(operator_id: int | None = None) -> LogStats:
        """Aggregate counters for the footer and the metrics exporter."""
        with session_scope() as session:
            def scoped(stmt):  # type: ignore[no-untyped-def]
                return stmt.where(Qso.operator_id == operator_id) if operator_id else stmt

            total = session.scalar(scoped(select(func.count(Qso.id)))) or 0
            start_of_day = dt.datetime.now(dt.timezone.utc).replace(
                tzinfo=None, hour=0, minute=0, second=0, microsecond=0
            )
            today = (
                session.scalar(
                    scoped(select(func.count(Qso.id))).where(Qso.qso_utc >= start_of_day)
                )
                or 0
            )
            unique_calls = (
                session.scalar(scoped(select(func.count(func.distinct(Qso.base_call))))) or 0
            )
            countries = (
                session.scalar(
                    scoped(select(func.count(func.distinct(Qso.country)))).where(Qso.country != "")
                )
                or 0
            )
            by_band = dict(
                session.execute(
                    scoped(select(Qso.band, func.count(Qso.id))).group_by(Qso.band)
                ).all()
            )
            by_mode = dict(
                session.execute(
                    scoped(select(Qso.mode, func.count(Qso.id))).group_by(Qso.mode)
                ).all()
            )
            return LogStats(
                total=total,
                today=today,
                unique_calls=unique_calls,
                countries=countries,
                by_band={k: v for k, v in by_band.items() if k},
                by_mode={k: v for k, v in by_mode.items() if k},
            )


# --------------------------------------------------------------------------- #
# Address book
# --------------------------------------------------------------------------- #

def _contact_to_row(contact: Contact, qso_count: int = 0) -> ContactRow:
    """Convert an address book entry into the UI/API shape."""
    return ContactRow(
        id=contact.id,
        callsign=contact.callsign,
        first_name=contact.first_name,
        last_name=contact.last_name,
        dmr_id=contact.dmr_id,
        city=contact.city,
        state=contact.state,
        country=contact.country,
        gridsquare=contact.gridsquare,
        email=contact.email,
        notes=contact.notes,
        source=contact.source,
        is_favorite=contact.is_favorite,
        qso_count=qso_count,
    )


class ContactService:
    """The address book.

    Entries usually arrive in bulk from a DMR user list, so imports are
    written in batches and lookups go through indexed columns: a list of the
    whole of Spain is tens of thousands of rows and the entry line queries it
    on every keystroke.
    """

    #: Rows per INSERT batch during an import.
    BATCH_SIZE = 1_000

    @staticmethod
    def lookup(call: str) -> ContactRow | None:
        """Find a station by callsign, ignoring portable prefixes.

        This runs while the operator types, so it must stay cheap.
        """
        base = callsign_module.base_call(call)
        if len(base) < 3:
            return None
        with session_scope() as session:
            contact = session.scalars(
                select(Contact).where(Contact.base_call == base).limit(1)
            ).first()
            return _contact_to_row(contact) if contact else None

    @staticmethod
    def lookup_by_dmr_id(dmr_id: int) -> ContactRow | None:
        with session_scope() as session:
            contact = session.scalars(
                select(Contact).where(Contact.dmr_id == dmr_id)
            ).first()
            return _contact_to_row(contact) if contact else None

    @staticmethod
    def get(contact_id: int) -> ContactRow | None:
        with session_scope() as session:
            contact = session.get(Contact, contact_id)
            return _contact_to_row(contact) if contact else None

    @staticmethod
    def search(text: str = "", *, limit: int = 500, with_counts: bool = True) -> list[ContactRow]:
        """Search by callsign, name, city, country or DMR ID."""
        with session_scope() as session:
            stmt = select(Contact).order_by(
                Contact.is_favorite.desc(), Contact.callsign
            ).limit(limit)
            needle = text.strip()
            if needle:
                pattern = f"%{needle}%"
                conditions = [
                    Contact.callsign.ilike(pattern),
                    Contact.first_name.ilike(pattern),
                    Contact.last_name.ilike(pattern),
                    Contact.city.ilike(pattern),
                    Contact.country.ilike(pattern),
                ]
                if needle.isdigit():
                    conditions.append(Contact.dmr_id == int(needle))
                stmt = stmt.where(or_(*conditions))
            contacts = list(session.scalars(stmt))

            counts: dict[str, int] = {}
            if with_counts and contacts:
                # One grouped query rather than one per row.
                calls = {contact.base_call for contact in contacts if contact.base_call}
                if calls:
                    counts = dict(
                        session.execute(
                            select(Qso.base_call, func.count(Qso.id))
                            .where(Qso.base_call.in_(calls))
                            .group_by(Qso.base_call)
                        ).all()
                    )
            return [
                _contact_to_row(contact, counts.get(contact.base_call, 0))
                for contact in contacts
            ]

    @staticmethod
    def count() -> int:
        with session_scope() as session:
            return session.scalar(select(func.count(Contact.id))) or 0

    @staticmethod
    def create(
        call: str,
        *,
        first_name: str = "",
        last_name: str = "",
        dmr_id: int | None = None,
        city: str = "",
        state: str = "",
        country: str = "",
        gridsquare: str = "",
        email: str = "",
        notes: str = "",
        source: str = "manual",
    ) -> ContactRow:
        normalized = callsign_module.normalize(call)
        if not normalized:
            raise ServiceError("El indicativo no puede estar vacío.")
        with session_scope() as session:
            base = callsign_module.base_call(normalized)
            if session.scalars(select(Contact).where(Contact.base_call == base)).first():
                raise ServiceError(f"{base} ya está en la agenda.")
            if dmr_id is not None:
                clash = session.scalars(
                    select(Contact).where(Contact.dmr_id == dmr_id)
                ).first()
                if clash is not None:
                    raise ServiceError(f"El ID DMR {dmr_id} ya es de {clash.callsign}.")
            contact = Contact(
                callsign=normalized,
                base_call=base,
                dmr_id=dmr_id,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                city=city.strip(),
                state=state.strip(),
                country=country.strip() or callsign_module.country_for(normalized),
                gridsquare=gridsquare.strip().upper(),
                email=email.strip(),
                notes=notes.strip(),
                source=source,
            )
            session.add(contact)
            session.flush()
            return _contact_to_row(contact)

    @staticmethod
    def update(contact_id: int, **changes: Any) -> ContactRow:
        with session_scope() as session:
            contact = session.get(Contact, contact_id)
            if contact is None:
                raise ServiceError("Contacto no encontrado en la agenda.")
            if "callsign" in changes:
                contact.callsign = callsign_module.normalize(str(changes.pop("callsign")))
                contact.base_call = callsign_module.base_call(contact.callsign)
            for key, value in changes.items():
                if hasattr(contact, key):
                    setattr(contact, key, value)
            session.flush()
            return _contact_to_row(contact)

    @staticmethod
    def delete(contact_id: int) -> None:
        with session_scope() as session:
            contact = session.get(Contact, contact_id)
            if contact is None:
                raise ServiceError("Contacto no encontrado en la agenda.")
            session.delete(contact)

    @staticmethod
    def clear(source: str | None = None) -> int:
        """Empty the address book, or just the entries from one source.

        Returns:
            How many entries were removed.
        """
        with session_scope() as session:
            stmt = session.query(Contact)
            if source:
                stmt = stmt.filter(Contact.source == source)
            removed = stmt.delete(synchronize_session=False)
            return int(removed or 0)

    @staticmethod
    def sources() -> dict[str, int]:
        """How many entries came from each source."""
        with session_scope() as session:
            return dict(
                session.execute(
                    select(Contact.source, func.count(Contact.id)).group_by(Contact.source)
                ).all()
            )
