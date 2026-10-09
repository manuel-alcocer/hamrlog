"""Capitalisation of personal names and places.

Names, surnames and QTHs are stored with every word capitalised, however they
were typed: ``mAnuel angel`` becomes ``Manuel Angel``. Callsigns go the
other way, all upper case (see :func:`hamrlog.core.callsign.normalize`).
"""

from __future__ import annotations

import re

# A run of letters: a hyphen or an apostrophe starts a new one, so
# "jean-pierre" and "o'brien" give "Jean-Pierre" and "O'Brien".
_LETTERS = re.compile(r"[^\W\d_]+")


def title_case(text: str) -> str:
    """Capitalise each word of a name or a place and lower-case the rest.

    Surrounding and repeated spaces go. A word with a digit in it is left as
    typed, so a locator or a street number in a QTH keeps its letters
    (``IN80dk``, ``3B``).
    """
    words = []
    for word in text.split():
        if any(char.isdigit() for char in word):
            words.append(word)
        else:
            words.append(_LETTERS.sub(lambda match: match.group(0).capitalize(), word))
    return " ".join(words)
