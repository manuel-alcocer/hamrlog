"""Band plan and frequency parsing."""

from __future__ import annotations

import pytest

from hamrlog.core import bands


@pytest.mark.parametrize(
    ("text", "expected_hz"),
    [
        ("14.250", 14_250_000),
        ("14,250", 14_250_000),
        ("7130", 7_130_000),
        ("145500000", 145_500_000),
        ("433.500 MHz", 433_500_000),
        ("7.130.000", 7_130_000),
        ("50,150", 50_150_000),
        ("3700 kHz", 3_700_000),
        ("", None),
        ("no soy una frecuencia", None),
    ],
)
def test_parse_frequency(text, expected_hz):
    assert bands.parse_frequency(text) == expected_hz


@pytest.mark.parametrize(
    ("freq_hz", "band_name"),
    [
        (7_130_000, "40m"),
        (14_250_000, "20m"),
        (145_500_000, "2m"),
        (433_500_000, "70cm"),
        (5_000_000, None),
    ],
)
def test_band_from_frequency(freq_hz, band_name):
    band = bands.from_frequency(freq_hz)
    assert (band.name if band else None) == band_name


def test_format_frequency_groups_digits():
    assert bands.format_frequency(7_130_000) == "7.130.000"
    assert bands.format_frequency(None) == "-"


def test_adif_frequency_keeps_six_decimals():
    """LoTW and other services expect a fixed precision MHz value."""
    assert bands.frequency_mhz(7_130_000) == "7.130000"
    assert bands.frequency_mhz(None) == ""


def test_every_band_default_is_inside_its_own_edges():
    for band in bands.BANDS:
        assert band.contains(band.default_hz), band.name
