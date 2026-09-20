# hamrlog

[![CI](https://github.com/manuel-alcocer/hamrlog/actions/workflows/ci.yml/badge.svg)](https://github.com/manuel-alcocer/hamrlog/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

Diario de contactos para radioaficionados, en modo texto. La misma aplicación
funciona en una consola de Linux y en PowerShell o Windows Terminal, sin
cambios ni configuración específica de cada sistema.

Está pensada para lo que ocurre de verdad durante una sesión de radio:
configuras la banda, la frecuencia, el modo y el equipo una sola vez, y a
partir de ahí solo escribes el indicativo y pulsas Enter.

```
 F1 Registro  F2 Banda  F3 Frec  F4 Modo  F5 Config  F6 Equipo  F7 Perfiles  F8 Contactos  F9 Rptr  F10 Menú
 OP EA7WM · BANDA 40m · QRG 7.130.000 · MODO SSB · EQUIPO IC-7300 / Dipolo G5RV · PERFIL HF-Casa
 FECHA HORA           INDICATIVO    NOMBRE      BANDA   FRECUENCIA   MODO     E/R       PAÍS        NOTAS
 2026-09-20 18:42:10  EA4ABC        Juan        40m     7.130.000    SSB      59/57     España      Madrid
 2026-09-20 18:45:02  DL2JKL        Hans        40m     7.130.000    SSB      59/59     Alemania
 2026-09-20 18:51:33  F5GHI         Pierre      40m     7.130.000    SSB      57/55     Francia     Toulouse
 ▸ <Insertar nuevo>
────────────────────────────────────────────────────────────────────────────────────────────────────────────
 IND  ea7wm        NOMBRE  Victor        ENV  59   REC  57   QTH  Sevilla      NOTAS
   Tab campo siguiente · Mayús+Tab anterior · Enter registra · ↑↓ histórico
  2026-09-20 18:52:41 UTC   QSO 128   hoy 17   únicos 96   países 23   40m:71      Ctrl+F1 Ayuda
```

## Instalación

### Windows

Descarga **`hamrlog-X.Y.Z-setup.exe`** de la [última
versión](https://github.com/manuel-alcocer/hamrlog/releases/latest) y
ejecútalo. No hace falta tener Python: el programa va dentro. El instalador
añade `hamrlog` al menú Inicio y, si lo marcas, al PATH para poder llamarlo
desde cualquier consola.

Si prefieres no instalar nada, descarga `hamrlog-windows-x86_64.exe` y
ejecútalo tal cual.

Se recomienda **Windows Terminal** en lugar de la consola clásica: los colores
y los caracteres de dibujo se ven correctamente. La aplicación cambia la
consola a UTF-8 por su cuenta, así que los acentos funcionan también en la
consola antigua.

### Linux

**Ejecutable suelto**, sin necesidad de Python:

```bash
curl -LO https://github.com/manuel-alcocer/hamrlog/releases/latest/download/hamrlog-linux-x86_64
chmod +x hamrlog-linux-x86_64
./hamrlog-linux-x86_64
```

**Con Python 3.10 o superior**, en un entorno aislado y con el comando en el
PATH:

```bash
git clone https://github.com/manuel-alcocer/hamrlog
cd hamrlog
./install.sh
```

El script usa `uv` o `pipx` si los tienes y, si no, crea un entorno virtual.
Para quitarlo: `./install.sh --uninstall`.

**Arch Linux**:

```bash
cd packaging/arch
makepkg -si
```

**Con pipx**, directamente desde el repositorio:

```bash
pipx install git+https://github.com/manuel-alcocer/hamrlog
```

### Desde el código

```bash
git clone https://github.com/manuel-alcocer/hamrlog
cd hamrlog
python3 -m venv .venv
source .venv/bin/activate     # en Windows: .venv\Scripts\Activate.ps1
pip install -e .
hamrlog
```

### Extras opcionales

```bash
pip install -e ".[metrics]"   # exportador Prometheus
pip install -e ".[api]"       # API REST
pip install -e ".[dev]"       # pruebas y linter
```

Los ejecutables de las releases no incluyen los extras: son para usar la
aplicación de terminal. Si quieres las métricas o la API, instala con pip.

## Uso

### La pantalla principal

El recuadro **Registro** tiene dos mitades: arriba la lista de QSO, abajo el
**detalle** de lo que esté señalado, con todo lo que no cabe en una fila
—locator, equipo, operador, parámetros del modo digital, el comentario entero y
las dos frecuencias cuando sales por un repetidor—.

Sobre `<Insertar nuevo>` ese mismo espacio muestra lo que heredará el próximo
QSO: operador, banda, frecuencia, repetidor, modo, equipo e informe por
defecto. Así ves con qué se va a registrar antes de pulsar Enter.

El teclado **no se mueve de la línea de entrada**. No hay Tab ni paneles que
alternar: escribes, y las flechas recorren lo que ya está registrado.

La línea de abajo tiene **dos estados**, según dónde esté el cursor:

**Sobre `<Insertar nuevo>`** es el formulario de casillas descrito arriba.

**Sobre un QSO ya registrado** deja de aceptar texto y ofrece sus acciones:

```
 D suprimir · E editar · R repetir · ↓ volver a escribir
```

| Tecla | Efecto |
|---|---|
| `D` | Borra ese QSO, con confirmación |
| `E` | Lo abre para editarlo |
| `R` | **Repetir**: lo devuelve a la línea, editable, para registrarlo otra vez |
| `↓` o `Esc` | Vuelve a `<Insertar nuevo>` |

Repetir se guarda con la banda y el modo actuales, no con los de entonces:
repetir es volver a trabajar a esa estación, no rearchivar el contacto viejo.

Las letras **no escriben** mientras navegas. `D`, `E` y `R` son letras
corrientes en un indicativo, y una tecla que a veces escribe y a veces borra
sería una trampa. Lo que tuvieras a medio escribir se guarda al subir y vuelve
intacto al bajar.

| Tecla | Siempre |
|---|---|
| `↑` `↓` | Recorren el histórico (`Re Pág` / `Av Pág`, de diez en diez) |
| `Enter` con algo escrito | Guarda un QSO nuevo, estés donde estés en la lista |
| `Ctrl+D` | Borra el QSO señalado, o el último si estás escribiendo |
| `Ctrl+↑` `Ctrl+↓` | Recuperan líneas escritas antes |

La última fila del histórico es siempre **`<Insertar nuevo>`**: marca dónde
aparecerá el próximo QSO, y el cursor vuelve ahí solo después de guardar.

La dirección se elige en **F5 → Histórico**: los nuevos abajo (la lista crece
hacia abajo) o los nuevos arriba. `<Insertar nuevo>` acompaña siempre al
extremo por el que crece.

### Las confirmaciones

Todo borrado pregunta antes, y se responde de tres formas: `←` `→` o `Tab`
mueven entre los botones y `Enter` confirma el señalado, `S` dice que sí, y `N`
o `Esc` dicen que no. Arranca con **No** seleccionado, para que un Enter por
inercia no se lleve nada por delante.

### El menú superior

`F10` activa la barra de arriba: `←` `→` la recorren, `Enter` abre lo señalado
y `Esc` vuelve a la escritura, como en Midnight Commander. Es la salida si tu
terminal se queda con alguna tecla de función.

### La línea de entrada

Todo el trabajo durante una sesión ocurre en la línea inferior, donde cada
campo tiene su propia casilla:

```
 IND  ea7wm        NOMBRE  Victor        ENV  59   REC  57   QTH  Sevilla      NOTAS
```

| Tecla | Efecto |
|---|---|
| `Tab` | Pasa a la casilla siguiente |
| `Mayús+Tab` | Vuelve a la anterior |
| `Enter` | Registra el QSO desde cualquier casilla |

La fecha y la hora UTC se ponen solas. Solo el indicativo es obligatorio: con
escribirlo y pulsar Enter ya queda registrado, con el informe por defecto del
modo activo (59 en fonía, 599 en CW, -10 en FT8).

Las casillas y su orden se configuran en **F5 → Entrada rápida**; por defecto
son `indicativo, nombre, rst_env, rst_rec, qth, notas`. Las comas no separan
nada: son texto corriente, así que una nota puede llevarlas.

Mientras escribes el indicativo, si ya está en el log aparece un aviso de
duplicado con la fecha del último contacto, y si está en la agenda se te dice
quién es.

### Teclas

| Tecla | Acción |
|---|---|
| `F1` | **Registro**: los QSO que llevas hechos |
| `F2` | Selector de banda (160 m a 3 cm, plan IARU R1) |
| `F3` | Frecuencia, con detección automática de banda |
| `F4` | Modo: SSB, CW, FM, AM, DMR, D-STAR, C4FM, M17, FT8, RTTY... todos en una lista |
| `F5` | Configuración, incluidas la importación y la exportación del registro |
| `F6` | Equipo: emisora, antena y potencia |
| `F7` | Perfiles: guardar y recuperar configuraciones completas |
| `F8` | **Contactos**: la agenda de quién es cada indicativo |
| `F9` | Repetidor: por dónde sales, y alta de repetidores |
| `F10` | Menú: recorre la barra superior con `←` `→`, como Midnight Commander |
| `Ctrl+F1` | Ayuda (también `F12`, y `/ayuda`) |
| `Ctrl+Q` | Salir |

**Registro** (`F1`) y **Contactos** (`F8`) son cosas distintas y deliberadamente
separadas: el registro es *qué* has trabajado y cuándo, los contactos son
*quién* es cada cual. Desde cualquiera de las dos pantallas, la tecla de la
otra te lleva allí sin apilar ventanas.

Si tu emulador de terminal se queda con alguna tecla de función (`F10` abre el
menú en varios terminales de Linux), cada atajo tiene su comando equivalente.

### Comandos

Escritos en la propia línea de entrada:

| Comando | Efecto |
|---|---|
| `/banda 20m` | Cambia de banda al instante |
| `/frec 14.250` | Fija la frecuencia |
| `/modo cw` o `/modo dmr` | Cambia de modo, analógico o digital |
| `/equipo` | Abre el selector de equipo |
| `/perfil HF-Casa` | Carga un perfil por su nombre |
| `/repetidor ED7ZAE` | Sale por ese repetidor sin abrir la lista |
| `/directo` | Vuelve a simplex |
| `/registro`, `/log` | El registro de QSO |
| `/contactos`, `/agenda` | La agenda |
| `/exportar`, `/importar` | Importar y exportar el registro |
| `/config`, `/ayuda` | Configuración y ayuda |
| `/borrar` o `/deshacer` | Borra el último contacto registrado |
| `/salir` | Cierra la aplicación |

### Modos

`F4` lista todos los modos juntos, analógicos y digitales, porque son lo mismo:
cómo estás trabajando. Escribe para filtrar (`dmr`, `digital`, `datos`, `cw`).

Al elegir uno digital se piden los datos que ese modo necesita, y se aplican a
todos los QSO hasta que los cambies:

| Modo | Datos que pide |
|---|---|
| DMR | Talkgroup, red (Brandmeister, TGIF, DMR+), color code, repetidor |
| D-STAR | Reflector, gateway |
| C4FM | Room de Wires-X, DG-ID, repetidor |
| M17 | Reflector, módulo |
| FT8, FT4, JS8, RTTY... | Ninguno |

En ADIF se exportan con su equivalencia correcta: DMR, D-STAR y C4FM son
`MODE=DIGITALVOICE` con el `SUBMODE` correspondiente, y los datos sin campo
estándar viajan como `APP_HAMRLOG_TALKGROUP`, `APP_HAMRLOG_NETWORK`, etc.

### Los contactos (agenda)

`F8` es la agenda: nombre, apellidos, ID DMR, ciudad, provincia, país, locator,
correo y notas, más cuántos QSO llevas con cada estación.

**Se llena sola con lo que trabajas**: al registrar un indicativo que no esté
en ella, se da de alta con el nombre, el QTH y el país del propio QSO. Los que
ya están no se tocan —lo que hayas escrito ahí vale más que lo que traiga un
contacto suelto— y las portables (`F/EA4ABC/P`) se archivan bajo el indicativo
de casa, así que no se duplican.

De vuelta, al teclear un indicativo conocido aparece quién es bajo la línea de
entrada, y al pulsar Enter el nombre y el QTH que no hayas escrito se rellenan
solos. **Lo que tú escribas siempre manda** sobre lo que diga el listín.

Ambas cosas se desactivan en **F5 → Histórico y agenda**. Importar un ADIF no
da de alta contactos: solo lo hace lo que registras en directo, para que un
fichero de miles de QSO no se convierta en miles de fichas a medias.

#### Importar listas de usuarios DMR

`Ctrl+I` desde `F8`, o `hamrlog contacts import`. El formato se detecta
solo, así que no hay que convertir nada:

| Origen | Qué se reconoce |
|---|---|
| RadioID.net | `RADIO_ID,CALLSIGN,FIRST_NAME,LAST_NAME,CITY,STATE,COUNTRY,REMARKS`, con o sin cabecera |
| BrandMeister | Sus CSV, incluidos los de nombre en una columna y separador `;` |
| CPS de la radio | El CSV de contactos de Anytone D878UV y compatibles |
| APIs | El JSON de RadioID y de BrandMeister |
| hamrlog | Su propia exportación |

Se detecta el separador (`,`, `;`, tabulador), se tolera texto no UTF-8 y se
reconstruye el nombre cuando viene en una sola columna. Un fichero que no sea
una lista de contactos se rechaza en vez de llenarte la agenda de basura.

Al importar puedes filtrar por país, para quedarte solo con el 214 partiendo de
una lista mundial:

```bash
hamrlog contacts import ~/Descargas/user.csv --country Spain
```

Reimportar **no duplica**: reconoce al mismo operador por ID DMR o por
indicativo, rellena lo que falte y nunca pisa un dato escrito a mano.

#### Exportar a la radio

`Ctrl+O` desde `F8`, o por línea de órdenes:

```bash
hamrlog contacts export contactos.csv --format anytone
```

| Formato | Para qué |
|---|---|
| `anytone` | El CSV que espera el CPS de la D878UV, con sus columnas `No.`, `Call Type` y `Call Alert` |
| `radioid` | El formato estándar de RadioID.net |
| `hamrlog` | El propio, con cabeceras en español |

En el formato de la radio se omiten los contactos sin ID DMR: el equipo no
puede usarlos.

### Repetidores

`F9` decide por dónde sale tu señal: directo (simplex) o por un repetidor dado
de alta. Al elegir uno se adopta todo lo que define —frecuencia de escucha y de
transmisión, banda, modo y sus parámetros digitales— y puedes volver a registrar
contactos de inmediato.

Para dar uno de alta, `F9` y luego `N`. Lo único imprescindible es el indicativo
y la frecuencia de salida, la que sintonizas:

| Campo | Ejemplo | Notas |
|---|---|---|
| Indicativo | `ED7ZAE` | |
| Nombre / ubicación | `Sevilla - Cerro del Águila` | |
| Frecuencia de salida | `145.600` | La que pones en la radio |
| Desplazamiento | `-600 kHz` | Vacío = el habitual de la banda |
| Modo | `FM`, `C4FM`, `DMR`, `DSTAR` | |
| Subtono CTCSS | `88.5` | Se valida contra los tonos estándar |
| DCS, QTH, locator, notas | | Opcionales |

Si el modo es digital se piden después sus parámetros: color code y talkgroup en
DMR, reflector en D-STAR, room de Wires-X en C4FM.

Cambiar de banda o de frecuencia a mano (`F2`, `F3`) te saca del repetidor,
porque dejan de describir dónde trabajas. Se vuelve a simplex con `D` en la
lista o con `/directo`.

Un contacto por repetidor es un QSO en split, y así se exporta: `FREQ` lleva la
frecuencia de entrada (lo que transmites), `FREQ_RX` la de salida (lo que
escuchas) y `PROP_MODE` vale `RPT`, tal como define ADIF. El indicativo del
repetidor viaja en `APP_HAMRLOG_REPEATER` y se conserva al reimportar.

### Perfiles

Un perfil guarda la configuración completa: operador, equipo, repetidor, banda,
frecuencia, modo, datos del modo digital y el formato de la línea de entrada.
En `F7`, la tecla `G` guarda la configuración actual como un perfil nuevo, `S`
sobrescribe el seleccionado y `D` lo marca como predeterminado para que se
cargue solo al arrancar.

### Borrar QSO del registro

* **`Ctrl+D` desde la línea de entrada** borra el último contacto registrado,
  que es el caso habitual: acabas de guardar un indicativo mal escrito.
* **`Tab` al histórico, `↑↓` y `Supr`** borra el contacto seleccionado.
* **`F1`** abre el registro completo, donde puedes buscar primero y borrar
  con `Supr` o `Ctrl+D`.

Siempre se pide confirmación, indicando indicativo, fecha, banda y modo.

### Indicativos mal escritos

Al teclear, el indicativo se contrasta con la forma que tiene uno real
(prefijo, dígito y sufijo). Si no encaja se avisa mientras escribes y al pulsar
Enter **no se guarda**, diciendo qué falla: le falta el número, es demasiado
corto, lleva caracteres que un indicativo no tiene…

Pasan sin problema los indicativos especiales y los portables (`AM500ITU`,
`9A1AA`, `3DA0RS`, `F/EA7WM/P`). Para forzar uno inusual que el filtro no
admita, termínalo en `!`:

```
bv100!,chen
```

Se cambia en **F10 → Entrada rápida → Validar indicativos**: `estricta` (por
defecto), `avisar` o `no`.

### Contactos automáticos y manuales

Esta distinción es deliberada:

* **AUTO** — la fecha y la hora las puso el programa al pulsar Enter. Es la
  prueba de cuándo ocurrió el contacto, así que **solo se puede corregir el
  indicativo**: lo único que se corrige de verdad después es haber escuchado
  mal una letra.
* **MANUAL** — contactos añadidos con fecha a mano (`F1` → `Ctrl+N`) o
  importados desde un ADIF. No los cronometró esta aplicación, así que
  **todos sus campos son editables**.

### Multiusuario

Varios operadores comparten la misma base de datos y cada contacto queda
asociado a quien lo registró. No hay contraseñas: se cambia de operador en
`F10 → Operador activo`. Las estadísticas y las exportaciones pueden filtrarse
por operador.

## Desde la línea de órdenes

```bash
hamrlog                                      # abre la interfaz
hamrlog info                                 # rutas, base de datos y versión
hamrlog export log.adi                       # exporta todo el log a ADIF
hamrlog export --format csv log.csv          # exporta a CSV
hamrlog import otro.adi --operator EA7WM     # importa un ADIF
hamrlog metrics --port 9119                  # solo el exportador Prometheus

hamrlog contacts import user.csv             # importa una lista de usuarios DMR
hamrlog contacts import user.csv --country Spain
hamrlog contacts export c.csv --format anytone   # contactos para el CPS de la radio
hamrlog contacts list ea7                    # busca en la agenda
```

## Dónde se guardan los datos

Una base de datos SQLite, en la carpeta estándar de cada sistema:

| Sistema | Ruta |
|---|---|
| Linux | `~/.local/share/hamrlog/hamrlog.sqlite3` |
| Windows | `%APPDATA%\hamrlog\hamrlog.sqlite3` |
| macOS | `~/Library/Application Support/hamrlog/` |

Dos variables de entorno lo cambian todo:

```bash
export HAMRLOG_HOME=/ruta/a/mis/datos
export HAMRLOG_DATABASE_URL=postgresql+psycopg://usuario:clave@servidor/hamrlog
```

La segunda permite usar PostgreSQL sin tocar una línea de código, que es lo
que necesitarías para compartir el log entre varios equipos.

## Integraciones

### Prometheus

Se activa en `F10 → Métricas Prometheus` o con `hamrlog metrics`. Expone en
`/metrics`:

```
hamrlog_qso_total, hamrlog_qso_today, hamrlog_unique_callsigns_total,
hamrlog_countries_total, hamrlog_qso_by_band{band}, hamrlog_qso_by_mode{mode}
```

Las métricas se calculan en cada consulta, así que siguen siendo correctas tras
reiniciar o editar contactos desde fuera.

### API REST

```bash
pip install -e ".[api]"
uvicorn hamrlog.api.server:app
```

Expone `/health`, `/operators`, `/qsos`, `/qsos/{id}` y `/stats`. Es de solo
lectura a propósito: abrir la escritura exige decidir una autenticación, y esa
decisión corresponde a quien la despliegue.

### Aplicación web futura

La lógica vive entera en `hamrlog/core/services.py`, sin ninguna dependencia de
la interfaz. Una web o una aplicación móvil se construirían sobre esos mismos
servicios. Consulta [docs/arquitectura.md](docs/arquitectura.md).

## Desarrollo

```bash
pip install -e ".[dev,metrics,api]"
pytest                  # 235 pruebas, incluidas las de la interfaz
ruff check src tests
```

Las pruebas de interfaz usan el piloto de Textual: escriben en la línea de
entrada, pulsan teclas de función y comprueban el resultado, sin necesidad de
un terminal real.

Los comentarios y los identificadores del código están en inglés; los textos
que ve el usuario, en español.

## Publicar una versión

Las releases se construyen solas: etiquetar y empujar compila el ejecutable de
Linux, el de Windows y el instalador, comprueba que las pruebas pasan y que
cada binario arranca, y lo publica todo con sus sumas SHA-256.

```bash
# Sube la versión en pyproject.toml y en packaging/arch/PKGBUILD
git tag -a v0.2.0 -m "v0.2.0"
git push origin v0.2.0
```

Los detalles están en [packaging/README.md](packaging/README.md).

## Licencia

MIT. Ver [LICENSE](LICENSE).
