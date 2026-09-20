"""Callsign normalisation, validation and prefix lookup.

The DXCC table is deliberately small: it covers the prefixes a European
operator meets daily and degrades to "unknown" rather than guessing. Replacing
it with a full cty.dat parser later only requires changing ``country_for``.
"""

from __future__ import annotations

import re

#: Structure of a callsign: a prefix of up to three alphanumerics, the digit
#: that separates prefix from suffix, and a suffix of up to four characters
#: ending in a letter. This admits the shapes that actually exist — EA7WM,
#: K1ABC, 9A1AA, 3DA0RS, VP2E and special event calls such as AM500ITU —
#: while rejecting typos like "EA77" or "QWERTY".
#: Portable indicators (EA7WM/P, F/EA7WM) are stripped before matching.
CALLSIGN_RE = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]$")

#: Characters a callsign may contain at all, before splitting on slashes.
_ALLOWED_RE = re.compile(r"^[A-Z0-9/]+$")

_COMMON_SUFFIXES = {"P", "M", "MM", "AM", "QRP", "A", "B", "R"}

#: Appending this to a callsign accepts it even if it fails validation, for
#: the genuinely unusual call that no reasonable pattern covers.
OVERRIDE_MARKER = "!"

# Prefix -> (entity name, ISO-ish DXCC label). Longest prefix wins.
_PREFIXES: dict[str, str] = {
    "EA": "España", "EB": "España", "EC": "España", "ED": "España",
    "EE": "España", "EF": "España", "EG": "España", "EH": "España",
    "AM": "España", "AN": "España", "AO": "España",
    "CT": "Portugal", "CR": "Portugal", "CS": "Portugal", "CQ": "Portugal",
    "F": "Francia", "TM": "Francia", "TK": "Córcega",
    "I": "Italia", "IZ": "Italia", "IK": "Italia", "IW": "Italia",
    "DL": "Alemania", "DK": "Alemania", "DJ": "Alemania", "DB": "Alemania",
    "DD": "Alemania", "DF": "Alemania", "DG": "Alemania", "DH": "Alemania",
    "DO": "Alemania", "DM": "Alemania", "DA": "Alemania",
    "G": "Inglaterra", "M": "Inglaterra", "2E": "Inglaterra",
    "GM": "Escocia", "MM": "Escocia", "GW": "Gales", "MW": "Gales",
    "GI": "Irlanda del Norte", "GD": "Isla de Man", "GJ": "Jersey", "GU": "Guernsey",
    "EI": "Irlanda", "EJ": "Irlanda",
    "ON": "Bélgica", "OO": "Bélgica", "PA": "Países Bajos", "PD": "Países Bajos",
    "PE": "Países Bajos", "PI": "Países Bajos",
    "LX": "Luxemburgo", "HB": "Suiza", "HB0": "Liechtenstein", "OE": "Austria",
    "SP": "Polonia", "SQ": "Polonia", "OK": "Chequia", "OL": "Chequia",
    "OM": "Eslovaquia", "HA": "Hungría", "HG": "Hungría",
    "S5": "Eslovenia", "9A": "Croacia", "E7": "Bosnia-Herzegovina",
    "YU": "Serbia", "YT": "Serbia", "Z3": "Macedonia del Norte", "ZA": "Albania",
    "SV": "Grecia", "SY": "Grecia", "SZ": "Grecia", "5B": "Chipre", "C4": "Chipre",
    "TA": "Turquía", "YM": "Turquía", "LZ": "Bulgaria", "YO": "Rumanía", "YR": "Rumanía",
    "ER": "Moldavia", "UR": "Ucrania", "UT": "Ucrania", "UY": "Ucrania", "US": "Ucrania",
    "EU": "Bielorrusia", "EV": "Bielorrusia", "EW": "Bielorrusia",
    "R": "Rusia", "UA": "Rusia", "RA": "Rusia", "RK": "Rusia", "RV": "Rusia",
    "LY": "Lituania", "YL": "Letonia", "ES": "Estonia",
    "OH": "Finlandia", "OH0": "Islas Aland", "OF": "Finlandia",
    "SM": "Suecia", "SA": "Suecia", "SK": "Suecia", "8S": "Suecia",
    "LA": "Noruega", "LB": "Noruega", "LN": "Noruega", "JW": "Svalbard",
    "OZ": "Dinamarca", "OU": "Dinamarca", "OY": "Islas Feroe", "OX": "Groenlandia",
    "TF": "Islandia",
    "9H": "Malta", "1A": "S.M.O.M.", "HV": "Vaticano", "T7": "San Marino",
    "3A": "Mónaco", "C3": "Andorra", "ZB": "Gibraltar",
    "CN": "Marruecos", "7X": "Argelia", "3V": "Túnez", "5A": "Libia", "SU": "Egipto",
    "EA8": "Islas Canarias", "EA9": "Ceuta y Melilla", "EA6": "Islas Baleares",
    "CT3": "Madeira", "CU": "Azores",
    "K": "Estados Unidos", "W": "Estados Unidos", "N": "Estados Unidos",
    "AA": "Estados Unidos", "AB": "Estados Unidos", "AC": "Estados Unidos",
    "KH6": "Hawái", "KL7": "Alaska", "KP4": "Puerto Rico",
    "VE": "Canadá", "VA": "Canadá", "VO": "Canadá", "VY": "Canadá",
    "XE": "México", "LU": "Argentina", "PY": "Brasil", "PP": "Brasil", "PU": "Brasil",
    "CE": "Chile", "CX": "Uruguay", "CP": "Bolivia", "OA": "Perú", "HK": "Colombia",
    "YV": "Venezuela", "HC": "Ecuador", "ZP": "Paraguay",
    "CO": "Cuba", "CM": "Cuba", "HI": "República Dominicana", "TI": "Costa Rica",
    "JA": "Japón", "JH": "Japón", "JR": "Japón", "JE": "Japón", "JF": "Japón",
    "BY": "China", "BG": "China", "BH": "China", "BD": "China",
    "HL": "Corea del Sur", "DS": "Corea del Sur", "BV": "Taiwán",
    "VK": "Australia", "ZL": "Nueva Zelanda", "YB": "Indonesia", "DU": "Filipinas",
    "9M": "Malasia", "HS": "Tailandia", "9V": "Singapur", "VU": "India",
    "4X": "Israel", "4Z": "Israel", "A4": "Omán", "A6": "Emiratos Árabes Unidos",
    "A7": "Catar", "A9": "Baréin", "HZ": "Arabia Saudí", "9K": "Kuwait",
    "ZS": "Sudáfrica", "5Z": "Kenia", "5H": "Tanzania", "TR": "Gabón",
    "D2": "Angola", "C9": "Mozambique", "3B8": "Mauricio", "FR": "Reunión",
}

# Longest prefixes first so EA8 beats EA and KH6 beats K.
_SORTED_PREFIXES = sorted(_PREFIXES, key=len, reverse=True)


def normalize(raw: str) -> str:
    """Upper-case and strip a callsign, keeping portable indicators intact."""
    return raw.strip().upper().replace(" ", "")


def base_call(raw: str) -> str:
    """Return the home callsign, dropping prefixes and portable suffixes.

    ``F/EA7WM/P`` becomes ``EA7WM``. The longest slash-separated part that
    looks like a full callsign wins, which is how DX clusters resolve it.
    """
    call = normalize(raw)
    if "/" not in call:
        return call

    parts = [part for part in call.split("/") if part]
    candidates = [part for part in parts if part not in _COMMON_SUFFIXES and len(part) > 2]
    if not candidates:
        return parts[0] if parts else call
    # Prefer a part that matches the callsign shape, else the longest one.
    for part in candidates:
        if CALLSIGN_RE.match(part):
            return part
    return max(candidates, key=len)


def is_valid(raw: str) -> bool:
    """True when the callsign has a plausible structure."""
    return validate(raw) is None


def validate(raw: str) -> str | None:
    """Check a callsign and explain what is wrong with it.

    The point is to catch typing mistakes during a fast session, not to
    enforce licensing rules. The message names the actual problem so the
    operator can fix it without guessing.

    Returns:
        None when the callsign is acceptable, otherwise the reason it is not.
    """
    call = normalize(raw)
    if not call:
        return "Falta el indicativo."
    if not _ALLOWED_RE.match(call):
        invalid = sorted({c for c in call if not c.isalnum() and c != "/"})
        return (
            f"«{call}» contiene caracteres no permitidos ({' '.join(invalid)}). "
            "Un indicativo solo lleva letras, números y la barra de portable."
        )

    base = base_call(call)
    if not base:
        return f"«{call}» no contiene ningún indicativo."
    if len(base) < 3:
        return f"«{base}» es demasiado corto para ser un indicativo."
    if len(base) > 8:
        return f"«{base}» es demasiado largo para ser un indicativo."
    if not any(character.isdigit() for character in base):
        return (
            f"«{base}» no lleva ningún número. Todo indicativo tiene un dígito "
            "que separa el prefijo del sufijo, como en EA7WM."
        )
    if CALLSIGN_RE.match(base):
        return None
    return (
        f"«{base}» no tiene forma de indicativo. Se espera prefijo, dígito y "
        f"sufijo, como EA7WM o 9A1AA. Añade «{OVERRIDE_MARKER}» al final para "
        "registrarlo de todos modos."
    )


def strip_override(raw: str) -> tuple[str, bool]:
    """Split a trailing override marker off a callsign.

    Returns:
        The callsign without the marker, and whether it was present.
    """
    call = raw.strip()
    if call.endswith(OVERRIDE_MARKER):
        return call[: -len(OVERRIDE_MARKER)].strip(), True
    return call, False


def dx_prefix(raw: str) -> str:
    """Return the prefix used for country lookup.

    For ``F/EA7WM`` the operating prefix is ``F``, so a leading slash segment
    shorter than the base call takes precedence.
    """
    call = normalize(raw)
    if "/" in call:
        parts = [part for part in call.split("/") if part]
        head = parts[0]
        if head and head not in _COMMON_SUFFIXES and not CALLSIGN_RE.match(head):
            return head
    return base_call(call)


def country_for(raw: str) -> str:
    """Best-effort DXCC entity name, or an empty string when unknown."""
    prefix = dx_prefix(raw)
    if not prefix:
        return ""
    for candidate in _SORTED_PREFIXES:
        if prefix.startswith(candidate):
            return _PREFIXES[candidate]
    return ""
