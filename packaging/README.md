# Empaquetado

Cómo se construyen y publican las versiones de hamrlog.

## Qué produce cada versión

Al empujar una etiqueta `v*`, el flujo `.github/workflows/release.yml` genera:

| Fichero | Para |
|---|---|
| `hamrlog-linux-x86_64` | Ejecutable de Linux, sin necesidad de Python |
| `hamrlog-windows-x86_64.exe` | Ejecutable de Windows, sin necesidad de Python |
| `hamrlog-X.Y.Z-setup.exe` | Instalador gráfico de Windows: instala, actualiza y desinstala |
| `hamrlog-X.Y.Z-linux-x86_64.tar.gz` | Ejecutable de Linux con su instalador (`install.sh`) |
| `hamrlog-install.sh` | El mismo instalador suelto, para `curl … \| bash` |
| `hamrlog-X.Y.Z-py3-none-any.whl` | Paquete de Python, para `pipx install` |
| `hamrlog-X.Y.Z.tar.gz` | Código fuente empaquetado |
| `SHA256SUMS.txt` | Sumas de comprobación de todo lo anterior |

Antes de publicar nada, el flujo ejecuta las pruebas y comprueba que cada
ejecutable arranca de verdad. En Windows instala además una versión 0.0.1
compilada para la ocasión, la actualiza a la nueva, comprueba que un downgrade
silencioso se rechaza y desinstala; en Linux instala y desinstala el tarball.

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

Necesita Windows con [Inno Setup](https://jrsoftware.org/isinfo.php) 6.7 (la
release instala la 6.7.3) y el `hamrlog.exe` ya construido en `dist\`:

```powershell
iscc /DHamrlogVersion=0.2.0 packaging\windows\hamrlog.iss
```

Instala por usuario, así que no pide permisos de administrador; el asistente
permite elegir una instalación para todos los usuarios.

- **Actualización**: el `AppId` del script identifica la instalación; no se
  debe cambiar nunca. Al ejecutar un instalador más nuevo encima, se salta la
  licencia, reutiliza carpeta y opciones, cierra hamrlog si está abierto y
  reconstruye la base de datos de la demo. Misma versión: ofrece reparar.
  Versión anterior: pregunta, y en modo silencioso la rechaza (código de
  salida 1).
- **Desinstalación**: quita la carpeta del PATH sin tocar las demás entradas,
  borra la plantilla de la demo y pregunta si borrar `%APPDATA%\hamrlog`. En
  modo silencioso conserva los datos.
- Los textos del asistente están en español e inglés según el idioma de
  Windows (`[CustomMessages]`).
- El fichero va en UTF-8 con BOM para que Inno Setup lea bien los acentos.

Instalación desatendida:

```powershell
hamrlog-X.Y.Z-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /TASKS=addtopath
"%LOCALAPPDATA%\Programs\hamrlog\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES
```

Se puede compilar y probar en Linux con Wine instalando Inno Setup en un
prefijo aparte y usando cualquier `.exe` como `dist\hamrlog.exe`.

### Instalador de Linux

`packaging/linux/install.sh` instala el ejecutable autocontenido, sin Python.
Si hay un `hamrlog` a su lado (el tarball de la release) instala ese; si no,
descarga la versión de GitHub y la comprueba con `SHA256SUMS.txt`. Lo que
instala queda apuntado en `<prefijo>/lib/hamrlog/` (versión y lista de
ficheros), y eso es lo que borra al desinstalar.

`--upgrade` descarga primero solo `SHA256SUMS.txt`, saca de ahí la versión
del tarball `hamrlog-X.Y.Z-linux-x86_64.tar.gz` y no baja nada más si ya es
la instalada. `HAMRLOG_RELEASES_URL` cambia el origen de las descargas: las
pruebas (`tests/test_linux_installer.py`) lo apuntan a una carpeta local con
`file://`.

No es el `install.sh` de la raíz del repositorio, que instala desde el código
con Python.

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
