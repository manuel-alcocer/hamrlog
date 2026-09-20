# Cambios

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
