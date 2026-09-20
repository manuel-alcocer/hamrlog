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
├── tui/            Interfaz Textual (widgets y pantallas)
│   ├── screens/        log.py = registro de QSO, contacts.py = agenda
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
determina qué campos se pueden editar. La regla se aplica en el servicio, no en
la pantalla, para que una API futura no pueda saltársela.

**Los informes (RST) son texto.** Los modos digitales usan decibelios (`-12`),
no la escala RST clásica.

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

**Registro y agenda son pantallas separadas.** Empezaron como dos pestañas de
una misma pantalla y se demostró confuso: en radioafición «contactos» es la
gente, no los QSO. Ahora `F1` es el registro (`tui/screens/log.py`) y `F8` la
agenda (`tui/screens/contacts.py`), y se sustituyen la una a la otra en vez de
apilarse.

**Un solo selector de modo.** Analógicos y digitales estaban en `F4` y `F5`,
una distinción que le importa al programa y no al operador, que solo piensa en
«modo». Ahora `F4` los lista todos con el grupo buscable en el filtro.

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

**El alta automática solo crea, nunca actualiza.** Registrar un indicativo
desconocido añade su ficha; si ya existe, se deja intacta. Actualizarla con cada
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
`digital_fields`: la pantalla F5 se genera sola a partir de esa definición.

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
| `stations` | Equipos (emisora, antena, potencia) |
| `repeaters` | Repetidores: frecuencias, shift, CTCSS y datos digitales |
| `contacts` | Agenda: quién es cada indicativo, con su ID DMR |
| `profiles` | Configuraciones guardadas, incluido el formato de la entrada rápida |
| `qsos` | Contactos, con `digital_data` y `extra` en JSON |
| `settings` | Clave/valor: estado de la sesión, métricas |
| `schema_version` | Revisión del esquema, para migraciones futuras |
