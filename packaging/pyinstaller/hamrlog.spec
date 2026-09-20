# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for a self-contained hamrlog executable.

Produces one file that runs without Python installed, which is the point for
Windows users. Textual loads its widgets and stylesheets dynamically, so it
has to be collected whole rather than left to the import analyser.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = Path(SPECPATH)
PROJECT_DIR = SPEC_DIR.parent.parent
SRC_DIR = PROJECT_DIR / "src"

# Textual reads .tcss files and imports widgets by name at runtime.
textual_datas, textual_binaries, textual_hidden = collect_all("textual")

datas = textual_datas + [
    # The application stylesheet, read through importlib.resources.
    (str(SRC_DIR / "hamrlog" / "tui" / "styles.tcss"), "hamrlog/tui"),
]

hiddenimports = (
    textual_hidden
    + collect_submodules("hamrlog")
    # SQLAlchemy resolves its dialects by name.
    + collect_submodules("sqlalchemy.dialects.sqlite")
)

a = Analysis(
    [str(SPEC_DIR / "entry.py")],
    pathex=[str(SRC_DIR)],
    binaries=textual_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Kept out to save size: the API and metrics extras are optional and a
    # bundled build is for running the terminal application.
    excludes=["tkinter", "matplotlib", "numpy", "pytest", "fastapi", "uvicorn"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="hamrlog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # A terminal application: it must keep the console it was started from.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
