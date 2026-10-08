# Arquitectura

El objetivo del diseño es que la interfaz de texto sea *una* forma de usar el
programa, no *la* forma. Por eso no hay lógica de negocio en los widgets.

## Capas

```
hamrlog/
├── paths.py        Rutas por sistema operativo (Linux, Windows, macOS)
├── core/           Dominio puro, sin base de datos ni interfaz
│   ├── bands.py        Plan de bandas IARU y análisis de frecuencias
│   ├── modes.py        Modos y su equivalencia ADIF (MODE/SUBMODE)
│   ├── callsign.py     Normalización de indicativos y prefijos DXCC
│   ├── units.py        Unidades de frecuencia y separadores numéricos
│   ├── repeaters.py    Desplazamientos por banda y tonos CTCSS
│   ├── contacts.py     Formatos de listín: RadioID, BrandMeister, CPS, JSON
│   ├── entry.py        Analizador de la línea de entrada rápida
│   ├── state.py        Configuración activa de la sesión
│   ├── dto.py          Objetos de lectura que consume la interfaz
│   ├── services.py     Toda la lógica de negocio y el acceso a datos
│   └── transfer.py     Importación y exportación (ADIF, CSV)
├── db/             Persistencia
│   ├── models.py       Modelos SQLAlchemy
│   ├── migrations.py   Añade columnas y tablas que falten al abrir
│   └── session.py      Motor, sesiones y esquema
├── adif/           Lectura y escritura del formato ADIF 3.1
├── i18n.py         Traducciones: _() y lectura de los .po
├── locales/es/     Traducciones al español, un .po por área
├── data/preseed/   Catálogo de emisoras, antenas, fuentes y la lista de
│                   repetidores de la URE (JSON, en español)
├── tui/            Interfaz Textual: una sola pantalla
│   ├── screens/        base.py = los dos diálogos (confirmación y formulario)
│   └── widgets/        detail.py = detalle de lo señalado en el histórico
├── api/            Métricas Prometheus y API REST opcional
└── cli.py          Punto de entrada y subcomandos
```

La regla es estricta: **`tui/` no contiene SQL ni objetos ORM**. Todo pasa por
`core/services.py`, que devuelve dataclasses de `core/dto.py`. Si mañana
existiera una web, consumiría exactamente los mismos servicios.

## Decisiones y por qué

**Frecuencias en hercios enteros.** Los flotantes acumulan error y las
comparaciones de banda se vuelven frágiles. La conversión a megahercios ocurre
solo al exportar a ADIF.

**Marcas de tiempo UTC ingenuas.** SQLite no guarda zona horaria. Normalizar al
escribir hace que SQLite y PostgreSQL se comporten igual. La interfaz muestra
UTC siempre, que es lo que va al log y a cualquier exportación.

**`entry_mode` (AUTO/MANUAL) en el modelo.** No es un detalle de presentación:
un QSO automático no admite cambiar su fecha y hora, que puso el programa; uno
manual, sí. La regla se aplica en el servicio, no en la pantalla, para que una
API futura no pueda saltársela.

**Los informes (RST) son texto.** Los modos digitales usan decibelios (`-12`),
no la escala RST clásica.

**Las unidades se guardan en la grafía del SI.** `MHz`, `kHz` y `Hz`, con la
kilo en minúscula porque la `K` mayúscula es el kelvin. `FrequencyFormat`
normaliza lo que reciba en lugar de rechazarlo, de modo que un ajuste escrito
por una versión anterior, o a mano en la base de datos, se sigue entendiendo.

**El formato de frecuencia es estado de módulo.** `core/units.py` guarda el
formato activo y `bands.format_frequency` delega en él, de modo que cambiar la
preferencia se refleja en toda la interfaz sin pasarla por parámetro a veinte
widgets. Es estado global, admitido porque es presentación y no datos: lo que
se almacena son hercios enteros, siempre.

**Ya no se adivina la unidad por la magnitud.** Antes `7130` se leía como
kilohercios y `14.250` como megahercios según su tamaño, así que el mismo texto
significaba cosas distintas según el número. Ahora un número sin unidad usa la
configurada, y la unidad escrita a mano manda sobre ella.

**Dos frecuencias por contacto.** `freq_hz` es la que el operador sintoniza, que
por repetidor es la de salida; `freq_tx_hz` es la de transmisión cuando difiere,
es decir la entrada del repetidor. La interfaz enseña la primera, que es la que
todo el mundo reconoce, y ADIF exporta la segunda como `FREQ` con la primera
como `FREQ_RX`, que es lo que manda la norma para un QSO en split.

**La pantalla principal tiene un solo foco.** El teclado vive en la línea de
entrada y nunca se mueve; el histórico es `can_focus = False` y su cursor se
gobierna desde allí con mensajes. Así no hay estado de «qué panel está activo»
que recordar en mitad de un pile-up, y Tab deja de significar nada.

**El panel de detalle no se queda en blanco.** Sobre un QSO muestra lo que la
tabla no puede enseñar; sobre la fila de inserción, lo que heredará el próximo
contacto. Un panel vacío la mitad del tiempo sería espacio gastado en una
pantalla donde el histórico se lo disputa.

**La fila `<Insertar nuevo>` es estado, no adorno.** Estar sobre ella significa
«escribiendo»; estar sobre un QSO significa «mirando». La posición del cursor
resume por sí sola en qué modo está la pantalla, y la línea de entrada cambia
con ella: campo de texto en una, barra de acciones en la otra.

**Una casilla por campo, no una línea con separadores.** La línea única
obligaba a contar comas para saber en qué campo se estaba escribiendo, y el
separador tenía que quedar prohibido dentro de los valores. Con una casilla por
campo, `Tab` sustituye al separador y una coma en las notas es solo una coma.
`entry.parse()` sigue existiendo para el CLI y para una API futura; la interfaz
usa `entry.from_fields()`, y ambas comparten `entry.finish()`, de modo que la
validación y las conversiones son las mismas por los dos caminos.

**Navegando, las letras no escriben.** `D`, `E` y `R` son letras corrientes en
un indicativo. Un modo que a veces las escriba y a veces borre un QSO sería una
trampa, así que escribir queda desactivado mientras el cursor está sobre un
registro y una tecla desconocida explica dónde estás en lugar de no hacer nada.
El borrador a medio escribir se guarda al entrar y se restaura al salir.

**Una sola pantalla, sin menús.** Hubo nueve pantallas de gestión (registro,
selectores de banda, frecuencia y modo, configuración, equipo, perfiles,
agenda y repetidores) tras una barra de atajos `Alt`+letra. La vista principal
funcionaba y ellas no convencían, así que se retiraron enteras para
rediseñarlas: `tui/` es ahora la pantalla principal más dos diálogos
(`ConfirmScreen` y `FormScreen`), y la sesión se cambia con comandos `/` en la
línea de entrada. Los servicios que esas pantallas usaban siguen intactos en
`core/services.py`; lo que falta es solo la presentación.

**Se edita en la línea de entrada, no en un formulario aparte.** `E` sobre un
QSO rellena las mismas casillas con las que se registró, más una segunda fila
(`#entry-extra`) con frecuencia y modo, que un QSO nuevo hereda de la
sesión y por eso no tienen casilla. La banda no se ofrece: es un valor
calculado a partir de la frecuencia, y dejar escribir las dos permitiría que
se contradijeran. Mientras dura, las flechas no mueven el
cursor: el formulario pertenece a esa fila. La tabla se redibuja celda a celda
(`HistoryPanel.replace_row`) para no perder la posición.

**El Inventario reutiliza el registro en vez de imitarlo.** `F2` no abre otra
pantalla: oculta el histórico, muestra `InventoryView` en el mismo marco y
reconstruye la línea de entrada con las casillas de la pestaña. Cada pestaña es
una `Kind` (`tui/inventory.py`) que declara columnas, casillas y cómo se
guardan; la navegación, la fila `<Nuevo …>`, la barra de acciones y la edición
son las del registro. Lo escrito a medias se guarda por vista y pestaña. La
Agenda (`F3`, `tui/address_book.py`), los Perfiles (`F4`, `tui/profiles.py`)
los Repetidores (`F5`, `tui/repeaters.py`), las Herramientas (`F8`,
`tui/tools.py`) y la Configuración (`F9`, `tui/settings.py`) son otras `Kind`
sobre el mismo mecanismo. Una `Kind` puede no admitir altas (`can_add`, sin
fila `<Nuevo …>`) ni bajas (`can_delete`), o ser de solo lectura
(`browses=False`): entonces la línea de entrada es una casilla que filtra la
lista mientras se escribe, y las flechas la recorren sin pasar a la barra de
acciones.

**La configuración de la aplicación no está en la base de datos.** La ruta
de la base de datos, el idioma, la zona horaria y el separador de días viven
en `config.json` (`hamrlog/appconfig.py`), en la carpeta de configuración:
la base de datos no puede guardar su propia ruta y el idioma hace falta antes
de pintar nada. Las variables de entorno mandan sobre el fichero.

**El perfil activo es el estado de la sesión.** Activar un perfil
(`ProfileService.apply_to_state`) copia sus valores en `SessionState`, y
`QsoService.log` solo lee el estado: no sabe nada de perfiles. El estado
recuerda `profile_id` para marcarlo en la lista y en la línea de estado; un
cambio a mano (`/banda`, `/frec`…) llama a `leave_profile()`, que olvida el
perfil pero conserva sus valores. Con un equipo en el estado, cada QSO toma la
emisora y la antena del equipo que cubran su frecuencia
(`Equipment.parts_for`), como al asignar un equipo a mano.

**Dos identificadores.** Cada emisora, antena y fuente tiene su `id`
autoincremental, que es el que usan las claves ajenas, y su `code` (`E0001`,
`A0001`, `S0001`), que es el que lee y escribe el operador. El código tiene
índice único y lo asigna `db/codes.py` al crear la fila; al arrancar, además,
`assign_missing_codes` da código a cualquier fila que no lo tenga (bases
antiguas, catálogo) y crea el índice si falta.

**Las teclas de función son de cada vista.** Todas pasan por
`action_function_key`, que decide según la vista; una tecla sin uso no hace
nada en vez de llegar a la línea de entrada, y sobre un diálogo se cede a él
con `SkipAction`. `F1` es siempre el registro.

**El catálogo vive en la base de datos, marcado.** Los elementos de
`data/preseed` se insertan como filas con `preset = True` y son los servicios
los que se niegan a modificarlas o borrarlas, de modo que la regla vale igual
para la interfaz y para una API. La carga es idempotente (por nombre, sin
distinguir mayúsculas; los repetidores, por indicativo y frecuencia de salida)
y lee cualquier fichero de la carpeta, que declara su `tipo`. Esos ficheros son
lo único escrito en español.

**Un indicativo no identifica un repetidor.** La URE publica varios
repetidores con el mismo indicativo (bandas o modos distintos), así que desde
el esquema 11 `repeaters.callsign` no es único; lo es, en el servicio, el par
indicativo + salida. `RepeaterService.resolve` lee lo que escribe el operador
(«ED4ZAH», «ED4ZAH DMR», «ED4ZAH 438.325») y `label` produce el texto que
`resolve` vuelve a leer, que es lo que guardan y muestran los perfiles.

**Inglés en el código, traducciones aparte.** Los textos de origen están en
inglés dentro de `_()`; `N_()` marca los de tablas construidas al importar,
que se traducen al mostrarse. Los `.po` se leen directamente, sin compilar a
`.mo`: son pocos y así no hay ficheros generados que mantener. Una prueba
falla si algún texto marcado no tiene traducción.

**La agenda no tiene claves ajenas al log.** Un listín de usuarios DMR son
decenas de miles de filas que llegan de golpe y se reemplazan enteras; atarlas
a los QSO obligaría a mantener esa relación en cada importación. El enlace se
hace por `base_call` en el momento de consultar, que está indexado.

**La detección de formato va por cabeceras, no por nombre de fichero.** Las
listas de usuarios DMR cambian de columnas y de origen cada temporada. Se
normalizan los encabezados y se buscan alias conocidos, de modo que un fichero
con columnas familiares en otro orden sigue entrando. Sin cabeceras, solo se
acepta el orden de RadioID y únicamente si la primera fila tiene un ID DMR y un
indicativo con forma válida: lo contrario llenaría la agenda de basura.

**La importación nunca pisa lo escrito a mano.** Solo rellena campos vacíos.
Un nombre anotado durante un QSO vale más que el de una lista descargada.

**El alta automática crea y, como mucho, pone nombre.** Registrar un indicativo
desconocido añade su ficha; si ya existe, se deja intacta, salvo que no tenga
nombre: entonces toma el del QSO, porque una ficha sin nombre no dice nada que
proteger. Actualizarla con cada
QSO convertiría la agenda en un reflejo del último contacto en lugar de en lo
que el operador sabe de esa persona. Vive en `QsoService.log`, no en la
interfaz, para que una API futura se comporte igual, y captura sus errores: un
fallo en la agenda no puede costar el QSO. Las importaciones de ADIF pasan por
otro camino (`transfer._insert`) y por eso no la alimentan.

**`repeater_call` está desnormalizado.** El contacto guarda el indicativo del
repetidor además de la clave ajena, para que borrar un repetidor de la lista no
borre el hecho de que se usó.

**Campos desconocidos en `extra`.** Un ADIF importado de otro programa conserva
los campos que hamrlog no entiende, de modo que reexportarlo no pierde nada.

**SQLAlchemy en lugar de Django.** La interfaz tiene que abrirse al instante;
Django habría añadido un arranque más lento y muchas dependencias a cambio de
ventajas que solo importarían en la web. Si esa web llega, FastAPI reutiliza
estos mismos modelos.

## Cómo extenderlo

**Un campo nuevo en los contactos.** Añádelo a `db/models.py`, a `core/dto.py`,
a la conversión `_to_row` de `services.py` y al exportador ADIF. Sube
`CURRENT_SCHEMA_VERSION` si necesita migración.

**Un modo nuevo.** Una entrada en la tupla correspondiente de `core/modes.py`,
con su `adif_mode` y su `adif_submode`. Si necesita datos propios, añádelos en
`digital_fields`: las preguntas tras `/modo` se generan solas a partir de esa definición.

**Un formato de listín nuevo.** Añade sus encabezados a `HEADER_ALIASES` en
`core/contacts.py`; si es para escribir, una rama en `_rows_for` y una entrada
en `EXPORT_FORMATS`.

**Una banda nueva.** Una entrada en `BANDS`, en `core/bands.py`. Si tiene
repetidores, añade también su desplazamiento habitual a `DEFAULT_SHIFTS` en
`core/repeaters.py`.

**Una columna nueva en una tabla existente.** Añádela al modelo y sube
`CURRENT_SCHEMA_VERSION`: `db/migrations.py` la añade sola al abrir una base de
datos anterior. Renombrar o eliminar columnas sí necesitaría una herramienta de
migración de verdad.

**Escritura en la API.** Los servicios ya validan las reglas de negocio y
lanzan `ServiceError`. Lo único que falta decidir es la autenticación.

**Una interfaz web.** `core/services.py` más `api/schemas.py` cubren la capa de
datos; falta la de presentación.

## Esquema de la base de datos

| Tabla | Contenido |
|---|---|
| `operators` | Operadores locales. Nunca se borran: sus contactos los referencian |
| `stations` | Emisoras (marca, modelo, potencia, tipos). `preset` marca las del catálogo |
| `antennas` | Antenas con sus bandas y marca |
| `power_supplies` | Fuentes de alimentación: tensión, corriente, marca |
| `equipment` | Equipos: conjuntos de emisoras, antenas y fuentes |
| `repeaters` | Repetidores (F5): número URE, canal, frecuencias, shift, CTCSS y datos digitales. `preset` marca los de la lista de la URE |
| `contacts` | Agenda: quién es cada indicativo, con su ID DMR |
| `profiles` | Perfiles (F4): operador, equipo, frecuencia, modo, potencia, repetidor, datos digitales, tecla `Ctrl+0…9` y predeterminado |
| `qsos` | Contactos, con `digital_data` y `extra` en JSON, y el equipo con que se hicieron (`equipment_id`) |
| `settings` | Clave/valor: estado de la sesión, métricas |
| `schema_version` | Revisión del esquema, para migraciones futuras |
