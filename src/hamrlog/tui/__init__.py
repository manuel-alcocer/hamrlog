"""Textual user interface."""

import os

# The shortcuts are Alt+letter, and under the kitty keyboard protocol some
# terminals (Konsole among them) report Alt+P together with the text "p";
# Textual then drops the Alt and the app sees a plain "p". The legacy
# encoding (ESC followed by the letter) reaches the app as alt+p everywhere.
# Textual reads this once, on import, so it has to be set before any of it
# loads. setdefault leaves an explicit choice by the user alone.
os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")
