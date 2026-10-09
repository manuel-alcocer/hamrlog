#!/usr/bin/env bash
#
# Linux installer for hamrlog: installs, upgrades and uninstalls the
# self-contained executable published with each release. Needs no Python.
#
#   ./install.sh                      install the hamrlog next to this script,
#                                     or download the latest release
#   ./install.sh --upgrade            download and install the latest release
#   ./install.sh --uninstall          remove it; the log stays
#   ./install.sh --uninstall --purge  remove it along with the log and settings
#
# Straight from the web:
#   curl -fsSL https://github.com/manuel-alcocer/hamrlog/releases/latest/download/hamrlog-install.sh | bash
#
set -euo pipefail

APP="hamrlog"
PLATFORM="linux-x86_64"
RELEASES_URL="${HAMRLOG_RELEASES_URL:-https://github.com/manuel-alcocer/hamrlog/releases}"

# Messages follow the locale, like the application does.
case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
    es*) SPANISH=1 ;;
    *) SPANISH=0 ;;
esac

# Prints the English or the Spanish text.
t() { if [[ $SPANISH == 1 ]]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m==>\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m==>\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    if [[ $SPANISH == 1 ]]; then
        cat <<'EOF'
Uso: install.sh [opciones]

  (sin opciones)     Instala el hamrlog que acompaña al script o, si no hay
                     ninguno, descarga la última versión. Si ya hay una
                     instalada más antigua, la actualiza.
  --upgrade          Descarga la última versión y actualiza la instalada.
  --uninstall        Desinstala hamrlog. El diario y la configuración se quedan.
  --purge            Desinstala y borra también el diario y la configuración.
  --status           Muestra la versión instalada.
  --version X.Y.Z    Descarga esa versión en lugar de la última.
  --system           Instala para todos los usuarios en /usr/local (con sudo).
  --prefix DIR       Instala en DIR (por defecto ~/.local).
  --force            Reinstala la misma versión, permite volver a una anterior
                     o sustituye un hamrlog instalado por otro medio.
  -y, --yes          No pide confirmación antes de borrar datos.
  -h, --help         Muestra esta ayuda.
EOF
    else
        cat <<'EOF'
Usage: install.sh [options]

  (no options)       Install the hamrlog shipped with this script or, when
                     there is none, download the latest release. An older
                     installed version is upgraded.
  --upgrade          Download the latest release and upgrade to it.
  --uninstall        Uninstall hamrlog. The log and settings stay.
  --purge            Uninstall and delete the log and settings as well.
  --status           Show the installed version.
  --version X.Y.Z    Download that version instead of the latest.
  --system           Install for every user in /usr/local (with sudo).
  --prefix DIR       Install under DIR (default ~/.local).
  --force            Reinstall the same version, go back to an older one or
                     replace a hamrlog installed by other means.
  -y, --yes          Do not ask before deleting data.
  -h, --help         Show this help.
EOF
    fi
}

action="install"
prefix=""
system=0
pinned_version=""
purge=0
force=0
assume_yes=0

while (($#)); do
    case "$1" in
        --upgrade) action="upgrade" ;;
        --uninstall) action="uninstall" ;;
        --purge) action="uninstall"; purge=1 ;;
        --status) action="status" ;;
        --system) system=1 ;;
        --prefix)
            [[ $# -ge 2 ]] || die "$(t "--prefix needs a directory" "--prefix necesita un directorio")"
            prefix="$2"; shift ;;
        --prefix=*) prefix="${1#*=}" ;;
        --version)
            [[ $# -ge 2 ]] || die "$(t "--version needs a number" "--version necesita un número")"
            pinned_version="${2#v}"; shift ;;
        --version=*) pinned_version="${1#*=}"; pinned_version="${pinned_version#v}" ;;
        --force) force=1 ;;
        -y|--yes) assume_yes=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "$(t "Unknown option: $1 (see --help)" "Opción desconocida: $1 (mira --help)")" ;;
    esac
    shift
done

if [[ -z $prefix ]]; then
    if ((system)); then prefix="/usr/local"; else prefix="$HOME/.local"; fi
fi
if ((system)) && [[ $EUID -ne 0 ]]; then
    die "$(t "--system needs root: run it with sudo" "--system necesita ser root: ejecútalo con sudo")"
fi

BIN_DIR="$prefix/bin"
BIN="$BIN_DIR/$APP"
DESKTOP_DIR="$prefix/share/applications"
DESKTOP="$DESKTOP_DIR/$APP.desktop"
# What this installer put on disk, so uninstalling removes exactly that.
STATE_DIR="$prefix/lib/$APP"
MANIFEST="$STATE_DIR/manifest"
VERSION_FILE="$STATE_DIR/version"

# The same folders as hamrlog.paths, for --purge.
DATA_DIR="${HAMRLOG_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/$APP}"
CONFIG_DIR="${HAMRLOG_HOME:-${XDG_CONFIG_HOME:-$HOME/.config}/$APP}"

# A binary next to the script means the script came inside a release tarball.
SCRIPT_DIR=""
if [[ -n ${BASH_SOURCE[0]:-} && -f ${BASH_SOURCE[0]} ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

installed_version() {
    if [[ -f $VERSION_FILE ]]; then cat "$VERSION_FILE"; fi
}

# "hamrlog 0.2.0" -> "0.2.0"; empty when the binary does not run here.
version_of() {
    "$1" --version 2>/dev/null | awk '{print $2}' || true
}

# True when $1 is an older version than $2.
version_lt() {
    [[ $1 != "$2" && "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" == "$1" ]]
}

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$2" "$1"
    else
        die "$(t "curl or wget is needed to download hamrlog" "Hace falta curl o wget para descargar hamrlog")"
    fi
}

write_desktop_entry() {
    mkdir -p "$DESKTOP_DIR"
    cat >"$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=hamrlog
GenericName=Amateur radio logbook
GenericName[es]=Diario de radioaficionado
Comment=Terminal logbook for amateur radio operators
Comment[es]=Diario de contactos para radioaficionados, en modo texto
Exec="$BIN"
Icon=utilities-terminal
Terminal=true
Categories=Network;HamRadio;
Keywords=ham;radio;logbook;adif;qso;
EOF
}

refresh_desktop_database() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q "$DESKTOP_DIR" 2>/dev/null || true
    fi
}

# Installs the executable at $1: fresh install, upgrade or reinstall.
install_binary() {
    local source="$1" new current
    new="$(version_of "$source")"
    [[ -n $new ]] || die "$(t "$source does not run on this system" "$source no arranca en este sistema")"
    current="$(installed_version)"

    if [[ -n $current ]]; then
        if [[ $current == "$new" ]] && ! ((force)); then
            info "$(t "hamrlog $new is already installed in $BIN" "hamrlog $new ya está instalado en $BIN")"
            return 0
        fi
        if version_lt "$new" "$current" && ! ((force)); then
            die "$(t "hamrlog $current is installed, newer than $new. Use --force to go back." \
                     "Está instalado hamrlog $current, más nuevo que $new. Usa --force para volver atrás.")"
        fi
        if [[ $current == "$new" ]]; then
            info "$(t "Reinstalling hamrlog $new" "Reinstalando hamrlog $new")"
        else
            info "$(t "Upgrading hamrlog from $current to $new" "Actualizando hamrlog de $current a $new")"
        fi
    else
        if [[ -e $BIN || -L $BIN ]] && ! ((force)); then
            die "$(t "$BIN already exists and was not installed by this script (perhaps by the source install.sh, uv or pipx). Remove it first or use --force." \
                     "$BIN ya existe y no lo instaló este script (quizá el install.sh del código, uv o pipx). Quítalo antes o usa --force.")"
        fi
        info "$(t "Installing hamrlog $new in $BIN" "Instalando hamrlog $new en $BIN")"
    fi

    mkdir -p "$BIN_DIR" "$STATE_DIR"
    # Copy, then rename: a running hamrlog keeps its old file and nobody
    # sees a half-written one.
    install -m 755 "$source" "$BIN.new"
    mv -f "$BIN.new" "$BIN"
    write_desktop_entry
    printf '%s\n' "$BIN" "$DESKTOP" >"$MANIFEST"
    printf '%s\n' "$new" >"$VERSION_FILE"
    refresh_desktop_database

    # The demo database belongs to whoever runs it; under sudo that would be
    # root, so a system install leaves it to the first demo.
    if ! ((system)); then
        info "$(t "Preparing the demo database" "Preparando la base de datos de demostración")"
        "$BIN" build-demo >/dev/null 2>&1 ||
            warn "$(t "Could not prepare the demo; it will be built on first use." \
                      "No se pudo preparar la demo; se creará al usarla.")"
    fi

    info "$(t "Done: hamrlog $new" "Hecho: hamrlog $new")"
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            warn "$(t "$BIN_DIR is not in PATH. Add this line to ~/.bashrc or ~/.zshrc:" \
                      "$BIN_DIR no está en el PATH. Añade esta línea a ~/.bashrc o ~/.zshrc:")"
            printf '\n    export PATH="%s:$PATH"\n\n' "$BIN_DIR"
            ;;
    esac
    info "$(t "Start it with: hamrlog   (or try it with: hamrlog --demo)" \
              "Arráncalo con: hamrlog   (o pruébalo con: hamrlog --demo -l es)")"
}

# Downloads a release, checks it against SHA256SUMS.txt and installs it.
install_release() {
    local base workdir name remote current
    if [[ -n $pinned_version ]]; then
        base="$RELEASES_URL/download/v$pinned_version"
    else
        base="$RELEASES_URL/latest/download"
    fi

    workdir="$(mktemp -d)"
    # shellcheck disable=SC2064  # expand now: workdir is local
    trap "rm -rf '$workdir'" EXIT

    info "$(t "Looking for the release in $base" "Buscando la versión en $base")"
    fetch "$base/SHA256SUMS.txt" "$workdir/SHA256SUMS.txt" ||
        die "$(t "Could not download $base/SHA256SUMS.txt" "No se pudo descargar $base/SHA256SUMS.txt")"
    name="$(grep -oE "$APP-[0-9][0-9A-Za-z.]*-$PLATFORM\.tar\.gz" "$workdir/SHA256SUMS.txt" | head -n1 || true)"
    [[ -n $name ]] || die "$(t "That release has no Linux package" "Esa versión no tiene paquete para Linux")"
    remote="${name#"$APP-"}"
    remote="${remote%"-$PLATFORM.tar.gz"}"

    current="$(installed_version)"
    if [[ $current == "$remote" ]] && ! ((force)); then
        info "$(t "hamrlog $current is already the latest version" "hamrlog $current ya es la última versión")"
        return 0
    fi

    info "$(t "Downloading $name" "Descargando $name")"
    fetch "$base/$name" "$workdir/$name" ||
        die "$(t "Could not download $base/$name" "No se pudo descargar $base/$name")"
    (cd "$workdir" && grep "  $name\$" SHA256SUMS.txt | sha256sum -c --quiet - >/dev/null 2>&1) ||
        die "$(t "$name does not match its SHA-256 sum; nothing was installed" \
                 "$name no coincide con su suma SHA-256; no se ha instalado nada")"
    tar -xzf "$workdir/$name" -C "$workdir"
    install_binary "$workdir/$APP-$remote-$PLATFORM/$APP"
}

uninstall() {
    local current
    current="$(installed_version)"
    if [[ -n $current ]]; then
        info "$(t "Uninstalling hamrlog $current from $prefix" "Desinstalando hamrlog $current de $prefix")"
        while IFS= read -r file; do
            [[ -n $file ]] && rm -f -- "$file"
        done <"$MANIFEST"
        rm -rf -- "$STATE_DIR"
        refresh_desktop_database
    elif ((purge)); then
        warn "$(t "hamrlog is not installed in $prefix; deleting its data only" \
                  "hamrlog no está instalado en $prefix; solo se borran sus datos")"
    else
        die "$(t "hamrlog is not installed in $prefix (installed with --system or --prefix?)" \
                 "hamrlog no está instalado en $prefix (¿se instaló con --system o --prefix?)")"
    fi

    if ! ((purge)); then
        info "$(t "Done. Your log stays in $DATA_DIR" "Hecho. Tu diario sigue en $DATA_DIR")"
        return 0
    fi

    if ! ((assume_yes)); then
        local answer=""
        printf '%s ' "$(t "Delete $DATA_DIR and $CONFIG_DIR, with every QSO in them? [y/N]" \
                          "¿Borrar $DATA_DIR y $CONFIG_DIR, con todos los QSO que contienen? [s/N]")"
        read -r answer </dev/tty ||
            die "$(t "No terminal to confirm; add --yes" "No hay terminal para confirmar; añade --yes")"
        case "$answer" in
            [yYsS]*) ;;
            *) info "$(t "Data kept in $DATA_DIR" "Datos conservados en $DATA_DIR")"; return 0 ;;
        esac
    fi
    rm -rf -- "$DATA_DIR" "$CONFIG_DIR"
    info "$(t "Data deleted" "Datos borrados")"
}

case "$action" in
    status)
        current="$(installed_version)"
        if [[ -n $current ]]; then
            echo "hamrlog $current ($BIN)"
        else
            echo "$(t "hamrlog is not installed in $prefix" "hamrlog no está instalado en $prefix")"
            exit 1
        fi
        ;;
    uninstall)
        uninstall
        ;;
    upgrade)
        [[ -n $(installed_version) ]] ||
            die "$(t "hamrlog is not installed in $prefix; run without --upgrade to install it" \
                     "hamrlog no está instalado en $prefix; ejecuta sin --upgrade para instalarlo")"
        install_release
        ;;
    install)
        if [[ -z $pinned_version && -n $SCRIPT_DIR && -f $SCRIPT_DIR/$APP && -x $SCRIPT_DIR/$APP ]]; then
            install_binary "$SCRIPT_DIR/$APP"
        else
            install_release
        fi
        ;;
esac
