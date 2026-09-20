"""Amateur radio band plan.

Band edges follow IARU Region 1 where regions differ. Frequencies are stored
as integer hertz everywhere in the application to avoid float rounding; ADIF
export converts to megahertz only at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

KHZ = 1_000
MHZ = 1_000_000


@dataclass(frozen=True, slots=True)
class Band:
    """A single amateur band.

    Attributes:
        name: ADIF band identifier, e.g. "20m".
        low_hz: Lower edge, inclusive.
        high_hz: Upper edge, inclusive.
        default_hz: Sensible starting frequency (calling/activity centre).
        label: Human readable wavelength plus frequency range.
    """

    name: str
    low_hz: int
    high_hz: int
    default_hz: int
    label: str

    def contains(self, freq_hz: int) -> bool:
        return self.low_hz <= freq_hz <= self.high_hz


# Ordered from lowest to highest frequency; the order drives the selector list.
BANDS: tuple[Band, ...] = (
    Band("2190m", 135_700, 137_800, 136_000, "2190 m · 135,7-137,8 kHz"),
    Band("630m", 472 * KHZ, 479 * KHZ, 475 * KHZ, "630 m · 472-479 kHz"),
    Band("160m", 1_810 * KHZ, 2_000 * KHZ, 1_840 * KHZ, "160 m · 1,810-2,000 MHz"),
    Band("80m", 3_500 * KHZ, 3_800 * KHZ, 3_700 * KHZ, "80 m · 3,500-3,800 MHz"),
    Band("60m", 5_351_500, 5_366_500, 5_355 * KHZ, "60 m · 5,3515-5,3665 MHz"),
    Band("40m", 7_000 * KHZ, 7_200 * KHZ, 7_130 * KHZ, "40 m · 7,000-7,200 MHz"),
    Band("30m", 10_100 * KHZ, 10_150 * KHZ, 10_120 * KHZ, "30 m · 10,100-10,150 MHz"),
    Band("20m", 14_000 * KHZ, 14_350 * KHZ, 14_250 * KHZ, "20 m · 14,000-14,350 MHz"),
    Band("17m", 18_068 * KHZ, 18_168 * KHZ, 18_130 * KHZ, "17 m · 18,068-18,168 MHz"),
    Band("15m", 21_000 * KHZ, 21_450 * KHZ, 21_300 * KHZ, "15 m · 21,000-21,450 MHz"),
    Band("12m", 24_890 * KHZ, 24_990 * KHZ, 24_950 * KHZ, "12 m · 24,890-24,990 MHz"),
    Band("10m", 28_000 * KHZ, 29_700 * KHZ, 28_400 * KHZ, "10 m · 28,000-29,700 MHz"),
    Band("6m", 50 * MHZ, 52 * MHZ, 50_150 * KHZ, "6 m · 50-52 MHz"),
    Band("4m", 70 * MHZ, 70_500 * KHZ, 70_200 * KHZ, "4 m · 70-70,5 MHz"),
    Band("2m", 144 * MHZ, 146 * MHZ, 145_500 * KHZ, "2 m · 144-146 MHz"),
    Band("1.25m", 222 * MHZ, 225 * MHZ, 223_500 * KHZ, "1,25 m · 222-225 MHz (R2)"),
    Band("70cm", 430 * MHZ, 440 * MHZ, 433_500 * KHZ, "70 cm · 430-440 MHz"),
    Band("33cm", 902 * MHZ, 928 * MHZ, 906 * MHZ, "33 cm · 902-928 MHz (R2)"),
    Band("23cm", 1_240 * MHZ, 1_300 * MHZ, 1_297 * MHZ, "23 cm · 1240-1300 MHz"),
    Band("13cm", 2_300 * MHZ, 2_450 * MHZ, 2_320 * MHZ, "13 cm · 2300-2450 MHz"),
    Band("9cm", 3_300 * MHZ, 3_500 * MHZ, 3_400 * MHZ, "9 cm · 3300-3500 MHz"),
    Band("6cm", 5_650 * MHZ, 5_850 * MHZ, 5_760 * MHZ, "6 cm · 5650-5850 MHz"),
    Band("3cm", 10_000 * MHZ, 10_500 * MHZ, 10_368 * MHZ, "3 cm · 10,0-10,5 GHz"),
)

BY_NAME: dict[str, Band] = {band.name: band for band in BANDS}


def get(name: str) -> Band | None:
    """Look up a band by its ADIF name, case-insensitively."""
    return BY_NAME.get(name.strip().lower())


def from_frequency(freq_hz: int) -> Band | None:
    """Return the band containing ``freq_hz``, or None if out of any band."""
    for band in BANDS:
        if band.contains(freq_hz):
            return band
    return None


def format_frequency(freq_hz: int | None) -> str:
    """Render hertz as MHz with kHz resolution, e.g. 7130000 -> '7.130.000'."""
    if not freq_hz:
        return "-"
    mhz, remainder = divmod(freq_hz, MHZ)
    khz, hz = divmod(remainder, KHZ)
    return f"{mhz}.{khz:03d}.{hz:03d}"


def frequency_mhz(freq_hz: int | None) -> str:
    """Render hertz as the decimal MHz string ADIF expects, e.g. '7.130000'.

    Trailing zeros are kept: logging programs read FREQ at fixed precision and
    a trimmed '7.13' is technically valid but unusual enough to confuse some.
    """
    if not freq_hz:
        return ""
    return f"{freq_hz / MHZ:.6f}"


def parse_frequency(text: str) -> int | None:
    """Parse a user supplied frequency into hertz.

    Accepts the shapes an operator actually types: ``14.250`` and ``14,250``
    (MHz), ``7130`` (kHz), ``145500000`` (Hz), and explicit units such as
    ``433.500 MHz`` or ``7130 kHz``. Grouping dots like ``7.130.000`` are also
    understood because the status bar renders frequencies that way.
    """
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        return None

    unit = None
    for suffix, scale in (("ghz", 1_000 * MHZ), ("mhz", MHZ), ("khz", KHZ), ("hz", 1)):
        if raw.endswith(suffix):
            unit = scale
            raw = raw[: -len(suffix)]
            break

    # Two or more separators means digit grouping (7.130.000), not a decimal point.
    if raw.count(".") + raw.count(",") >= 2:
        raw = raw.replace(".", "").replace(",", "")
        unit = unit or 1
    else:
        raw = raw.replace(",", ".")

    try:
        value = float(raw)
    except ValueError:
        return None

    if unit is None:
        # No explicit unit: guess from magnitude the way logging software does.
        if "." in raw:
            unit = MHZ
        elif value >= 1_000_000:
            unit = 1
        elif value >= 1_000:
            unit = KHZ
        else:
            unit = MHZ

    return int(round(value * unit))
