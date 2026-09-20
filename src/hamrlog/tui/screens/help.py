"""F1: keyboard reference and command list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown, Static

HELP_TEXT = """
## La pantalla principal

El recuadro **Registro** ocupa el centro y tiene dos mitades: arriba la lista
de QSO, y debajo el **detalle** de lo que tengas señalado, con todo lo que no
cabe en una fila (locator, equipo, operador, datos del modo digital, el
comentario completo, y las dos frecuencias cuando sales por un repetidor).

Sobre `<Insertar nuevo>`, ese mismo espacio muestra lo que heredará el próximo
QSO: operador, banda, frecuencia, repetidor, modo, equipo y el informe por
defecto. Así sabes con qué se va a registrar antes de pulsar Enter.


El teclado **siempre está en la línea de entrada**. No hay que pulsar Tab ni
cambiar de panel: escribes, y las flechas recorren lo ya registrado.

La línea de abajo tiene **dos estados**, y cuál sea depende de dónde esté el
cursor del histórico:

**Sobre `<Insertar nuevo>`** es el formulario: una casilla por campo, `Tab`
entre ellas, `Enter` registra.

**Sobre un QSO ya registrado** deja de aceptar texto y ofrece lo que se puede
hacer con él:

```
 D suprimir · E editar · R repetir · ↓ volver a escribir
```

| Tecla | Efecto |
|---|---|
| `D` | Borra ese QSO, con confirmación |
| `E` | Lo abre para editarlo |
| `R` | Lo devuelve a la línea de entrada para repetirlo |
| `↓` o `Esc` | Vuelve a `<Insertar nuevo>` y a escribir |

**Repetir** (`R`) trae el contacto de vuelta a la línea, editable: cambias lo
que sea distinto y pulsas `Enter` para registrarlo otra vez. Se guarda con la
banda y el modo de ahora, no con los de entonces, porque repetir significa
volver a trabajar a esa estación.

Mientras navegas, las letras **no escriben**: `D`, `E` y `R` son letras
corrientes en un indicativo, y una tecla que unas veces escribe y otras borra
sería una trampa. Si empiezas a teclear sin querer, se te recuerda dónde estás.

Lo que tuvieras a medio escribir **se guarda** al subir al histórico y vuelve
intacto al bajar.

| Tecla | Siempre |
|---|---|
| `↑` `↓` | Recorren el histórico. `Re Pág` y `Av Pág` van de diez en diez |
| `Enter` con texto escrito | Guarda un QSO nuevo, estés donde estés |
| `Ctrl+D` | Borra el QSO señalado, o el último si estás escribiendo |
| `Ctrl+↑` `Ctrl+↓` | Recuperan líneas que escribiste antes |

La última fila del histórico es siempre **`<Insertar nuevo>`**: es el sitio
donde aparecerá el próximo QSO, y donde vuelve el cursor solo después de
guardar.

En **F5 → Histórico** eliges la dirección: los nuevos abajo (la lista crece
hacia abajo, es lo normal) o los nuevos arriba. La fila `<Insertar nuevo>`
acompaña siempre al extremo por el que crece.

## Las confirmaciones

Antes de borrar algo siempre se pregunta, y se puede responder de tres maneras:
`←` `→` (o `Tab`) mueven entre los botones y `Enter` confirma el señalado; `S`
dice que sí directamente; `N` o `Esc` dicen que no. El botón **No** viene
seleccionado de partida, para que un Enter por inercia no borre nada.

## El menú de arriba

`F10` activa la barra superior: `←` y `→` la recorren, `Enter` abre la entrada
señalada y `Esc` vuelve a escribir, igual que en Midnight Commander. Sirve como
salida si tu terminal se queda con alguna tecla de función.

## Flujo de trabajo

Configura la sesión una vez (banda, frecuencia, modo, equipo) y a partir de ahí
escribe únicamente en la línea de entrada. Cada Enter guarda un contacto con la
fecha y hora UTC automáticas.

```
ea7wm,victor,59,57
```

El orden de los campos se configura en **F10 → Entrada rápida**. Por defecto es
`indicativo, nombre, rst_env, rst_rec, qth, notas`.

También puedes asignar un campo por nombre en cualquier posición:

```
ea7wm,victor,grid=IM76,tg=214,nota=por el repetidor
```

## Indicativos mal escritos

Al teclear, el indicativo se comprueba contra la forma que tiene un indicativo
real: prefijo, dígito y sufijo. Si no encaja, se avisa mientras escribes y al
pulsar Enter **no se guarda**, indicando qué está mal (le falta el número, es
demasiado corto, lleva caracteres raros...).

Si de verdad quieres registrar uno inusual que el filtro no admite, termínalo
en `!`:

```
bv100!,chen
```

El comportamiento se cambia en **F10 → Entrada rápida → Validar indicativos**:
`estricta` (por defecto), `avisar` (lo registra con una advertencia) o `no`.

## Teclas

| Tecla | Acción |
|---|---|
| `F1` | **Registro**: los QSO que llevas hechos |
| `F2` | Selector de banda |
| `F3` | Frecuencia |
| `F4` | Modo: SSB, CW, FM, AM, DMR, C4FM, D-STAR, FT8... todos juntos |
| `F5` | Configuración, incluidas importación y exportación del registro |
| `F6` | Equipo (emisora y antena) |
| `F7` | Perfiles: cargar y guardar configuraciones |
| `F8` | **Contactos**: la agenda de quién es cada indicativo |
| `F9` | Repetidor: por dónde sales, y alta de repetidores |
| `F10` | Menú: recorre la barra de arriba con `←` `→` |
| `Ctrl+F1` | Esta ayuda (también `F12` y `/ayuda`) |
| `Ctrl+Q` | Salir |

**Registro** y **Contactos** son cosas distintas: el registro (`F1`) es lo que
has trabajado y cuándo; los contactos (`F8`) son quién es cada cual. Desde
cualquiera de las dos, la tecla de la otra te lleva allí directamente.

Si tu terminal captura alguna tecla de función (`F10` abre el menú en varios
emuladores de Linux), usa el comando equivalente en la línea de entrada.

## Comandos de la línea de entrada

| Comando | Equivale a |
|---|---|
| `/banda 20m` | Cambia de banda sin abrir el selector |
| `/frec 14.250` | Fija la frecuencia |
| `/modo cw` o `/modo dmr` | Cambia de modo, analógico o digital |
| `/equipo` | Abre el selector de equipo |
| `/perfil` o `/perfil HF-Casa` | Abre perfiles o carga uno directamente |
| `/registro` o `/log` | El registro de QSO |
| `/contactos` o `/agenda` | La agenda |
| `/exportar` o `/importar` | Importar y exportar el registro |
| `/borrar` | Borra el último contacto registrado |
| `/repetidor` o `/repetidor ED7ZAE` | Abre la lista o selecciona uno directamente |
| `/directo` | Vuelve a simplex, sin repetidor |
| `/config` | Configuración |
| `/ayuda` | Esta ayuda |
| `/salir` | Cerrar la aplicación |

## Los contactos (agenda)

`F8` abre la agenda: nombre, ciudad, provincia, ID DMR, país y cuántos QSO
llevas con cada estación.

La agenda se llena sola con lo que trabajas: **al registrar un indicativo que
no esté en ella, se da de alta**, con el nombre, el QTH y el país del propio
QSO. Un indicativo que ya esté no se toca, porque lo que hayas escrito ahí vale
más que lo que traiga un contacto suelto. Las estaciones portables (`F/EA4ABC/P`)
se archivan bajo el indicativo de casa, así que no se duplican.

De vuelta, mientras escribes un indicativo conocido aparece quién es debajo de
la línea de entrada, y al pulsar Enter el nombre y el QTH que no hayas escrito
se rellenan desde la agenda. **Lo que tú escribas siempre manda** sobre lo que
diga el listín.

Las dos cosas se desactivan en **F5 → Histórico y agenda**. Importar un ADIF no
da de alta contactos: solo lo hace lo que registras en directo.

### Importar listas de usuarios DMR

Desde la agenda, `Ctrl+I`. El formato se detecta solo, así que sirve cualquiera
de estos sin convertir nada:

* CSV de **RadioID.net** (`RADIO_ID,CALLSIGN,FIRST_NAME,...`), con o sin
  cabecera.
* CSV de **BrandMeister**, incluidos los que traen el nombre en una sola
  columna y los que usan `;` como separador.
* CSV del **CPS de la radio** (Anytone D878UV y compatibles).
* **JSON** de las APIs de RadioID y BrandMeister.
* El CSV que exporta el propio hamrlog.

Puedes filtrar por país al importar, para quedarte solo con el 214 de una lista
mundial. Reimportar no duplica: actualiza lo que falte y **nunca pisa un dato
que hayas escrito tú a mano**.

### Exportar a la radio

`Ctrl+O` desde la agenda, eligiendo formato: `anytone` genera el CSV que el CPS
de la D878UV espera (con sus columnas `No.`, `Call Type` y `Call Alert`),
`radioid` el formato estándar y `hamrlog` el propio. En el formato de la radio
se omiten los contactos sin ID DMR, porque el equipo no puede usarlos.

## Borrar QSO del registro

Hay tres formas, según dónde estés:

* **`Ctrl+D` desde la línea de entrada** borra el último contacto registrado.
  Es lo que quieres cuando acabas de guardar un indicativo mal escrito.
* **`Tab` hasta el histórico, `↑↓` para elegir y `Supr`** borra el contacto
  que tengas seleccionado.
* **`F1`, elegir en la lista y `Supr`** (o `Ctrl+D`, que funciona también
  mientras escribes en el buscador). Desde ahí puedes buscar primero, lo que
  es más cómodo cuando el QSO es antiguo.

Siempre se pide confirmación indicando el indicativo, la fecha, la banda y el
modo del contacto que se va a borrar.

## Salir por un repetidor

`F9` elige por dónde sale tu señal. Al seleccionar un repetidor se adopta todo
lo que define: frecuencia de escucha y de transmisión, banda, modo y sus datos
digitales (color code, talkgroup, reflector, room). A partir de ahí solo tienes
que registrar indicativos.

Para dar uno de alta, `F9` y luego `N`. Basta con el indicativo y la frecuencia
de salida (la que sintonizas): el desplazamiento se calcula solo según la banda
(-600 kHz en 2 m, -7,6 MHz en 70 cm) y puedes ajustarlo si tu repetidor es
atípico. Si el modo es digital se piden después sus parámetros propios.

Cambiar de banda o de frecuencia a mano (`F2`, `F3`) te saca del repetidor,
porque ya no describen dónde estás trabajando. `D` en la lista, o `/directo`,
vuelve a simplex.

En el log queda registrado el indicativo del repetidor, y en la exportación
ADIF el contacto sale como lo que es: `FREQ` con la frecuencia de entrada (lo
que transmites), `FREQ_RX` con la de salida (lo que escuchas) y `PROP_MODE=RPT`.

## Contactos automáticos y manuales

* **AUTO**: la fecha y la hora las pone el programa al pulsar Enter. Es la
  prueba de cuándo ocurrió el contacto, así que solo se permite corregir el
  indicativo (un error de escucha es lo único que se corrige después).
* **MANUAL**: contactos añadidos con fecha a mano (`F8 → Ctrl+N`) o importados
  desde ADIF. Todos sus campos son editables.

## Dónde se guarda todo

Una base de datos SQLite en la carpeta de datos del usuario. Se muestra la ruta
exacta en **F10 → Información del sistema**. Para usar PostgreSQL basta con
definir `HAMRLOG_DATABASE_URL`.
"""


class HelpScreen(ModalScreen[None]):
    """Scrollable keyboard and command reference."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("ctrl+f1", "close", "Cerrar", show=False),
        Binding("f12", "close", "Cerrar", show=False),
        Binding("q", "close", "Cerrar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal modal-wide"):
            yield Label("Ctrl+F1 · Ayuda", classes="modal-title")
            with VerticalScroll(classes="help-body"):
                yield Markdown(HELP_TEXT)
            yield Static("Esc o Q para cerrar · ↑↓ para desplazar", classes="modal-help")

    def on_mount(self) -> None:
        self.query_one(VerticalScroll).focus()

    def action_close(self) -> None:
        self.dismiss(None)
