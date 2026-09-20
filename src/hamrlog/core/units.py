"""Frequency units and number formatting.

Every frequency the operator reads or types goes through here, so the whole
application agrees on units and separators and the preference is set in one
place. Frequencies are stored as integer hertz regardless; this is
presentation only.

ADIF export does not use any of it: the specification fixes megahertz with a
dot, and a file has to be readable by other programs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Canonical unit suffixes. The operator may type any capitalisation, and any
#: of them may be written with or without the "Hz" part.
UNIT_MHZ = "MHz"
UNIT_KHZ = "KHz"
UNIT_HZ = "Hz"

#: Unit -> how many hertz one of it is worth.
UNIT_SCALE: dict[str, int] = {
    UNIT_MHZ: 1_000_000,
    UNIT_KHZ: 1_000,
    UNIT_HZ: 1,
}

#: Unit -> (minimum, maximum) decimals shown. Megahertz keeps three so a
#: frequency reads at kilohertz resolution, which is how radios show it.
UNIT_DECIMALS: dict[str, tuple[int, int]] = {
    UNIT_MHZ: (3, 6),
    UNIT_KHZ: (0, 3),
    UNIT_HZ: (0, 0),
}

UNITS: tuple[str, ...] = (UNIT_MHZ, UNIT_KHZ, UNIT_HZ)

#: Separators offered for the thousands group. The empty string hides it.
THOUSANDS_SEPARATORS: tuple[str, ...] = (".", ",", " ", "'", "")
DECIMAL_SEPARATORS: tuple[str, ...] = (".", ",")

#: Spelling of "hidden" accepted in the settings screen.
HIDDEN_WORDS: frozenset[str] = frozenset(
    {"ocultar", "oculto", "ninguno", "ninguna", "no", "none", "hidden", "-"}
)

# Leading prefix letter plus an optional "hz" in any capitalisation.
_UNIT_RE = re.compile(r"^(?P<prefix>[mkMK]?)(?P<hz>[hH][zZ])?$")


class UnitError(ValueError):
    """Raised when a unit or a separator choice cannot be used."""


def normalize_unit(text: str) -> str:
    """Turn what the operator typed into a canonical unit.

    ``m``, ``M``, ``mhz``, ``MHZ`` all become ``MHz``; ``k`` and ``khz``
    become ``KHz``; ``hz``, ``HZ`` and ``hZ`` become ``Hz``.

    Raises:
        UnitError: When the text is not a frequency unit.
    """
    match = _UNIT_RE.match(text.strip())
    if match is None:
        raise UnitError(
            f"«{text.strip()}» no es una unidad de frecuencia. Usa M, K o Hz."
        )

    prefix = match.group("prefix").upper()
    if prefix == "M":
        return UNIT_MHZ
    if prefix == "K":
        return UNIT_KHZ
    if match.group("hz"):
        return UNIT_HZ
    raise UnitError("Falta la unidad. Usa M, K o Hz.")


def describe_separator(separator: str) -> str:
    """Name a separator for the settings screen."""
    if separator == "":
        return "ocultar"
    if separator == " ":
        return "espacio"
    return separator


def parse_separator(text: str, *, allow_hidden: bool) -> str:
    """Read a separator as written in the settings screen.

    Raises:
        UnitError: When it is neither a single character nor "ocultar".
    """
    cleaned = text.strip()
    lowered = cleaned.lower()
    if lowered in HIDDEN_WORDS:
        if not allow_hidden:
            raise UnitError("El separador decimal no se puede ocultar.")
        return ""
    if lowered in ("espacio", "space"):
        return " "
    if len(cleaned) != 1:
        return _reject(cleaned, allow_hidden)
    if allow_hidden and cleaned not in THOUSANDS_SEPARATORS:
        return _reject(cleaned, allow_hidden)
    if not allow_hidden and cleaned not in DECIMAL_SEPARATORS:
        return _reject(cleaned, allow_hidden)
    return cleaned


def _reject(text: str, allow_hidden: bool) -> str:
    options = "  .  ,  espacio  '  ocultar" if allow_hidden else "  .  ,"
    raise UnitError(f"«{text}» no vale como separador. Opciones:{options}")


@dataclass(frozen=True, slots=True)
class FrequencyFormat:
    """How frequencies are shown and how a bare number is read.

    Attributes:
        unit: Unit used when displaying, and assumed when the operator types
            a number with no unit of its own.
        decimal: Decimal separator.
        thousands: Thousands separator, empty to hide the grouping.
    """

    unit: str = UNIT_MHZ
    decimal: str = "."
    thousands: str = ""

    def __post_init__(self) -> None:
        if self.unit not in UNIT_SCALE:
            raise UnitError(f"Unidad desconocida: «{self.unit}».")
        if self.decimal not in DECIMAL_SEPARATORS:
            raise UnitError(f"Separador decimal no válido: «{self.decimal}».")
        if self.thousands not in THOUSANDS_SEPARATORS:
            raise UnitError(f"Separador de millar no válido: «{self.thousands}».")
        if self.thousands and self.thousands == self.decimal:
            raise UnitError(
                "El separador de millar y el decimal no pueden ser el mismo "
                f"(«{self.decimal}»)."
            )

    # ------------------------------------------------------------- format --
    def format(self, freq_hz: int | None, *, with_unit: bool = True) -> str:
        """Render hertz in the configured unit, e.g. '7.130 MHz'."""
        if not freq_hz:
            return "-"

        scale = UNIT_SCALE[self.unit]
        minimum, maximum = UNIT_DECIMALS[self.unit]

        whole, remainder = divmod(abs(freq_hz), scale)
        decimals = ""
        if maximum:
            decimals = f"{remainder:0{len(str(scale)) - 1}d}"[:maximum]
            decimals = decimals.rstrip("0")
            while len(decimals) < minimum:
                decimals += "0"

        rendered = self._group(whole)
        if decimals:
            rendered = f"{rendered}{self.decimal}{decimals}"
        if freq_hz < 0:
            rendered = f"-{rendered}"
        return f"{rendered} {self.unit}" if with_unit else rendered

    def _group(self, value: int) -> str:
        """Insert the thousands separator, or not when it is hidden."""
        digits = str(value)
        if not self.thousands:
            return digits
        groups = []
        while len(digits) > 3:
            groups.insert(0, digits[-3:])
            digits = digits[:-3]
        groups.insert(0, digits)
        return self.thousands.join(groups)

    # -------------------------------------------------------------- parse --
    def parse(self, text: str) -> int | None:
        """Read a frequency the operator typed, in hertz.

        A unit written by hand wins over the configured one, so ``7130 k``
        means kilohertz even when the preference is megahertz. Without a unit
        the configured one is assumed.

        Returns:
            The frequency in hertz, or None when it cannot be understood.
        """
        raw = text.strip()
        if not raw:
            return None

        # Split off a trailing unit, which may be glued to the number.
        match = re.match(r"^(?P<number>[^A-Za-z]*)(?P<unit>[A-Za-z ]*)$", raw)
        if match is None:
            return None
        number = match.group("number").strip()
        unit_text = match.group("unit").strip()

        unit = self.unit
        if unit_text:
            try:
                unit = normalize_unit(unit_text)
            except UnitError:
                return None
        if not number:
            return None

        # Drop the thousands separator, then normalise the decimal one. Spaces
        # and apostrophes always group, whatever the preference says.
        cleaned = number.replace(" ", "").replace("'", "")
        if self.thousands and self.thousands not in (" ", "'"):
            cleaned = cleaned.replace(self.thousands, "")
        cleaned = cleaned.replace(self.decimal, ".")
        if cleaned.count(".") > 1:
            return None

        try:
            value = float(cleaned)
        except ValueError:
            return None
        return int(round(value * UNIT_SCALE[unit]))

    # --------------------------------------------------------------- help --
    @property
    def example(self) -> str:
        """A sample value, for placeholders and help text."""
        return self.format(14_250_000)

    @property
    def summary(self) -> str:
        """One line describing the settings, for the configuration screen."""
        return (
            f"unidad {self.unit} · decimal «{self.decimal}» · "
            f"millar {describe_separator(self.thousands)}"
        )


#: Format in use. Presentation state, set once from the session settings at
#: startup so every widget and helper agrees without threading it through.
_active = FrequencyFormat()


def active() -> FrequencyFormat:
    return _active


def set_active(frequency_format: FrequencyFormat) -> None:
    global _active
    _active = frequency_format
