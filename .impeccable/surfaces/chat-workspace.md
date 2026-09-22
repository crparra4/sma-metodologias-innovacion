# Espacio de proyecto de Hilo

Actualizado el 18 de septiembre de 2026. Modo: Operate. Sustituye la composición lateral de sidebar.md y las reglas anteriores de distribución del proyecto. Documento extraído de `prototipo/frontend/index.html`, el bloque final «Espacio de proyecto» de `src/style.css` y la navegación de `src/main.ts`.

La referencia Trello proporcionada por el usuario se expresa en una navegación superior y dos rectángulos: conversación grande y Post-its menor. Se conserva el azul de Hilo. No se adopta la paleta de la referencia.

## Layout

- Barra superior horizontal de 56px, fondo plano #2a55bc, padding 0 24px, esquinas rectas y sin sombra. Botón cuadrado con icono de cuadrícula, sin texto visible, seguido del icono y nombre Hilo a la izquierda; avatar de cuenta, ayuda y campanita a la derecha. Inicio, Proyectos, Fichas metodológicas y Recientes quedan encerrados en un panel desplegable, oculto por defecto en todos los tamaños. Los grupos conservan rótulos accesibles ocultos visualmente.
- El nombre y la etapa están en la cabecera del chat, de mínimo 72px; ya no hay franja de proyecto independiente. El título admite hasta dos líneas. La barra del proyecto flota sobre los paneles en el centro inferior de la ventana; se oculta en Inicio. Opciones visibles: Inicio, Agentes y Editar cuaderno.
- Fondo #edf2fb. Cuadrícula `minmax(0,1fr) clamp(290px,25vw,360px)`, gap 20px y padding 16px 24px 24px. Ambos paneles son blancos, borde 1px #d8e1f0 y radio 12px.
- Chat en columna con cabecera de título y etapa de mínimo 72px, mensajes desplazables y compositor dentro del panel al pie. Inspector desplazable independientemente, padding 22px 20px y pila de notas con gap 14px. Contexto, memoria y flujo siguen siendo consultas secundarias.
- Entre 701px y 1050px: inspector 285px, gap 14px y padding 14px 16px 24px; navegación compacta, perfil 130px e iconos de sus enlaces ocultos.
- Hasta 700px: barra adhesiva de 52px y menú desplegable debajo, máximo 65dvh; filas mínimo 40px y fondo de cierre. Cuadrícula en una columna, gap 16px y padding 12px 12px 24px. Chat `calc(100dvh - 96px)` con mínimo 480px; cabecera de título y etapa mínimo 72px. Inspector debajo, altura automática, mínimo 260px, padding 20px y desplazamiento de página para alcanzarlo.

## Components

La selección de navegación usa #ffffff26, hover #ffffff16, texto claro y radio 6px; foco blanco y aria-current. Recientes abre una lista integrada dentro del menú en todos los tamaños. Sus filas muestran icono y nombre truncado sin vista previa. Se cierra al pulsar fuera, al navegar o con Escape. El botón móvil mantiene aria-expanded y alterna Mostrar/Ocultar menú.

Los mensajes de usuario conservan azul y texto blanco; respuestas sobre #f7f9fd. Las notas conservan su papel, categoría y origen. Las anotaciones permanecen personales, separadas de memoria verificada y contexto del modelo. La barra conserva el punto de estado real del modelo en el avatar y la comprobación automática.

## Verification

Compilación TypeScript/Vite correcta. QA reportada por el agente principal en localhost:8791 con cuenta, proyectos, notas y turnos largos sintéticos en almacenamiento aislado; sin modificaciones a datos reales. Escritorio 1280×720: chat 892×624 y Post-its 320×624, ambos desde y=72 hasta y=696. Intermedio 760px: documento de 760px, navegación hasta x=744. Móvil 390×844: menú abre/cierra, borrador multilínea cabe, notas alcanzables debajo y formulario de nota abre/cancela. Sin errores de consola. Se retiró la transición de padding señalada por el detector.

No se envió un mensaje al modelo en esta QA: se comprobaron el campo multilínea, estado de envío y turnos sintéticos existentes. El agente principal inspeccionó capturas inline de escritorio y móvil; la revisión independiente fue de fuente. No hay rutas de capturas guardadas. Servidor y pestaña de QA cerrados. La página real en 8787 fue recargada y mostró el acceso sin pantalla blanca.

### Ajuste del lanzador de navegación

El botón de cuadrícula despliega un panel azul de hasta 320px, radio 12px, separado 8px de la barra y con filas principales de 44px. El panel se adapta al ancho y alto disponibles y desplaza su contenido; no hay capa oscurecida. Escape devuelve el foco al botón. Verificado en escritorio 1280×720 y móvil 390×844, navegación a Fichas, cierre al navegar, cierre con Escape y foco restaurado. Compilación correcta y detector layout sin hallazgos.

### Accesos de cuenta en la cabecera

La zona derecha muestra únicamente el avatar de iniciales de la cuenta, Ayuda y la campanita de Notificaciones, en ese orden. El avatar abre el menú de cuenta; Perfil abre el editor existente. Se conserva el nombre accesible de la cuenta. Ayuda despliega una guía breve; Notificaciones está preparado visualmente y anuncia que estará disponible próximamente. No hay servicio de alertas conectado. Los paneles cierran al pulsar fuera o con Escape. Buscar proyectos y Nuevo proyecto permanecen dentro del menú principal. Verificado en escritorio y móvil con almacenamiento de prueba aislado, sin desbordamiento horizontal y sin guardar cambios de perfil.

### Menú desplegable de cuenta

El avatar abre un panel azul de Hilo con avatar ampliado, nombre real y @usuario local. Acciones: Perfil, Configuración de la cuenta, Tema, guía de inicio rápido, Cambiar de cuenta y Finalizar la sesión. El tema oscuro está pendiente; cambiar de cuenta cierra la sesión y vuelve al acceso. Geometría, estados y límites funcionales en [.impeccable/surfaces/account-menu.md](.impeccable/surfaces/account-menu.md).

### Cabecera del chat y acciones flotantes

La franja superior de proyecto se eliminó. Título y etapa sustituyen a Conversación dentro del panel. La barra azul de opciones visibles está fija a 12px del borde inferior, centrada y superpuesta a los paneles. Barra compacta de 42px de altura, texto 12px, iconos 15px y botones de mínimo 32px: Inicio, Agentes y Editar cuaderno. El compositor conserva 40px de padding inferior para mantener libre el campo. Verificado con datos sintéticos aislados en escritorio 1280×720 y móvil 390×844: opciones visibles, Agentes abre/cierra el flujo, editar abre/cancela, Inicio oculta la barra, sin desbordamiento ni errores de consola. Compilación correcta, detector limpio y referencias de elementos presentes.

### Escritura discreta

El compositor reduce su zona a padding 6px 16px 40px (12px laterales en móvil), sin separador superior. Campo de una línea de 42px, fondo #f7f9fd, borde #e5ebf5 y foco #b4c5e5 sin contorno externo. Texto 13px, botón de envío 30px y separaciones del estado y ayuda de 4px. Los borradores multilínea conservan crecimiento y expansión.

### Progreso de etapas

Círculo de 48px (44px móvil) a la izquierda del título: posición de la etapa actual sobre el total del catálogo, con etiqueta X de N. No representa porcentaje de tareas completadas. Anillo #2a55bc sobre pista #e2eafa. La fase bajo el título usa fondo #edf2fc y texto #244ba8; el nombre de etapa usa #426293. Valor y nombre accesibles; indicador oculto mientras no haya una etapa válida.

### Compartir

Botón al extremo derecho de la cabecera, mínimo 36px, fondo azul claro y texto #244ba8. En móvil muestra solo el icono y conserva nombre accesible. Comparte nombre, fase y etapa con la función nativa disponible; si no existe, copia ese resumen y confirma Copiado. No publica conversaciones, crea enlaces públicos ni concede acceso al cuaderno local.

## Tablero

Actualizado el 18 de septiembre de 2026. El espacio del proyecto funciona como un tablero, con la barra flotante inferior como en la referencia de Trello del usuario. El chat es la base y siempre está visible; por defecto es lo único que aparece. Con una sola herramienta el chat deja de ser tarjeta: ocupa el área completa bajo la barra superior, sin margen, borde, esquinas ni fondo de tablero, y la conversación se centra en una columna de hasta 1120px en escritorio. Las tarjetas, el fondo #edf2fb y los márgenes solo aparecen cuando hay dos o más herramientas que separar. El grupo «Herramientas del tablero», separado por una línea del resto de acciones, enciende y apaga paneles: hoy solo Post-its. Activo, el tablero vuelve a la composición de dos paneles descrita arriba.

Cada botón usa aria-pressed, fondo #ffffff26 y una línea blanca inferior de 2px cuando está activo; su título nombra la herramienta («Agregar Post-its al tablero»). La elección se guarda en el navegador (`hilo-tablero`), es la misma para todos los proyectos y, si el almacenamiento falla, vale para la pestaña actual.

Herramientas actuales: Post-its y Agentes. Una herramienta nueva se registra en `BOARD_TOOLS` de `main.ts`, con su botón `data-board-tool`, su panel y la clase `board-has-<herramienta>`; `data-board-count` en el tablero decide la composición. Con dos herramientas: tres columnas desde 1181px (Post-its algo más ancho, para sostener la pared en dos columnas); entre 701 y 1180px ambas comparten la columna derecha, una encima de la otra; en móvil todo se apila. La regla de tres columnas está acotada a escritorio ancho porque su especificidad le gana a la regla móvil.

## Personas con acceso

Actualizado el 18 de septiembre de 2026. Junto a Compartir, en la cabecera del chat, una lista de círculos de 32px con las iniciales de cada persona con acceso al proyecto, como en la referencia de Trello. Se solapan 7px con un anillo blanco de 2px; a partir de la quinta persona se agrupan en un círculo «+N». La cuenta propia conserva el azul #2a55bc; las demás reciben un tono fijo derivado de su id, elegido de una paleta con contraste AA sobre texto blanco (mínimo 4.92:1). Cada círculo lleva tooltip y texto accesible con nombre, «(tú)» y rol, y la lista anuncia cuántas personas tienen acceso.

Mientras no exista la función de compartir, `projectMembers()` en `main.ts` devuelve solo la cuenta actual como propietaria. Al implementar la membresía descrita en `docs/plan-compartir-proyectos.md`, esa función debe devolver los miembros reales del proyecto con su rol (propietario, puede editar, puede ver); el componente no requiere otros cambios.

## Pared de Post-its

Actualizado el 18 de septiembre de 2026. El panel de Post-its contiene solo post-its. El flujo de agentes y la memoria verificada son el panel Agentes; la ficha de una respuesta se abre en su propio diálogo desde el nombre de la ficha; el contexto se consulta y edita en Editar cuaderno, donde también está Eliminar cuaderno (solo al editar, con confirmación).

Las notas forman una pared en dos columnas (mínimo 128px cada una): papel de su color, esquina doblada, sombra con desplazamiento y una inclinación distinta por posición (−1.2°, 1°, −0.5°, 1.5°) que se endereza al apuntar o enfocar la nota. Arriba: categoría en versalitas con elipsis, marca de «guardado desde el chat» y la fecha corta («18 sept») a la derecha; editar y borrar aparecen sobre la fecha al apuntar, y en táctil quedan visibles bajando a otra línea antes que ocultar la fecha. Título a dos líneas y texto a cuatro; el texto completo está en el editor. Al pie firma el autor: círculo de 20px con sus iniciales y el mismo tono que en Personas con acceso, y su primer nombre; el nombre completo va en el título y en texto accesible. Borrar confirma dentro de la propia nota.

El autor se guarda en cada nota (`author_id`, `author_name`) y sale de la sesión, nunca del cuerpo de la petición. Editar no lo cambia. Las notas previas al campo las reclama la cuenta dueña del almacenamiento al abrir el cuaderno; sin cuenta (pruebas), la nota se muestra como de la cuenta actual. No hay fotos de perfil: el avatar son las iniciales.

## Hoja de post-it

Actualizado el 18 de septiembre de 2026. Crear o editar una nota abre una hoja del propio papel, no un formulario coloreado: se escribe directamente sobre ella. Cinta translúcida arriba, esquina doblada con --note-fold abajo a la derecha y radio mayor en esa esquina. El título es texto grande sin caja, con una línea de tinta solo al enfocarlo; el texto se escribe sobre renglones cada 28px que se desplazan con el contenido (`background-attachment:local`). Las etiquetas visibles «Título» y «Texto» son solo para lectores de pantalla; los ejemplos del campo usan tinta al 84 %, el mínimo que da 4.5:1 en los seis papeles.

La categoría se elige con etiquetas-píldora (radios) y el color con muestras redondas del papel; la elegida lleva anillo de tinta. Elegir un color cambia la hoja al instante, sin transición: al reabrirla se veía un momento el color de la nota anterior. Al pie firma quien escribe (círculo de iniciales, nombre y «ahora» o la fecha de creación al editar) y el botón principal usa la tinta sobre el papel. Validación en línea, foco al primer campo vacío y los mismos identificadores de antes.

