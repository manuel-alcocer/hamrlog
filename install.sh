#!/usr/bin/env bash
#
# Installs hamrlog into an isolated environment and puts the command on PATH.
#
# Works on any Linux (and macOS) with Python 3.10 or newer. Prefers uv, then
# pipx, and falls back to a plain virtual environment so the script never
# depends on a tool the user may not have.
#
#   ./install.sh              install or upgrade
#   ./install.sh --uninstall  remove it again
#
set -euo pipefail

REPO="https://github.com/manuel-alcocer/hamrlog"
PACKAGE="hamrlog"
VENV_DIR="${HAMRLOG_VENV:-$HOME/.local/share/hamrlog-venv}"
BIN_DIR="${HAMRLOG_BIN:-$HOME/.local/bin}"
MIN_PYTHON="3.10"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m==>\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[1;31m==>\033[0m %s\n' "$*" >&2; exit 1; }

# Source directory when run from a clone, otherwise install straight from git.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    SOURCE="$SCRIPT_DIR"
else
    SOURCE="git+$REPO"
fi

find_python() {
    local candidate
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

uninstall() {
    info "Desinstalando $PACKAGE"
    if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "$PACKAGE"; then
        pipx uninstall "$PACKAGE"
    fi
    rm -rf "$VENV_DIR"
    rm -f "$BIN_DIR/$PACKAGE"
    info "Hecho. Tus datos siguen en ~/.local/share/hamrlog (bórralos a mano si quieres)."
    exit 0
}

[[ "${1:-}" == "--uninstall" ]] && uninstall

if command -v uv >/dev/null 2>&1; then
    info "Instalando con uv"
    uv tool install --force "$SOURCE"
    HAMRLOG_PATH="$(command -v hamrlog || echo "$HOME/.local/bin/hamrlog")"
elif command -v pipx >/dev/null 2>&1; then
    info "Instalando con pipx"
    pipx install --force "$SOURCE"
    HAMRLOG_PATH="$(command -v hamrlog || echo "$HOME/.local/bin/hamrlog")"
else
    PYTHON="$(find_python)" || die "Hace falta Python $MIN_PYTHON o superior. Instálalo y vuelve a ejecutar."
    info "Instalando con $PYTHON en $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet "$SOURCE"
    mkdir -p "$BIN_DIR"
    ln -sf "$VENV_DIR/bin/hamrlog" "$BIN_DIR/$PACKAGE"
    HAMRLOG_PATH="$BIN_DIR/$PACKAGE"
fi

info "Instalado: $HAMRLOG_PATH"

if ! command -v hamrlog >/dev/null 2>&1; then
    warn "$BIN_DIR no está en el PATH. Añade esta línea a tu ~/.bashrc o ~/.zshrc:"
    printf '\n    export PATH="%s:$PATH"\n\n' "$BIN_DIR"
fi

info "Arráncalo con:  hamrlog"
