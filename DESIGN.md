---
name: Hilo
description: Cuaderno local de proyectos, agenda y evidencia metodológica Ruta DIA
colors:
  accent: "#294eb8"
  accent-hover: "#2142a0"
  text: "#263348"
  muted: "#5f6d82"
  evidence-text: "#627087"
  line: "#e1e6ef"
  background: "#f3f5f9"
  surface: "#ffffff"
  navigation-background: "#2a55bc"
  navigation-selected: "#ffffff26"
  workspace-background: "#edf2fb"
  workspace-border: "#d8e1f0"
  sidebar-ink: "#f0f5fe"
  sidebar-ink-muted: "#ffffffdb"
  sidebar-active-ink: "#ffffff"
  inspector: "#ffffff"
  green: "#267054"
  red: "#a53c3c"
  calendar-today-paper: "#d9ee9b"
  calendar-task-dot: "#c8771a"
  calendar-conversation-dot: "#617da9"
  note-yellow-paper: "#f7e594"
  note-yellow-fold: "#dec976"
  note-yellow-ink: "#4c3c16"
  note-pink-paper: "#f3bac5"
  note-pink-fold: "#da97a5"
  note-pink-ink: "#542630"
  note-blue-paper: "#b5ddf2"
  note-blue-fold: "#90bfd9"
  note-blue-ink: "#21465b"
  note-green-paper: "#c8e3ba"
  note-green-fold: "#a4c692"
  note-green-ink: "#314c27"
  note-purple-paper: "#ddcaef"
  note-purple-fold: "#bfa6d8"
  note-purple-ink: "#49315f"
  note-orange-paper: "#f7cea6"
  note-orange-fold: "#ddac7f"
  note-orange-ink: "#593619"
typography:
  body:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  conversation:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.75
  title:
    fontSize: "13px"
    fontWeight: 600
  control:
    fontSize: "13px"
    fontWeight: 600
  label:
    fontSize: "11px"
    fontWeight: 600
  note-title:
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.4
  note-body:
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.75
  task-title:
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
rounded:
  badge: "4px"
  compact: "6px"
  control: "8px"
  compact-action: "7px"
  node: "9px"
  conversation: "12px"
  folder: "16px"
  note: "3px 3px 20px 3px"
spacing:
  small: "8px"
  medium: "12px"
  regular: "16px"
  section: "22px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#34435a"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "#34435a"
    rounded: "{rounded.compact}"
    padding: "9px 8px"
  notebook-selected:
    backgroundColor: "{colors.navigation-selected}"
    textColor: "{colors.sidebar-active-ink}"
    rounded: "{rounded.compact}"
    padding: "7px 8px"
  verdict-approved:
    backgroundColor: "#eaf4ee"
    textColor: "#246a4f"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  graph-node:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.node}"
  project-folder:
    backgroundColor: "linear-gradient(145deg,#e4e8ef,#eff2f7)"
    textColor: "{colors.text}"
    rounded: "{rounded.folder}"
    height: "245px"
  project-field:
    backgroundColor: "{colors.surface}"
    textColor: "#34435a"
    rounded: "{rounded.compact}"
    padding: "11px 10px"
  postit-yellow:
    backgroundColor: "{colors.note-yellow-paper}"
    textColor: "{colors.note-yellow-ink}"
    rounded: "{rounded.note}"
    padding: "16px 20px 12px"
  postit-pink:
    backgroundColor: "{colors.note-pink-paper}"
    textColor: "{colors.note-pink-ink}"
    rounded: "{rounded.note}"
    padding: "16px 20px 12px"
  postit-blue:
    backgroundColor: "{colors.note-blue-paper}"
    textColor: "{colors.note-blue-ink}"
    rounded: "{rounded.note}"
    padding: "16px 20px 12px"
  postit-green:
    backgroundColor: "{colors.note-green-paper}"
    textColor: "{colors.note-green-ink}"
    rounded: "{rounded.note}"
    padding: "16px 20px 12px"
  postit-purple:
    backgroundColor: "{colors.note-purple-paper}"
    textColor: "{colors.note-purple-ink}"
    rounded: "{rounded.note}"
    padding: "16px 20px 12px"
  postit-orange:
    backgroundColor: "{colors.note-orange-paper}"
    textColor: "{colors.note-orange-ink}"
    rounded: "{rounded.note}"
    padding: "16px 20px 12px"
  note-editor-field:
    backgroundColor: "#ffffffb8"
    textColor: "{colors.text}"
    rounded: "{rounded.compact}"
    padding: "10px"
  flow-disclosure:
    backgroundColor: "transparent"
    textColor: "#40536f"
    rounded: "7px"
    height: "40px"
  calendar-day:
    backgroundColor: "transparent"
    textColor: "#34435a"
    height: "44px"
  calendar-day-today:
    backgroundColor: "{colors.calendar-today-paper}"
    textColor: "#563815"
    size: "34px"
  calendar-day-selected:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    size: "34px"
  task-filter-selected:
    backgroundColor: "#edf2fc"
    textColor: "{colors.accent}"
    rounded: "{rounded.compact-action}"
    padding: "7px 13px"
  task-deadline-overdue:
    backgroundColor: "#fce8e8"
    textColor: "#96313e"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  task-deadline-soon:
    backgroundColor: "#fff0d9"
    textColor: "#825019"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  task-deadline-near:
    backgroundColor: "#eaf0ff"
    textColor: "#34539a"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  task-deadline-later:
    backgroundColor: "#eef4ee"
    textColor: "#406849"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  task-priority-high:
    backgroundColor: "#fae9ed"
    textColor: "#94374c"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  task-priority-medium:
    backgroundColor: "#fbefdc"
    textColor: "#7e5523"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
  task-priority-low:
    backgroundColor: "#eaf2e8"
    textColor: "#486d3d"
    rounded: "{rounded.badge}"
    padding: "3px 7px"
---

# Design System: Hilo

## Overview

**Creative North Star: "El cuaderno de evidencia local"**

Nombre descriptivo derivado del artefacto implementado, sin atribuir una elección de marca al usuario. La interfaz utiliza superficies claras, azul funcional, texto de sistema y diagramas precisos para conversar y observar verificaciones metodológicas. Su densidad responde a una herramienta operativa de evaluación local.

El sistema permite contextualizar el proyecto antes de conversar, leer mensajes extensos y consultar estados, memoria y fuentes mediante jerarquía tipográfica y separadores discretos. El contexto declarado conserva una identidad visual separada de la evidencia verificada. La distribución actual expresa la primera superficie de prueba; las decisiones reutilizables son la claridad del contenido, los estados explícitos y la contención visual de los controles.

Las anotaciones personales añaden papel de color a este cuaderno operativo. Su pila conserva la lectura vertical y el editor toma el color del papel elegido; la evidencia metodológica y el contexto declarado mantienen sus propios tratamientos. El pliegue y la sombra pertenecen a la nota, como los papeles superpuestos pertenecen a la carpeta.

**Key Characteristics:**

- Superficies claras con separación tonal y bordes finos.
- Azul para acción, selección y ejecución.
- Tipografía de sistema en cuerpo y controles.
- Estados descritos con texto además del color.
- Papel de color para anotaciones personales, con tinta oscura y pliegue pequeño.

## Colors

La paleta combina un azul sobrio con neutros fríos y colores semánticos de estado; los valores del frontmatter constituyen los tokens reutilizables.

### Primary

- **Azul de acción:** enviar, crear, seleccionar cuaderno y señalar ejecución; el tono más profundo resuelve hover de acciones principales.

En Inicio y en la vista previa, las carpetas ofrecen seis paletas personales: azul, amarillo, verde, naranja, morado y gris. Cada selección combina fondo, frente en gradación y tonos de texto propios; los valores quedan encapsulados en el componente mediante data-color. El color pertenece al cuaderno y no representa progreso, veredicto ni última apertura. «Último abierto» es una etiqueta independiente de la paleta, procedente del proyecto recordado localmente.

### Secondary

- **Papeles personales:** amarillo, rosa, azul, verde, morado y naranja. Cada papel se empareja con tinta oscura y un tono de pliegue; los dieciocho tokens note del frontmatter conservan los valores reales del componente. El editor y la tarjeta comparten esta paleta. La categoría se escribe con texto y puede combinarse con cualquier papel.

**The Papel personal Rule.** El color de una nota expresa preferencia personal; no indica aprobación, progreso ni categoría metodológica.

### Neutral

- **Texto tinta:** base de lectura; **texto secundario** y **texto de evidencia** distinguen contexto y metadatos.
- **Superficie blanca:** conversación, campos y selección activa.
- **Fondo frío**, **navegación azul** e **inspector blanco:** separan áreas sin decoración pesada. La superficie de proyecto utiliza workspace-background y workspace-border.
- **Línea suave:** límites de panel y divisores internos.

El verde señala conexión disponible o finalización y el rojo señala error, rechazo o eliminación. Los veredictos y nodos añaden fondos semánticos específicos; no constituyen acentos de marca adicionales.

En el calendario, el papel ámbar distingue hoy y el azul de acción distingue la fecha elegida; si
coinciden, la selección azul prevalece. Los puntos ámbar representan tareas y los azules apagados
representan conversaciones, con una leyenda estable. En la lista, plazo e importancia usan dos
familias de etiquetas independientes: el plazo pasa por rojo, ámbar, azul y verde según cercanía;
la importancia usa rosa, ámbar y verde. Las variantes de estas etiquetas pertenecen a la agenda,
sin convertirlas en una nueva paleta de marca.

**The Dos lecturas de tarea Rule.** Mostrar plazo junto a fecha y hora, e importancia con su propia etiqueta; ningún color sustituye esos datos ni confunde ambas funciones.

**The Estado explícito Rule.** Acompañar cada color de estado con una etiqueta, descripción o leyenda legible.

## Typography

**Body Font:** Segoe UI con alternativas de sistema. **Control Font:** la misma familia. No se define una familia display reutilizable.

La jerarquía es compacta y funcional. El cuerpo usa la base del frontmatter; la conversación amplía el interlineado para respuestas metodológicas. Títulos de panel y nombres de nodo utilizan el rol title; nombres de cuaderno y botones utilizan control; etiquetas y cabeceras de memoria utilizan label. Las notas usan note-title para títulos seminegrita y note-body para texto con saltos de línea conservados; en móvil estrecho el cuerpo aumenta (14px). El título del editor usa una jerarquía local (22px, 600), que se compacta (20px) bajo (460px). La memoria emplea cuerpo compacto (12px) y los metadatos secundarios se mantienen subordinados a la lectura principal.

**The Lectura antes de ornamento Rule.** Mantener el texto metodológico como contenido principal y usar peso seminegrita para identificar controles y secciones.

## Layout

La agenda de Inicio sigue a las carpetas y precede a Herramientas. Comparte ancho máximo de Inicio
y separador fino: calendario a la izquierda y tareas a la derecha, columnas flexibles con mínimo
de calendario (290px), gap (44px) y padding de tareas (34px). Bajo (1150px), el mínimo pasa a (260px),
gap y padding a (24px). Hasta (900px), se apila con gap (30px), calendario de hasta (420px) y
separador horizontal sobre tareas. Es una composición local de Inicio, sin imponer esta cuadrícula
a otras superficies.

Inicio comparte la navegación superior con las demás vistas; la cabecera de proyecto se oculta en Inicio. Conserva búsqueda por nombre y orden por actualización o nombre. Las medidas vigentes de biblioteca están descritas en «Inicio amplio»; no sustituyen la distribución de conversación descrita a continuación.

El diálogo de creación y edición tiene ancho máximo (920px), margen lateral mínimo (16px) y altura limitada a la ventana. En escritorio distribuye campos a la izquierda y vista previa con selector de color a la derecha (250px), separados por (32px). La zona central desplaza su contenido y deja las acciones visibles al pie. Bajo (700px), el margen lateral es (12px), el padding (22px) y el selector aparece primero en dos columnas, con etiquetas (12px); siguen los campos desplazables y la vista previa. Esta composición describe el formulario vigente y no establece una cuadrícula global.

La superficie de proyecto ocupa la altura de la ventana bajo una navegación superior (56px) con el título y la etapa dentro de la cabecera del chat, de mínimo (72px). Sobre fondo frío (#edf2fb), conversación e inspector son dos rectángulos blancos con borde (1px, #d8e1f0) y radio (12px). La cuadrícula usa centro flexible más inspector `clamp(290px, 25vw, 360px)`, separación (20px) y padding exterior (16px 24px 72px). Mensajes e inspector desplazan independientemente; el compositor permanece dentro del rectángulo del chat, al pie.

Los espacios reutilizables del frontmatter articulan controles y agrupaciones. Entre (701px) y (1050px), el inspector mide (285px), la separación (14px) y el padding exterior (14px 16px 72px); la navegación compacta sus controles. Hasta (700px), la navegación superior es adhesiva y mide (52px), abre un menú desplegable debajo y el inspector se apila bajo el chat. El chat mide `calc(100dvh - 144px)` con mínimo (480px), y el inspector tiene altura automática con mínimo (260px); la página desplaza para alcanzar las notas. Bajo (460px) se compacta el editor de notas. Son reglas locales del espacio de proyecto, no una cuadrícula obligatoria para otras superficies.

La pila de notas del proyecto mantiene separación (14px), sin distribución en mosaico. El inspector es el rectángulo menor contiguo al chat; hasta (700px) se apila debajo con separación exterior (16px). El editor de notas limita ancho (510px) y alto a la ventana con margen (28px); el área de campos desplaza con margen interior para foco (6px), mientras título, descripción y acciones permanecen fuera de ese desplazamiento. Bajo (460px), el padding del diálogo pasa de (28px) a (20px) y los radios de color pasan de tres a dos columnas. El flujo se consulta desde el menú de acciones del proyecto.

## Elevation & Depth

La profundidad proviene de superficies tonales y bordes de un píxel. En la navegación superior, selección y hover usan blanco translúcido sin sombra; el compositor enfocado añade un halo azul. El menú despliega un panel azul debajo del botón sin oscurecer la página. Los valores completos se conservan en el sidecar.

**The Profundidad funcional Rule.** Usar sombra o halo para selección y foco; mantener planos los paneles de lectura.

Las carpetas de Inicio son una excepción local: la referencia del usuario se expresa mediante papeles superpuestos, sombra interior y gradaciones de material. Hover eleva la carpeta (4px) con sombra suave y el estado presionado reduce la elevación (1px). El diálogo de creación usa sombra ambiental y fondo oscurecido para separar una tarea modal. Estos recursos no cambian el carácter plano de los paneles de lectura; el sidecar conserva sus valores y la reducción de movimiento vigente.

La nota también tiene material propio: una sombra suave (`2px 6px 9px #26334816`) separa cada papel de la pila y un pliegue tonal marca su esquina. Es una excepción local a los paneles de lectura planos, sin texturas. El editor de notas usa sombra ambiental (`0 18px 55px #17284440`) y fondo oscurecido; no añade movimiento propio.

## Shapes

Los controles y campos usan esquinas suavemente redondeadas; los turnos y el compositor usan la curva más amplia. Nodos y selección de cuaderno comparten una curva intermedia. Los puntos circulares identifican estados y extremos del grafo; los conectores distinguen rutas condicionales mediante línea discontinua. Los iconos son SVG de trazo con extremos redondeados.

La carpeta de Inicio añade una curva propia, papeles de esquinas intermedias y frente recortado con pestaña inclinada. El recorte y los papeles son la firma de este componente, derivada de la referencia, y no una obligación para cada contenedor.

La nota añade una silueta casi rectangular del rol note, con curva mayor solo en la esquina inferior derecha. El triángulo tonal del pliegue mide (19px) y no recibe interacción. El editor mantiene la curva conversation y los campos la curva compact.

## Components

### Buttons

Acciones compactas con texto seminegrita, altura mínima (40px) y separación clara. La acción principal utiliza azul; la secundaria, blanco y borde; la discreta, fondo transparente y texto secundario. El envío es un botón SVG cuadrado (36px). El foco visible utiliza contorno azul (2px), separado (3px). Los botones deshabilitados reducen opacidad y cambian el cursor.

### Inputs / Fields

Los campos de cuaderno usan blanco, borde fino y esquinas compactas. El compositor del chat empieza en una línea dentro de una cápsula blanca; al recibir foco muestra un contorno azul. La entrada crece con el texto hasta una altura limitada y ofrece un control para ampliar la lectura. La acción de envío permanece dentro de un botón circular contiguo.

La zona desplazable del formulario reserva (6px) alrededor de sus controles para mostrar completo
el contorno de foco. Los errores obligatorios aparecen debajo del campo, con texto rojo y
aria-invalid; al corregir el valor desaparecen. La validación enfoca el primer campo incompleto
y conserva los datos escritos, sin avisos flotantes que cubran otros controles.

El diálogo «Nuevo cuaderno» reutiliza estos campos con entrada (14px), etiqueta (12px) y padding del componente project-field; las áreas multilineales usan cuerpo (13px) e interlineado (1.7). Nombre y reto son obligatorios al crear; entorno y objetivo son opcionales. «Más detalles» agrupa hipótesis o supuestos, criterio de aceptación, ambición 10X y etapa inicial. Las hipótesis se presentan como explicaciones por contrastar, sin apariencia de resultado confirmado. La vista previa actualiza nombre, etapa y color. El mismo diálogo se abre desde «Editar cuaderno» en el menú flotante del proyecto y permite completar contexto y cambiar color. Mantiene padding de escritorio (28px), esquinas del rol conversation y acciones alineadas al final, fuera del área desplazable. El error usa texto rojo y role=alert; Escape y Cancelar cierran la tarea modal.

### Navigation

Los cuadernos recientes se presentan como filas de icono y nombre, sin vista previa, dentro de «Recientes». Hover y selección aportan blanco translúcido sobre azul, sin sombra; los nombres largos se recortan con elipsis y conservan tooltip. El estado activo utiliza también aria-current; la navegación se abre con botón en todos los tamaños y se cierra al pulsar fuera, navegar o presionar Escape.

Inicio es una acción de navegación superior compartida con icono SVG y texto; el estado actual usa blanco translúcido sobre azul y aria-current. Abrir una carpeta muestra su conversación, grafo y memoria; volver a Inicio restaura la biblioteca. La selección de navegación y la etiqueta «Último abierto» describen estados distintos. La cabecera dentro del chat muestra nombre y etapa. La barra azul flota centrada al pie sobre los paneles, con Inicio, Agentes y Editar cuaderno siempre visibles. En el inspector, «Contexto del proyecto / Declarado por ti» es un bloque desplegable separado del recorrido y de la memoria verificada; no atribuir a los supuestos declarados el tratamiento de veredicto.

### Menú

Barra superior horizontal azul (#2a55bc), altura (56px) en escritorio y (52px) en móvil. A la izquierda aparece un único botón cuadrado con icono de cuadrícula, sin texto visible, seguido del icono y nombre Hilo; solo el avatar de cuenta, ayuda y campanita permanecen a la derecha. Inicio, Proyectos, Fichas metodológicas y Recientes están ocultos hasta pulsar el botón.

El panel se despliega debajo del botón, mide hasta (320px), tiene radio (12px), filas de al menos (44px), y puede desplazarse cuando la ventana es baja. No oscurece la página. Recientes despliega su lista dentro del mismo panel. Selección (#ffffff26), hover (#ffffff16), foco blanco y aria-current. El botón mantiene aria-expanded y aria-controls; Escape cierra el panel y devuelve el foco al botón. También se cierra al pulsar fuera o navegar. Especificación: [.impeccable/surfaces/chat-workspace.md](.impeccable/surfaces/chat-workspace.md).

### Bandeja de Notificaciones

La campanita abre una bandeja blanca de hasta (390px) con cabecera, resumen y total. Ordena las entradas pendientes en **Vencidas**, **Para hoy** y **Próximos días**; cada fila conserva icono de tipo, título, fecha u hora y proyecto. Los chips siempre combinan texto y color: «Vencida» en rojo, «Hoy» en ámbar y «Próxima» en azul. El badge rojo de la campana —y el contador junto a Calendario— suma solo vencidas y lo que queda de hoy; los próximos tres días aparecen en la bandeja, pero no elevan ese badge.

Cada grupo muestra hasta seis entradas. Si hay más, una línea indica cuántos avisos quedan en el calendario; pulsar una entrada abre su fecha y «Ver calendario completo» ofrece la salida estable al calendario. Sin avisos, la lista se reemplaza por el estado calmado «Todo está en orden». La campanita y los cierres conservan objetivos de (44×44px); en móvil la bandeja se ajusta al ancho y alto disponibles. Especificación: [.impeccable/surfaces/notifications.md](.impeccable/surfaces/notifications.md).

**The Atención real Rule.** El badge representa únicamente vencidas y pendientes de hoy; no usar los próximos días para inflar urgencia.

### Toasts

Los avisos transitorios comparten icono, título, texto explicativo y cierre de (44×44px). Información usa azul, éxito verde, advertencia ámbar y error rojo; el color nunca sustituye el contenido. Se apilan hasta tres en la esquina superior derecha y, en móvil, pasan al borde inferior. Información, éxito y advertencia se cierran a los (4.8s); error permanece (7s). Hover o foco pausa el temporizador, y abrir la campanita retira los toasts para evitar dos capas de avisos simultáneas. La entrada y salida se anulan con `prefers-reduced-motion`.

### Bloques de Inicio

Debajo de la biblioteca de proyectos, Inicio continúa con dos bloques separados por una línea fina
y sin caja propia: la elevación ya la aportan las carpetas, y encerrar estas secciones en tarjetas
duplicaría la jerarquía.

«Herramientas» destaca cuatro fichas en recuadros de color con esquinas de 22px y sin borde, porque
el tono ya separa cada pieza del fondo. El criterio de selección es verificable —son las únicas
fichas que alimentan la memoria verificada— y nunca «las más usadas»: el prototipo no registra uso.

El recuadro tiene dos momentos. En reposo los cuatro caben en una sola línea (214×245px en
escritorio), con el título arriba a la izquierda y la imagen centrada ocupando el resto de la altura:
la imagen es el elemento dominante, no un icono de apoyo. Al apuntarlo o enfocarlo con teclado se
ensancha a rectángulo y la nota se abre a su derecha; como la fila centra el par imagen-nota, la
imagen se desplaza hacia la izquierda por sí misma.

La imagen se ancla a los cuatro lados de su área y se encaja con object-fit. Un alto en porcentaje no
sirve aquí: el área la centra en lugar de estirarla, el porcentaje queda sin base definida y la
imagen desborda el recuadro.

El ancho que gana el recuadro apuntado es exactamente el que ceden los demás, de modo que la suma de
la fila no cambia y ningún recuadro salta de línea al expandirse: ese salto es el error a evitar
cuando se toque esta regla. La imagen cede ancho en lugar de recortarse. El texto de la nota tiene ancho propio dentro de una caja que se abre,
para que no se reacomode línea a línea durante la animación, y siempre está en el DOM: la nota se
oculta a la vista, no a los lectores de pantalla.

La descripción no se escribe en el frontend: se lee de la sección «Qué es» de la ficha real. Si la
ficha cambia, el recuadro cambia con ella; si la ficha no carga, el recuadro se queda sin nota en
lugar de inventar una.

Por debajo de 1100px, o sin puntero fino, no hay ancho que repartir ni hover que esperar: cada
recuadro ocupa la fila completa y muestra su nota desde el principio. Las marcas sin fotografía son
geometría vectorial que describe su método —cinco nodos descendentes para los porqués, hexágono de
seis sectores para PESTEL, cuadrantes para el mapa de empatía—, con volumen por degradado y sombra
de apoyo. Un tag «Ver más» lleva a la biblioteca completa, y abrir un recuadro usa el mismo diálogo
de ficha.

«Calendario» muestra el mes en curso con la semana iniciando en lunes. Todos los días son
pulsables para consultar sus tareas, incluso cuando están vacíos. Hoy usa un círculo verde suave sobre violeta y el
día elegido, relleno blanco. Los puntos cálidos indican tareas guardadas; los azules, conversaciones
reales de los cuadernos. El pie resume esa actividad y la lista contigua muestra las tareas de la
fecha elegida. Hilo guarda fechas propias en su agenda personal, independiente del historial y
de la memoria metodológica verificada. Ver «Agenda de Inicio» para creación, prioridad y plazos.

### Perfil

Ocupa el inicio de la navegación superior. Combina avatar con iniciales, nombre truncado y acceso
al diálogo de perfil; un punto de color en la esquina del avatar muestra el estado real del modelo.
No hay bloque inferior de marca ni botón de recarga en la navegación. El nombre es una preferencia
local del navegador, editable en su propio diálogo: Hilo no tiene cuentas ni envía ese dato a
ninguna parte, y el diálogo lo declara. El estado del modelo nunca se presenta como decoración:
es la explicación de por qué el envío puede estar bloqueado.

### Fichas metodológicas

Biblioteca de consulta de las fuentes que el asistente puede citar. Cada ficha es una tarjeta con
borde de 1px y sin sombra —la elevación se declara una sola vez— que muestra nombre, metodología,
las etapas de la ruta donde está habilitada y si aporta campos verificables. Los datos provienen de
la ruta cargada; una ficha sin etapa se rotula como tal en lugar de ocultarse. Al abrirla, el
contenido real de la ficha se muestra en diálogo desplazable. Esta vista es consulta: no inicia
conversación ni altera la memoria de ningún cuaderno.

### Chips

Los veredictos combinan texto seminegrita, fondos semánticos tenues y esquinas pequeñas. Son etiquetas informativas; aprobación, observación y rechazo se expresan mediante texto y color.

### Cards / Containers

Las áreas principales son paneles planos separados por tono y borde.

### Conversación con Hilo

El chat conserva el azul de marca #294eb8 y papel blanco dentro de los paneles sobre workspace-background.
Los mensajes del usuario se alinean a la derecha en burbujas azules con texto blanco;
las respuestas se alinean a la izquierda sobre fondo tenue #f7f9fd con borde fino #e1e6ef.
Esquinas de 16px y esquina superior del lado de origen de 6px distinguen los interlocutores.
Cada encabezado agrupa avatar circular, Tú/Hilo y hora local si existe created_at válido.
Hilo usa su marca en blanco; el usuario usa las iniciales de su perfil local.
Las respuestas conservan Markdown saneado, observaciones, veredicto, ficha y acciones de
post-it/copiar. El pie agrupa acciones bajo un separador fino; los colores semánticos del
veredicto se conservan. Código y tablas admiten desplazamiento horizontal dentro del contenido.
Dentro del rectángulo del chat, la cabecera de mínimo (72px) muestra el título y la etapa.
El título ocupa hasta dos líneas y conserva el nombre completo como tooltip y texto accesible.
La barra de opciones flota sobre los paneles en el centro inferior de la ventana. «Inicio» permite cambiar de proyecto desde móvil.
El compositor blanco mide hasta 820px. Vacío o con texto breve es una cápsula compacta de esquinas
completamente redondas; con varias líneas adopta esquinas amplias y crece hasta 154px de texto.
Cuando supera ese límite aparece un botón en la esquina superior para ampliar la zona de escritura
hasta 520px o el 58% de la pantalla, lo que sea menor. El texto se desplaza dentro del campo al
alcanzar cada límite; el botón de enviar es circular, de 36px, y queda abajo a la derecha.
Estado del modelo, foco azul y ayuda de teclado siguen visibles.
En móvil se reducen márgenes, el texto queda en 13px y el inspector se mantiene debajo.
La bienvenida conserva su texto y sugerencias, presentadas como botones blancos de borde fino.

### Recorrido de agentes

El grafo SVG emplea nodos rectangulares redondeados, título y estado, conectores finos y rutas condicionales discontinuas. Ejecución, finalización y fallo cambian relleno, trazo y texto. La lista desplegable de eventos aporta el detalle temporal; los datos de ejecución proceden del flujo real del backend.

### Carpeta de proyecto

Objeto navegable con tres papeles superpuestos y frente con pestaña; toda la carpeta es un botón con nombre accesible para abrir el proyecto. El título ocupa hasta dos líneas; etapa y número de mensajes provienen de los datos guardados. En la esquina inferior derecha, donde antes aparecía la fecha, los perfiles del proyecto se muestran como círculos de iniciales cuando hay otra persona invitada: propietario, integrantes aceptados e invitaciones pendientes visibles para el propietario. La invitación pendiente usa borde discontinuo y se nombra como pendiente en el texto accesible; no se presenta como acceso concedido. Si solo está el propietario, no se muestra el grupo. Para más de tres perfiles, un círculo `+N` resume el resto. La carpeta conserva la paleta personal al mostrar la etiqueta «Último abierto». Hover, pulsación y foco visible acompañan la apertura; durante carga o ejecución se bloquea la navegación. La biblioteca distingue carga, proyectos disponibles, primera creación y búsqueda sin resultados mediante texto y contador, y muestra la acción de primera creación solo cuando aún no existen proyectos.

### Selector de color

Seis opciones de radio nativas, cada una con nombre visible y muestra cuadrada del tono de frente. La selección combina radio marcado, borde azul y fondo tenue; el azul del control indica selección, mientras la muestra representa la preferencia personal. Las etiquetas mantienen cuerpo (12px), altura mínima (42px) y foco visible. El selector usa dos columnas tanto en escritorio como en móvil.

### Post-its del cuaderno

Papel personal y lectura vertical. Cada nota presenta categoría, título, texto y fecha, con tokens de papel/tinta/pliegue, padding del componente postit y profundidad descrita arriba. El texto conserva saltos de línea y permite palabras largas sin desbordar. Nueva nota y Guardar selección del chat preceden la pila; el pie de respuesta incluye Guardar en post-it para su texto completo. El contador distingue la cantidad de notas; el estado vacío explica cómo crear la primera.

Editar y eliminar usan botones SVG (32px) con nombre accesible que incluye el título; hover aporta blanco translúcido y el foco conserva el contorno azul compartido. El origen aparece en «Guardado del chat» como desplegable de lectura; su cita tiene altura limitada (180px) y desplazamiento. Editar conserva ese fragmento original. Eliminar abre confirmación dentro de la nota, con Eliminar y Cancelar.

El editor modal refleja inmediatamente el color elegido. Título y texto son obligatorios; categoría usa selector nativo y los seis colores radios con nombre visible. Selección combina radio marcado, borde azul y fondo blanco. La validación conserva la entrada, muestra error en línea con role=alert y aria-invalid, y enfoca el primer campo vacío; al corregirlo se retira el estado de error. Durante el guardado los campos y acciones se deshabilitan. Cancelar y Escape cierran cuando no hay guardado pendiente; al guardar se enfoca la acción de edición de la nota creada o actualizada.

El grafo queda cerrado por defecto en Ver flujo de agentes. Su acceso Agentes en la barra flotante refleja aria-expanded y permite cerrar el grafo; la barra permanece alcanzable cuando la pila crece y conserva el nombre de cada acción en móvil. Contexto declarado y memoria verificada también parten colapsados. Las notas son anotaciones personales persistentes por cuaderno en SQLite; su tratamiento visual no implica verificación ni incorporación al contexto del modelo.

En Inicio, los títulos se agrupan con su contenido: encabezado a controles 16px (14px móvil),
contador a carpetas 12px (10px móvil) y retícula de proyectos con gap 20px (16px móvil).
Las secciones usan margen superior 24px y padding superior 18px; en móvil 22px/16px.
Las descripciones de herramientas tienen 5px arriba y 10px abajo. Calendario y agenda
usan 24px de separación superior, 20px de padding y gap 28px, reducido en pantallas estrechas.
Estas reglas están limitadas a `.home-view`; el chat y la biblioteca conservan su espaciado.

Inicio usa el ancho disponible sin el límite anterior de 1090px. Los márgenes laterales
varían entre 28px y 76px (20px en móvil). Desde 1280px, los proyectos se distribuyen en cuatro
columnas y las herramientas aprovechan el mismo ancho. Calendario y agenda se reparten
aproximadamente 47.5% y 52.5% del espacio, con calendario mínimo de 440px. En escritorio
las fechas tienen celdas de 52px, círculos de 38px y texto de 14px; en móvil ambos se apilan.

### Agenda de Inicio

Después de Herramientas, calendario lavanda a la izquierda y lista de tareas a la derecha.
El calendario conserva papel lavanda #ece8f8. La agenda usa un panel blanco, filas compactas
#f5f4f8 de esquinas 12px e iconos circulares violetas. La casilla nativa está cubierta por el
icono, con nombre accesible, foco visible y acción completar/reabrir. El título y fecha quedan
a la izquierda; prioridad y estado se alinean a la derecha en escritorio y debajo en móvil.
Estado: Pendiente amarillo, Completada verde, Vencida rojo; sin puntajes o progreso inventado.
Los filtros conservan selección violeta y el formulario usa superficie neutra suave.
El bloque del calendario usa retícula violeta #6f6199 y tinta blanca;
la actividad se resume en una superficie blanca inferior, según la referencia del usuario.
Todas las fechas permiten consultar tareas, incluso vacías; la semana empieza en lunes y el mes
usa formato español local. Las celdas tienen altura (42px; 40px en móvil estrecho), número en círculo (32px) y puntos
(5px). Hoy usa verde suave #d9ee9b; selección blanca con aria-pressed; la leyenda y el nombre accesible de
cada fecha explican tareas y conversaciones. Los puntos de tareas son cálidos (#ffd08a dentro de la retícula), aunque sus
plazos cambien de tono en la lista. La retícula conserva suficiente contraste para cifras y foco.

Las tareas tienen control circular (36px) con checkbox nativo, título seminegrita (14px; 13px móvil), fecha/hora local
y dos etiquetas pequeñas de esquinas badge. Plazo vencido es rojo, hasta (24h) ámbar, hasta (72h)
azul y posterior verde; «Completada» aparece en la etiqueta verde derecha; su título no se tacha. La importancia
alta es rosa, media ámbar y baja verde, siempre rotulada «Prioridad». La fecha/hora absoluta
permanece junto al plazo. Proyecto opcional aparece como texto. El botón SVG de edición (26px de ancho)
y el checkbox incluyen el título en su nombre accesible.

Hoy, Próximas y Todas son botones con aria-pressed, superficie azul tenue para selección y
esquinas compact-action. Elegir fecha consulta ese día; Próximas reúne pendientes, incluidas
vencidas. La lista coloca pendientes antes de completadas, ordena por fecha/hora y desempata por
importancia. Los estados de carga, error, reintento y vacío se escriben con texto procedente de
los datos reales.

Nueva tarea y Editar tarea abren el mismo formulario en línea bajo la lista. El formulario
reutiliza campos blancos de esquinas compactas, labels (11px) y filas de dos campos para fecha/hora
y prioridad/proyecto; reserva margen interior (6px) para foco. Título, fecha y hora son obligatorios;
el error aparece con role=alert y el primer control incompleto recibe foco. Los controles se
deshabilitan durante guardado; cancelar o guardar devuelve foco a Nueva tarea. El refresco de
plazos espera mientras un control de la agenda tiene foco. Las tareas persisten en SQLite,
separadas de conversación, contexto del modelo y memoria verificada.

## Do's and Don'ts

### Do:

- **Do** conservar la familia de sistema en cuerpo y controles.
- **Do** acompañar los colores de estado con texto y mantener el foco visible.
- **Do** resolver jerarquía con espaciado, peso, tono y bordes finos.
- **Do** respetar prefers-reduced-motion en transiciones e indicadores.
- **Do** emparejar cada papel de nota con su tinta oscura y conservar categoría y origen como texto legible.
- **Do** mantener la pila vertical y reservar margen interior para mostrar completo el foco en los editores.
- **Do** mantener texto e icono junto al color de avisos, y objetivos de al menos (44×44px) en campana y cierres.

### Don't:

- **Don't** tratar los colores de error y finalización como decoración de marca.
- **Don't** convertir medidas particulares de la primera pantalla en requisitos para todas las superficies.
- **Don't** representar progreso o evidencia sin datos de ejecución que los respalden.
- **Don't** usar el color del papel como veredicto ni presentar una anotación personal como memoria verificada.

### Accesos de cuenta en la cabecera

La zona derecha muestra únicamente el avatar de iniciales de la cuenta, Ayuda y la campanita de Notificaciones, en ese orden. El avatar abre el menú de cuenta; Perfil abre el editor existente. Se conserva el nombre accesible de la cuenta. Ayuda despliega una guía breve; Notificaciones abre la bandeja real de la agenda descrita arriba. Los avisos permanecen dentro de Hilo: no hay notificaciones del sistema operativo ni correos. Los paneles cierran al pulsar fuera o con Escape. Buscar proyectos y Nuevo proyecto permanecen dentro del menú principal. Verificado en escritorio y móvil con almacenamiento de prueba aislado, sin desbordamiento horizontal y sin guardar cambios de perfil.

### Menú desplegable de cuenta

El avatar abre un panel azul de Hilo con avatar ampliado, nombre real y @usuario local. Acciones: Perfil, Configuración de la cuenta, Tema, guía de inicio rápido, Cambiar de cuenta y Finalizar la sesión. El tema oscuro está pendiente; cambiar de cuenta cierra la sesión y vuelve al acceso. Geometría, estados y límites funcionales en [.impeccable/surfaces/account-menu.md](.impeccable/surfaces/account-menu.md).
