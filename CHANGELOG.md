# Cambios

## Sin publicar

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
- 319 pruebas, 79 más que en la versión anterior.

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
