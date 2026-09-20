# Empaquetado

Cómo se construyen y publican las versiones de hamrlog.

## Qué produce cada versión

Al empujar una etiqueta `v*`, el flujo `.github/workflows/release.yml` genera:

| Fichero | Para |
|---|---|
| `hamrlog-linux-x86_64` | Ejecutable de Linux, sin necesidad de Python |
| `hamrlog-windows-x86_64.exe` | Ejecutable de Windows, sin necesidad de Python |
| `hamrlog-X.Y.Z-setup.exe` | Instalador de Windows con menú Inicio y desinstalador |
| `hamrlog-X.Y.Z-py3-none-any.whl` | Paquete de Python, para `pipx install` |
| `hamrlog-X.Y.Z.tar.gz` | Código fuente empaquetado |
| `SHA256SUMS.txt` | Sumas de comprobación de todo lo anterior |

Antes de publicar nada, el flujo ejecuta las pruebas y comprueba que cada
ejecutable arranca de verdad.

## Publicar

```bash
# 1. Subir la versión en los dos sitios donde aparece
#    - pyproject.toml   -> version = "0.2.0"
#    - packaging/arch/PKGBUILD -> pkgver=0.2.0
# 2. Etiquetar y empujar
git tag -a v0.2.0 -m "v0.2.0"
git push origin v0.2.0
```

## Construir a mano

### Ejecutable autocontenido

```bash
uv sync --extra dev
uv pip install pyinstaller
uv run pyinstaller --clean --noconfirm packaging/pyinstaller/hamrlog.spec
./dist/hamrlog --version
```

El resultado ronda los 25 MB porque lleva dentro el intérprete de Python y
Textual completo. Textual carga sus widgets y hojas de estilo por nombre en
tiempo de ejecución, así que el `.spec` lo recoge entero con `collect_all` en
lugar de fiarse del análisis de importaciones.

La hoja de estilos de la aplicación se lee con `importlib.resources`, no por
ruta de fichero: dentro del paquete los módulos viven en un archivo comprimido
y `__file__` no apunta a nada del disco.

### Instalador de Windows

Necesita Windows con [Inno Setup](https://jrsoftware.org/isinfo.php) y el
`hamrlog.exe` ya construido en `dist\`:

```powershell
iscc /DHamrlogVersion=0.2.0 packaging\windows\hamrlog.iss
```

Instala por usuario, así que no pide permisos de administrador.

### Paquete de Arch

```bash
cd packaging/arch
makepkg -si
```

Depende de `python-textual` y `python-sqlalchemy`, ambos en los repositorios
oficiales, así que no arrastra nada del AUR.

## Por qué el .exe se construye en GitHub

PyInstaller no compila para otra plataforma: un ejecutable de Windows solo se
genera desde Windows. Por eso `release.yml` usa una matriz con un runner de
cada sistema en lugar de construirlo todo en Linux.
