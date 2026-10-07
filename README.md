# hamrlog

[![CI](https://github.com/manuel-alcocer/hamrlog/actions/workflows/ci.yml/badge.svg)](https://github.com/manuel-alcocer/hamrlog/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

Diario de contactos para radioaficionados, en modo texto. La misma aplicación
funciona en una consola de Linux y en PowerShell o Windows Terminal, sin
cambios ni configuración específica de cada sistema.

Está pensada para lo que ocurre de verdad durante una sesión de radio:
configuras la banda, la frecuencia, el modo y el equipo una sola vez, y a
partir de ahí solo escribes el indicativo y pulsas Enter. Todo ocurre en una
única pantalla: no hay menús ni ventanas que abrir.

```
 OP EA7WM · BANDA 40m · QRG 7.130.000 · MODO SSB · EQUIPO IC-7300 / Dipolo G5RV · PERFIL HF-Casa
 FECHA HORA           INDICATIVO    NOMBRE      BANDA   FRECUENCIA   MODO     E/R       PAÍS        NOTAS
 2026-09-20 18:42:10  EA4ABC        Juan        40m     7.130.000    SSB      59/57     España      Madrid
 2026-09-20 18:45:02  DL2JKL        Hans        40m     7.130.000    SSB      59/59     Alemania
 2026-09-20 18:51:33  F5GHI         Pierre      40m     7.130.000    SSB      57/55     Francia     Toulouse
 ▸ <Insertar nuevo>
────────────────────────────────────────────────────────────────────────────────────────────────────────────
 IND  ea7wm        NOMBRE  Victor        ENV  59   REC  57   QTH  Sevilla      NOTAS
   Tab campo siguiente · Mayús+Tab anterior · Enter registra · ↑↓ histórico
  2026-09-20 18:52:41 UTC   QSO 128   hoy 17   únicos 96   países 23   40m:71       Ctrl+Q Salir
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
 D suprimir · E editar · R repetir · Espacio marca · Ctrl+A todos · ↓ volver a escribir
```

| Tecla | Efecto |
|---|---|
| `D` | Borra ese QSO, con confirmación |
| `E` | **Editar**: lo corrige ahí mismo, en la línea de entrada |
| `Espacio` | Marca o desmarca el QSO (sale `S` en la columna INFO) |
| `Ctrl+A` | Marca todos, o los desmarca si ya lo estaban |
| `R` | **Repetir**: lo devuelve a la línea, editable, para registrarlo otra vez |
| `↓` o `Esc` | Vuelve a `<Insertar nuevo>` |

Editar no abre ninguna ventana: la línea de entrada se rellena con ese QSO y
añade una segunda fila con frecuencia, modo y **equipo**. Cambias lo que haga
falta, `Enter` guarda y `Esc` cancela. Se puede corregir todo **menos la fecha
y la hora**. La banda no se escribe: la calcula la aplicación a partir de la
frecuencia.

Con **más de un QSO marcado**, `E` los edita todos a la vez, pero solo en
frecuencia, modo y equipo. Cada casilla empieza con el valor que comparten, o
vacía si difieren; una casilla vacía deja cada QSO como estaba.

La lista muestra el equipo de cada QSO; los informes (RST) están en el detalle
de abajo al recorrerla.

En la casilla EQUIPO se escribe el nombre de uno de tus equipos del
Inventario (`→` completa). El QSO toma de él la emisora y la antena que cubren
su frecuencia, que son las que salen en ADIF como `MY_RIG` y `MY_ANTENNA`. Si
ninguna de sus emisoras sintoniza esa frecuencia, o ninguna de sus antenas
trabaja esa banda, se guarda igual, pero su columna INFO muestra `E` y el
detalle explica por qué.

La lista del registro muestra INFO, fecha y hora, indicativo, nombre,
frecuencia, modo, equipo, país y QTH. INFO lleva una letra por cada cosa que
señalar: `S` si el QSO está seleccionado, `E` si tiene un error, `d` (*drift*)
si el nombre del QSO no coincide con el de la ficha de la agenda (un QSO
seleccionado y con error dice `SE`); vacía si no hay nada. El nombre coincide
si es el nombre o el nombre completo de la ficha, sin mirar mayúsculas; el
detalle dice cuál tiene la agenda, y la ficha no se cambia. La fecha va sin
segundos: `DD/MM/AA HH:MM` en español y `AA/MM/DD HH:MM` en inglés.

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

### Las confirmaciones

Todo borrado pregunta antes, y se responde de tres formas: `←` `→` o `Tab`
mueven entre los botones y `Enter` confirma el señalado, `S` dice que sí, y `N`
o `Esc` dicen que no. Arranca con **No** seleccionado, para que un Enter por
inercia no se lleve nada por delante.

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

Las casillas son `indicativo, nombre, rst_env, rst_rec, qth, notas`, salvo que
el perfil cargado traiga otras. Las comas no separan
nada: son texto corriente, así que una nota puede llevarlas.

Mientras escribes el indicativo, si ya está en el log aparece un aviso de
duplicado con la fecha del último contacto, y si está en la agenda se te dice
quién es.

### Teclas

| Tecla | Acción |
|---|---|
| `Tab` / `Mayús+Tab` | Casilla siguiente / anterior |
| `Enter` | Registra el QSO |
| `↑` `↓` | Recorren el histórico |
| `Ctrl+D` | Borra el QSO señalado, o el último |
| `Esc` | Vuelve a `<Insertar nuevo>` |
| `F1` | **Registro** |
| `F2` | **Inventario** |
| `F3` | **Agenda** de contactos |
| `F4` | **Perfiles** |
| `F5` | **Repetidores** |
| `Ctrl+N` | Pestaña siguiente, en las secciones que tienen pestañas |
| `Ctrl+0` … `Ctrl+9` | Activan el perfil con esa tecla, desde cualquier ventana |
| `RePág` `AvPág` | Recorren el histórico página a página |
| `Ctrl+Q` | Salir |

Las teclas `F1` a `F5` llevan a su sección desde cualquier otra.

Lo que hereda cada QSO se cambia con comandos.

### Inventario (`F2`)

`F2` convierte el recuadro del registro en el **Inventario**, con cuatro pestañas, y
funciona igual que el registro: la lista arriba, la línea de entrada abajo
para escribir, `↑` `↓` para recorrerla y `<Nuevo …>` al final.

| Pestaña | Qué se da de alta | Casillas |
|---|---|---|
| **Equipos** | Un conjunto: al menos una emisora, con sus antenas y fuentes | nombre, emisoras, antenas, fuentes, notas |
| **Emisoras** | Cada emisora suelta | marca, modelo, nombre, potencia, tipos (HF, VHF, UHF, CB), notas |
| **Antenas** | Cada antena suelta | marca, nombre, bandas, notas |
| **Fuentes** | Fuentes de alimentación y baterías | marca, nombre, tensión, corriente, notas |

Cada emisora, antena y fuente recibe al darse de alta un **ID propio**,
automático y único: `E0001` para las emisoras, `A0001` para las antenas y
`S0001` para las fuentes. Es la primera columna de la lista y no se escribe ni
se cambia.

En **Equipos**, las casillas de emisoras, antenas y fuentes llevan sus ID o sus
nombres, separados por comas (`E0001, E0003`), y `→` al final de la casilla
completa lo sugerido. Una emisora sin nombre se llama «marca modelo».

| Tecla | En el Inventario |
|---|---|
| `Ctrl+N` | Pestaña siguiente, en ciclo; `Mayús+RePág` `Mayús+AvPág` van atrás y adelante |
| `RePág` `AvPág` | Recorren la lista página a página |
| `Alt+↑` `Alt+↓` | Recorre las marcas de la pestaña (filtro) |
| `D` `E` sobre un elemento | Suprimir / editar en la línea de entrada |
| `F1` | Vuelve al registro |

Las teclas de función cambian de significado en cada ventana; las que una
ventana no usa no hacen nada. `F1` es siempre el registro.

`/marca yaesu` filtra la lista por marca (vale el principio del nombre) y
`/marca` sola quita el filtro.

**Catálogo.** Al abrir, la aplicación carga todos los ficheros de
`hamrlog/data/preseed/`: emisoras, antenas y fuentes a la venta en tiendas
españolas. Se cargan una sola vez —abrir de nuevo no duplica nada— y lo que
hayas dado de alta con el mismo nombre se respeta. Los elementos del catálogo
salen atenuados: **no se modifican ni se borran**, solo se usan al montar un
equipo. Para añadir un catálogo basta con dejar otro `.json` en esa carpeta,
con la forma `{"tipo": "emisoras" | "antenas" | "fuentes" | "repetidores",
"elementos": [...]}`.

### Agenda (`F3`)

`F3` muestra la agenda en el recuadro del registro, igual que el Inventario:
la lista arriba, `<Nuevo contacto>` al final, `D` y `E` sobre una ficha, y la
línea de entrada para escribir. Como una ficha tiene muchos datos, la línea
de entrada tiene aquí dos filas:

```
 IND  EA4ABC       NOMBRE  Juan          APELLIDOS  Pérez García    ID DMR  2141234  LOC  IN80
 CIUDAD  Madrid        PROVINCIA  Madrid        PAÍS  España        CORREO                NOTAS
```

El país se escribe en tu idioma y se guarda en inglés, como en el registro.
El detalle de cada ficha dice cuántos QSO tienes con esa estación.

Una lista de usuarios DMR puede traer decenas de miles de fichas, así que la
agenda enseña como mucho 500 a la vez: `/buscar texto` busca en indicativo,
nombre, ciudad, provincia, país o ID DMR, y `/buscar` solo vuelve a todas.
La cabecera dice cuántas hay y cuántas se ven. `RePág` y `AvPág` pasan
página.

### Perfiles (`F4`)

Un **perfil** es lo que hereda cada QSO mientras está activo: operador, equipo
(de los del Inventario), frecuencia —la banda sale de ella—, modo, potencia,
repetidor y datos del modo digital. Con un perfil activo basta con escribir el
indicativo en el registro y pulsar Enter: el QSO se guarda con todo eso, y con
la emisora y la antena del equipo que cubran su frecuencia.

`F4` muestra la lista en el recuadro del registro, igual que el Inventario y
la Agenda, con `<Nuevo perfil>` al final y dos filas de casillas:

```
 CTRL  1    NOMBRE  40m casa      OPERADOR  EA7WM       EQUIPO  Casa
 FREC  7.100        MODO  SSB     POT  100   REPETIDOR             DIGITAL
```

| Casilla | Qué lleva |
|---|---|
| CTRL | `0` a `9`: el perfil es uno de los diez **principales** y `Ctrl+` esa cifra lo activa. Si otro tenía la cifra, la pierde |
| OPERADOR | Indicativo; si no existe se da de alta. Vacío, sigue el operador actual |
| EQUIPO | Un equipo del Inventario (`F2`) |
| REPETIDOR | Indicativo de un repetidor; sin frecuencia ni modo, se toman los suyos |
| DIGITAL | Valores del modo digital: `TG=214, CC=1`, `DG-ID=10, Room=12345`… |

| Tecla | En Perfiles |
|---|---|
| `Enter` sobre un perfil | Lo **activa** |
| `*` sobre un perfil | Lo hace **predeterminado**: se activa al arrancar. Otra vez `*` lo quita |
| `D` `E` sobre un perfil | Suprimir / editar en la línea de entrada |
| `Ctrl+0` … `Ctrl+9` | Activan los principales, también desde el registro |

En la lista, `▶` señala el perfil activo y `★` el predeterminado. El perfil
activo sale en la línea de estado; cambiar a mano la banda, la frecuencia, el
modo o el repetidor deja de usarlo (sus valores siguen), y editarlo aplica los
cambios a los QSO que vengan. `/perfil nombre` o `/perfil 3` también lo
activan, útil en terminales que no distinguen `Ctrl+` cifra.

### Repetidores (`F5`)

`F5` lista los repetidores en el recuadro del registro, como la Agenda: se
buscan con `/buscar` y la cabecera dice cuántos hay. Cada uno lleva su número
de la **URE** (`R5`, `R73`), indicativo, frecuencia de **salida** (la que
escuchas) y de **entrada** (la que transmites), **tono** CTCSS, modo, canal
IARU (`RV58`, `RU698`), locator y quién lo mantiene.

```
 IND  ED1YAB      SALIDA  145.725    ENTRADA  145.125   TONO  77.0   MODO  FM   URE  R5   CANAL  RV58
 TITULAR  Radio Club Rioja        QTH                     LOC  IN82PO   DIGITAL           NOTAS
```

| Casilla | Qué lleva |
|---|---|
| ENTRADA | La frecuencia de entrada, o el desplazamiento si empieza por signo (`-600`, `-7.6 MHz`). Vacía, el habitual de la banda |
| TONO | CTCSS en Hz; `88` se entiende como `88.5` |
| URE | El número que le da la URE: `R5`, `R73` |
| DIGITAL | Como en los perfiles: `CC=1, TG=214` |

`Enter` sobre un repetidor lo **sintoniza**, igual que `/repetidor`. `/buscar`
mira en indicativo, número URE, canal, titular, lugar, locator, banda y modo,
y cada palabra acota más: `/buscar R5`, `/buscar dmr madrid`, `/buscar IN80`.

**La lista de la URE.** Al abrir se cargan los repetidores publicados en
[ure.es/repetidores](https://www.ure.es/repetidores/) (10 m, 6 m, 2 m, 70 cm
y 23 cm), de `hamrlog/data/preseed/repetidores.json`. Como el catálogo del
Inventario, se cargan una sola vez, salen atenuados y **no se modifican ni se
borran**; los que tú añadas sí.

Un mismo indicativo puede ser varios repetidores (un radioclub con uno D-Star,
otro DMR y otro C4FM). Cuando pasa, se distinguen añadiendo la frecuencia de
salida, el modo o la banda: `/repetidor ED4ZAH DMR`, `/repetidor ED4ZAH
438.325`; en la casilla REPETIDOR de un perfil, igual.

### Idioma

La interfaz está en inglés y en español. Se elige sola según el idioma del
sistema (`LANG` en Linux, el idioma de la interfaz en Windows);
`HAMRLOG_LANG=en` o `HAMRLOG_LANG=es` la fuerza. Las
traducciones son ficheros `.po` en `hamrlog/locales/`.

### Comandos

Escritos en la primera casilla de la línea de entrada:

| Comando | Efecto |
|---|---|
| `/banda 20m` | Cambia de banda |
| `/frec 14.250` | Fija la frecuencia, con detección automática de banda |
| `/modo cw` o `/modo dmr` | Cambia de modo, analógico o digital |
| `/perfil 20m` o `/perfil 3` | Activa un perfil por su nombre o su tecla |
| `/repetidor ED7ZAE` | Sale por ese repetidor; `/repetidor ED4ZAH DMR` si el indicativo es de varios |
| `/directo` | Vuelve a simplex |
| `/borrar` o `/deshacer` | Borra el último contacto registrado |
| `/ayuda` | Lista los comandos |
| `/salir` | Cierra la aplicación |

Un comando escrito sin su valor (`/banda`) responde cómo se usa. Las
respuestas salen bajo la línea de entrada; nada tapa el registro salvo dos
diálogos: la confirmación de un borrado y los datos de un modo digital.

### Lo que por ahora no tiene interfaz

Las pantallas de gestión se han retirado para rediseñarlas. Los datos y la
lógica siguen en la base de datos y en `core/services.py`, pero desde la
aplicación **no se puede**, de momento: cambiar de operador ni tocar los ajustes (unidades, orden del
histórico, validación de indicativos, métricas). Importar y exportar sigue
disponible [desde la línea de órdenes](#desde-la-línea-de-órdenes).

### Modos

`/modo` acepta cualquiera, analógico o digital: SSB, CW, FM, AM, DMR, D-STAR,
C4FM, M17, FT8, RTTY...

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

La agenda guarda nombre, apellidos, ID DMR, ciudad, provincia, país, locator,
correo y notas de cada indicativo. Se consulta con `hamrlog contacts list`.

**Se llena sola con lo que trabajas**: al registrar un indicativo que no esté
en ella, se da de alta con el nombre, el QTH y el país del propio QSO. Los que
ya están no se tocan —lo que hayas escrito ahí vale más que lo que traiga un
contacto suelto—, salvo lo que le falte: si la ficha no tiene nombre toma el
que escribas al registrar, y si no tiene ciudad toma el QTH. Los QSO
anteriores con esa estación no se tocan. Las portables (`F/EA4ABC/P`) se archivan bajo el indicativo
de casa, así que no se duplican.

De vuelta, al teclear un indicativo conocido aparece quién es bajo la línea de
entrada, y al pulsar Enter el nombre y el QTH que no hayas escrito se rellenan
solos. **Lo que tú escribas siempre manda** sobre lo que diga el listín.

Importar un ADIF no
da de alta contactos: solo lo hace lo que registras en directo, para que un
fichero de miles de QSO no se convierta en miles de fichas a medias.

#### Importar listas de usuarios DMR

Con `hamrlog contacts import`. El formato se detecta
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

Por línea de órdenes:

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

`/repetidor ED7ZAE`, o `Enter` sobre él en [Repetidores](#repetidores-f5),
hace salir tu señal por un repetidor ya dado de alta. Se
adopta todo lo que define —frecuencia de escucha y de transmisión, banda, modo
y sus parámetros digitales— y puedes registrar contactos de inmediato.

Cambiar de banda o de frecuencia a mano (`/banda`, `/frec`) te saca del
repetidor, porque dejan de describir dónde trabajas. Se vuelve a simplex con
`/directo`.

Un contacto por repetidor es un QSO en split, y así se exporta: `FREQ` lleva la
frecuencia de entrada (lo que transmites), `FREQ_RX` la de salida (lo que
escuchas) y `PROP_MODE` vale `RPT`, tal como define ADIF. El indicativo del
repetidor viaja en `APP_HAMRLOG_REPEATER` y se conserva al reimportar.

### Emisora y antena de cada QSO

Cada QSO guarda la emisora y la antena en uso —las del equipo del perfil
activo que cubran su frecuencia—, que se exportan como `MY_RIG` y
`MY_ANTENNA`. Ver [Perfiles](#perfiles-f4).

### Borrar QSO del registro

* **`Ctrl+D` desde la línea de entrada** borra el último contacto registrado,
  que es el caso habitual: acabas de guardar un indicativo mal escrito.
* **`↑` `↓` y `D`** (o `Supr`) borra el contacto señalado en el histórico.

Siempre se pide confirmación, indicando indicativo, fecha, banda y modo.

### Frecuencias y unidades

Toda frecuencia lleva unidad. Los ajustes guardan la que se usa al mostrarlas
y la que se supone al escribir un número sin unidad (megahercios por defecto). Se
guardan con la grafía del Sistema Internacional (`MHz`, `kHz`, `Hz`), escribas
como escribas:

| Se escribe | Se guarda como |
|---|---|
| `M`, `m`, `mhz`, `MHZ`, `MHz` | `MHz` |
| `k`, `K`, `khz`, `KHZ` | `kHz` |
| `hz`, `HZ`, `hZ`, `Hz` | `Hz` |

La unidad escrita a mano manda sobre la configurada: con la preferencia en
`MHz`, `7130 k` sigue siendo kilohercios.

El **separador decimal** y el **de millar** también son ajustes. Nunca pueden
ser el mismo, y el de millar admite «ocultar»:

| Unidad | Decimal | Millar | 7.130.000 Hz se ve |
|---|---|---|---|
| MHz | `.` | ocultar | `7.130 MHz` |
| kHz | `.` | `,` | `7,130 kHz` |
| Hz | `,` | `.` | `7.130.000 Hz` |
| Hz | `.` | espacio | `7 130 000 Hz` |

Dos excepciones deliberadas: los **desplazamientos de repetidor** sin unidad
son siempre kilohercios, porque así se escriben en las radios; y la
**exportación ADIF** mantiene megahercios con punto, que es lo que fija la
norma para que el fichero lo lea cualquier otro programa.

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

La validación tiene tres niveles: `estricta` (por defecto), `avisar` o `no`.

### Contactos automáticos y manuales

Esta distinción es deliberada:

* **AUTO** — la fecha y la hora las puso el programa al pulsar Enter. Es la
  prueba de cuándo ocurrió el contacto, así que **se puede corregir todo
  menos la fecha y la hora**.
* **MANUAL** — contactos con fecha puesta a mano o
  importados desde un ADIF. No los cronometró esta aplicación, así que
  **todos sus campos son editables**, fecha incluida.

### Multiusuario

Varios operadores comparten la misma base de datos y cada contacto queda
asociado a quien lo registró. No hay contraseñas. Las estadísticas y las exportaciones pueden filtrarse
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

Se arranca con `hamrlog metrics`. Expone en
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
pytest                  # 319 pruebas, incluidas las de la interfaz
ruff check src tests
```

Las pruebas de interfaz usan el piloto de Textual: escriben en la línea de
entrada, pulsan teclas de función y comprueban el resultado, sin necesidad de
un terminal real.

Los comentarios y los identificadores del código están en inglés; los textos
que ve el usuario, en español.

## Cambios

Los de cada versión están en [CHANGELOG.md](CHANGELOG.md).

## Publicar una versión

Las releases se construyen solas: etiquetar y empujar compila el ejecutable de
Linux, el de Windows y el instalador, comprueba que las pruebas pasan y que
cada binario arranca, y lo publica todo con sus sumas SHA-256.

```bash
# El número vive en src/hamrlog/__init__.py; súbelo también en
# packaging/arch/PKGBUILD y packaging/windows/hamrlog.iss (hay pruebas que
# comprueban que no se queden atrás)
git tag -a v0.3.0 -m "v0.3.0"
git push origin v0.3.0
```

Los detalles están en [packaging/README.md](packaging/README.md).

## Licencia

MIT. Ver [LICENSE](LICENSE).
