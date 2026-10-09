## Instalación

**Windows**: descarga `hamrlog-*-setup.exe` y ejecútalo. No hace
falta tener Python. Para actualizar, ejecuta el instalador de la
versión nueva: conserva la carpeta, las opciones y tu diario. Se
desinstala desde «Agregar o quitar programas». Si prefieres el
ejecutable suelto, usa `hamrlog-windows-x86_64.exe`.

**Linux**: instala, o actualiza a la última versión, con

```bash
curl -fsSL https://github.com/manuel-alcocer/hamrlog/releases/latest/download/hamrlog-install.sh | bash
```

o descarga `hamrlog-*-linux-x86_64.tar.gz`, descomprímelo y
ejecuta `./install.sh`. Después: `install.sh --upgrade` para
actualizar y `install.sh --uninstall` para quitarlo. El ejecutable
suelto es `hamrlog-linux-x86_64`.

**Con Python ya instalado**: `pipx install hamrlog` desde el
`.whl`, o el `install.sh` de la raíz del repositorio.

**Arch Linux**: `packaging/arch/PKGBUILD`.

Comprueba las descargas con `SHA256SUMS.txt`.
