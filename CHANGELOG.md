# Cambios

## Sin publicar

### Instaladores

- **Windows**: el instalador gráfico actualiza además de instalar. Detecta la
  versión instalada y lo dice en el título y en el resumen; con la misma
  versión ofrece reparar y con una más nueva pregunta antes de volver atrás
  (en modo silencioso no lo hace). Cierra hamrlog si está abierto, reconstruye
  la demo y conserva carpeta y opciones.
- **Windows**: al desinstalar se quita `hamrlog` del PATH (antes se quedaba),
  se borra la plantilla de la demo y se pregunta si borrar el diario. Textos
  del asistente en español e inglés.
- **Linux**: instalador nuevo (`hamrlog-install.sh` y el tarball
  `hamrlog-X.Y.Z-linux-x86_64.tar.gz`) que instala el ejecutable sin Python,
  con entrada en el menú de aplicaciones, y admite `--upgrade`,
  `--uninstall`, `--purge`, `--system` y `--version`. Comprueba las descargas
  con SHA-256.
- La release prueba en Windows la instalación, la actualización, el rechazo
  del downgrade y la desinstalación, y en Linux la instalación y la
  desinstalación.

### Publicación

- Las versiones se publican solas con semantic-release a partir de los
  commits: tras cada push a `main` que pase las pruebas, si hay un `feat` o un
  `fix` nuevo, se sube el número, esta sección pasa a llamarse como la
  versión y se construye y publica la release, con este CHANGELOG como notas.

### Teclas de función

- `F1` … `F5` llevan a su sección desde cualquier otra, no solo desde el
  registro.
- Las pestañas (Inventario) se recorren en ciclo con `Ctrl+N`; `F5`/`F6` ya no
  cambian de pestaña. `Mayús+RePág`/`Mayús+AvPág` siguen yendo atrás y
  adelante.

### Repetidores (`F5`)

- `F5` muestra los **repetidores** en el recuadro del registro, como la
  Agenda: número de la URE (`R5`), indicativo, salida, entrada, tono CTCSS,
  modo, canal IARU, locator y titular. Se buscan con `/buscar` (`R5`,
  `dmr madrid`, `IN80`…).
- Alta y edición en la línea de entrada; la entrada admite una frecuencia o un
  desplazamiento (`-600`, `-7.6 MHz`).
- `Enter` sobre un repetidor lo sintoniza, como `/repetidor`.
- **Lista de la URE**: se cargan de forma idempotente los 268 repetidores de
  [ure.es/repetidores](https://www.ure.es/repetidores/) (10 m, 6 m, 2 m,
  70 cm y 23 cm), que no se pueden modificar ni borrar.
- Un indicativo puede ser varios repetidores; se elige uno con la frecuencia,
  el modo o la banda: `/repetidor ED4ZAH DMR`, también en los perfiles.
- Corregido: en las listas largas (Repetidores, Agenda) la fila `<Nuevo …>`
  quedaba oculta justo debajo del borde al abrir la vista.
- Esquema 11: el indicativo de los repetidores deja de ser único y ganan número
  URE, canal y marca de catálogo; las bases de datos anteriores se actualizan
  solas.

### Perfiles (`F4`)

- `F4` muestra los **perfiles** en el recuadro del registro, como el
  Inventario y la Agenda. Un perfil guarda operador, equipo del Inventario,
  frecuencia (y con ella la banda), modo, potencia, repetidor y datos del modo
  digital (`TG=214, CC=1`).
- `Enter` sobre un perfil lo **activa**: los QSO que se escriban en el
  registro se guardan con sus datos, y con la emisora y la antena del equipo
  que cubran su frecuencia.
- Diez perfiles **principales** llevan una cifra del 0 al 9 y se activan con
  `Ctrl+0` … `Ctrl+9` desde cualquier ventana; `/perfil 3` hace lo mismo.
- `*` marca el perfil **predeterminado**, que se activa al arrancar.
- La línea de estado dice `PERFIL` en lugar de `CONFIG`, y las
  «configuraciones» pasan a llamarse perfiles en los mensajes.
- Esquema 10: los perfiles ganan equipo, potencia y tecla; las bases de datos
  anteriores se actualizan solas.

### Agenda (`F3`)

- `F3` muestra la agenda como lista en el recuadro del registro: alta,
  edición (`E`) y borrado (`D`) desde la línea de entrada, que aquí tiene dos
  filas de casillas (indicativo, nombre, apellidos, ID DMR, locator; ciudad,
  provincia, país, correo, notas).
- `/buscar texto` busca en indicativo, nombre, ciudad, provincia, país o ID
  DMR; la lista enseña como mucho 500 fichas y la cabecera dice cuántas hay.
- El país se escribe en tu idioma y se guarda en inglés.
- Editar una ficha comprueba que el indicativo y el ID DMR no estén ya en
  otra.
- El pie se acorta en terminales estrechos en vez de quitar la ayuda entera.

### Inventario (`F2`)

- `F2` convierte el recuadro del registro en el **Inventario**, con cuatro
  pestañas: Equipos, Emisoras, Antenas y Fuentes. Funciona como el registro:
  lista arriba, `<Nuevo …>` al final y la línea de entrada para escribir.
  `F5` `F6` o `Mayús+RePág` `Mayús+AvPág` cambian de pestaña, `RePág` `AvPág`
  pasan página en la lista de cada ventana y `F1` vuelve al registro; lo que
  estuvieras escribiendo en cada sitio se conserva.
- Las teclas de función dependen de la ventana. `F1` es siempre el registro;
  la que una ventana no usa no hace nada.
- Un **equipo** es un conjunto de al menos una emisora, con antenas y fuentes.
  Emisoras, antenas y fuentes se dan de alta sueltas y pueden estar en varios
  equipos. Las casillas de un equipo completan los nombres con `→`.
- Cada emisora, antena y fuente tiene un **ID propio** automático y único
  (`E0001`, `A0001`, `S0001`), aparte del identificador interno. Los equipos
  aceptan esos ID en lugar de los nombres.
- Nuevas **fuentes de alimentación** (tensión y corriente) y **marca** en
  emisoras, antenas y fuentes, con filtro: `/marca icom`, `Alt+↑` `Alt+↓`.
- **Catálogo**: al abrir se cargan todos los ficheros de
  `hamrlog/data/preseed/` con equipos a la venta en tiendas españolas, sin
  duplicar. No se pueden modificar ni borrar; se usan al montar un equipo.
- No se puede borrar la única emisora de un equipo.

**Esquemas 6 a 9**: cada emisora existente se convierte en un equipo con su
mismo nombre y sus antenas; los países guardados en español pasan a inglés;
las emisoras, antenas y fuentes que ya existían reciben su ID por orden de
alta; y cada QSO puede guardar el equipo con que se hizo.

### Inglés y español

- Todo el código y los textos de origen pasan a inglés; el español es una
  traducción en `hamrlog/locales/es/*.po`. El idioma sale del sistema (en
  Windows, del idioma de su interfaz) y se fuerza con `HAMRLOG_LANG=en|es`.
- Los países se guardan con su nombre inglés, como los usa ADIF, y se
  muestran traducidos.

### Solo la pantalla principal

Las pantallas de menú se retiran para rediseñarlas; queda la vista principal.

- Desaparecen la barra de menús, los atajos `Alt`+letra, `Ctrl+F1`/`F12` y las
  pantallas Registro, Banda, Frec, Modo, Config, Equipo, Perfiles, Contactos,
  Rptr, Ayuda e importar/exportar.
- La sesión se cambia con comandos: `/banda 40m`, `/frec 7.100`, `/modo SSB`,
  `/perfil nombre`, `/repetidor IND`, `/directo`. Sin valor, cada uno dice
  cómo se usa, y `/ayuda` los lista bajo la línea de entrada.
- Ya no existen `/equipo`, `/config`, `/registro`, `/contactos`, `/exportar`
  ni `/importar`. Importar y exportar siguen en la línea de órdenes.
- Sobre un QSO del histórico, `D` suprime, `R` repite y `E` lo edita en la
  propia línea de entrada, sin abrir nada: aparecen sus valores y una segunda
  fila con frecuencia y modo; `Enter` guarda y `Esc` cancela. La banda no se
  escribe: se calcula a partir de la frecuencia.
- Un QSO automático admite corregir cualquier campo salvo la fecha y la hora
  (antes, solo el indicativo).
- Al editar un QSO se le asigna un **equipo** del Inventario; toma de él la
  emisora y la antena que cubren su frecuencia. Si el equipo no puede trabajar
  esa frecuencia o banda se guarda igual y se marca con `E` en la columna INFO.
- El registro tiene columna **QTH**; ya no se repite entre las notas.
- Columnas del registro: INFO, fecha y hora, indicativo, nombre, frecuencia,
  modo, equipo, país y QTH. Salen banda, RST y notas, que siguen en el
  detalle. INFO marca `S` (seleccionado), `E` (error) y `d` (el nombre no
  coincide con el de la agenda; el detalle dice cuál es). La fecha va sin
  segundos: `DD/MM/AA HH:MM` en español, `AA/MM/DD HH:MM` en inglés.
- `Espacio` marca QSO del registro y `Ctrl+A` los marca o desmarca todos. Con
  más de uno marcado, `E` edita a la vez su frecuencia, modo y equipo.
- Las listas ya no muestran barra de desplazamiento horizontal: con solo
  teclado no se podía usar; la última columna se acorta.
- Una raya separa las pestañas del Inventario de su lista.
- Al registrar un QSO, si el indicativo ya estaba en la agenda pero sin nombre
  o sin ciudad, la ficha toma el nombre y el QTH del QSO. Lo que ya tenía no
  se cambia, ni tampoco los QSO anteriores. Si no estaba, se crea, como
  antes.
- Se mantienen la confirmación de borrado, el asistente del primer arranque y
  la petición de datos de los modos digitales.
- Sin interfaz por ahora: agenda, alta de equipos, antenas,
  repetidores y configuraciones, cambio de operador y ajustes. Los datos y los
  servicios no se han tocado.

Las entradas de más abajo que describen esas pantallas quedan como historial.

### Sin ventanas flotantes, solo teclado

- Los menús ya no se abren como ventanas superpuestas: su contenido ocupa la
  zona del registro, con el mismo marco, y la barra de menús, la de estado, la
  línea de entrada y el pie siguen a la vista y sin oscurecerse. Formularios y
  confirmaciones aparecen en el mismo sitio.
- El ratón queda desactivado: todo se maneja con el teclado, y el terminal
  conserva el ratón para seleccionar y copiar texto.

### Perfiles: equipos y configuraciones

`Alt+P` pasa a tener dos niveles: los equipos y, dentro de cada uno, sus
configuraciones. `↑` `↓` eligen el equipo, `→` entra, `←` vuelve y `Enter`
carga el equipo y la configuración a la vez.

- **Configuraciones reutilizables**: una misma configuración puede asignarse a
  varios equipos (`A` en `Alt+P`) y quitarse de uno sin borrarla (`Supr`).
  Se gestionan todas en la nueva sección **Alt+C → Configuraciones**.
- **Tipos de equipo**: HF, CB, VHF y UHF de partida, cada uno con su
  frecuencia mínima y máxima. Se crean más en **Alt+C → Tipos de equipo**. Un
  equipo puede tener varios, y solo admite configuraciones que caigan dentro
  de alguno.
- La barra de estado muestra `CONFIG` en lugar de `PERFIL`.
- `/perfil nombre` carga la configuración sin cambiar de equipo.

- **Antenas con sus bandas**: nueva sección **Alt+C → Antenas**, donde cada
  antena lleva las bandas de radioaficionado en las que trabaja. En `Alt+E`
  cada equipo tiene su submenú de antenas (`A` asigna, `Supr` quita), y una
  antena puede estar en varios equipos. `Alt+P` pasa a tres niveles, equipo →
  antena → configuración, y bajo cada antena solo salen las configuraciones
  de sus bandas.
- Cada QSO guarda la antena usada; la exportación ADIF la escribe en
  `MY_ANTENNA`.

**Actualización de la base de datos** (esquema 4): cada perfil existente se
convierte en una configuración asignada al equipo que tenía; los que no tenían
equipo quedan en «Sin equipo». No se pierde nada.

**Esquema 5**: la antena que cada equipo tenía escrita pasa a ser una antena de
la nueva tabla, asignada a ese equipo (los equipos que nombraban la misma la
comparten), y los QSO hechos con ese equipo toman esa antena. Sus bandas
quedan sin indicar hasta que las rellenes.

### Atajos con Alt

Los menús se abren con `Alt` y una letra de su nombre en lugar de `F1` a `F9`.
La barra superior resalta esa letra dentro de cada palabra y ya no muestra
teclas aparte:

| Antes | Ahora | Pantalla |
|---|---|---|
| `F1` | `Alt+R` | Registro |
| `F2` | `Alt+B` | Banda |
| `F3` | `Alt+F` | Frecuencia |
| `F4` | `Alt+M` | Modo |
| `F5` | `Alt+C` | Configuración |
| `F6` | `Alt+E` | Equipo |
| `F7` | `Alt+P` | Perfiles |
| `F8` | `Alt+O` | Contactos |
| `F9` | `Alt+T` | Repetidor |

- **Adiós a `F10`**: el menú navegable con cursores desaparece.
- La ayuda sigue en `Ctrl+F1` (y `F12`).
- Se desactiva el protocolo de teclado de kitty: con él, Konsole y otros
  terminales entregan `Alt+P` como una «p» sin más y los atajos no llegan.
  Quien lo quiera activo puede arrancar con `TEXTUAL_DISABLE_KITTY_KEY=0`.
- Corregidas referencias antiguas que mandaban a `F10` para configurar el
  operador, la entrada rápida o las métricas: todo eso está en `Alt+C`.

## v0.2.0

### Unidades y formato de frecuencia

Toda frecuencia lleva ahora unidad, y cómo se muestran y se escriben se
configura en **F5 → Unidades y formato**.

- **Unidades**: `MHz`, `kHz` y `Hz`, con la grafía del Sistema Internacional.
  Se admite cualquier forma al escribir (`m`, `M`, `mhz`, `MHZ`, `k`, `K`,
  `khz`, `hz`, `HZ`...) y se guarda normalizada.
- **Unidad por defecto configurable**: un número sin unidad se interpreta con
  ella. La unidad que escribas a mano manda siempre sobre la configurada, así
  que `7130 k` son kilohercios aunque la preferencia sea megahercios.
- **Separadores decimal y de millar configurables**. Nunca pueden ser el
  mismo, y el de millar admite «ocultar» para no agrupar las cifras.
- La columna de frecuencia del registro indica su unidad en la cabecera en
  lugar de repetirla en cada fila.

**Cambio de comportamiento**: antes se adivinaba la unidad según el tamaño del
número, de modo que `7130` eran kilohercios y `14.250` megahercios. El mismo
texto significaba cosas distintas según el número. Ahora un número sin unidad
usa siempre la configurada.

Dos excepciones deliberadas: los desplazamientos de repetidor sin unidad siguen
siendo kilohercios, porque así se escriben en las radios, y la exportación ADIF
mantiene megahercios con punto, que es lo que fija la norma para que el fichero
lo lea cualquier otro programa.

### Mantenimiento

- El número de versión vive en un solo sitio (`src/hamrlog/__init__.py`) y las
  pruebas comprueban que el paquete de Arch y el instalador de Windows no se
  quedan atrás.
- En Windows la base de datos se reabría en cada acceso. SQLAlchemy escribe
  los dos puntos de la unidad (`C:`) como `C%3A`, así que el motor abierto
  nunca se reconocía.
- Las pruebas vuelven a pasar con Python 3.10, que no trae `tomllib`.
- 385 pruebas, 66 más que en la versión anterior.

## v0.1.0

Primera versión. Diario de contactos en modo texto que funciona igual en
consola de Linux y en PowerShell.

- Entrada rápida por casillas, navegada con Tab.
- Aviso de duplicado y consulta de la agenda mientras escribes.
- Validación de indicativos, con escape explícito para los inusuales.
- Navegación del registro desde la propia línea de entrada, con acciones de
  suprimir, editar y repetir.
- Agenda de contactos que se llena sola con lo que trabajas e importa listas
  de usuarios DMR de RadioID, BrandMeister, el CPS de la radio y sus APIs,
  detectando el formato.
- Repetidores con desplazamiento, subtono CTCSS y parámetros digitales.
- ADIF 3.1, CSV, perfiles y varios operadores locales.
- Métricas Prometheus y API REST opcionales.
