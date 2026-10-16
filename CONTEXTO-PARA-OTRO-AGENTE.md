# Contexto para continuar Hilo / Ruta DIA

Actualizado: 14 de septiembre de 2026. Este documento registra lo implementado y validado; el agente que retome debe comprobar el estado actual de los procesos antes de asumir que siguen activos.

## Objetivo y decisiones del usuario

Trabajo de grado con un asistente metodológico para explorar y desarrollar proyectos mediante Ruta DIA. El usuario eligió desarrollar el prototipo con **LangGraph**, un **modelo local Qwen3.5-4B** y una interfaz rápida en español para conversar y ajustar el diseño. CrewAI se conserva como línea base comparativa. Se discutieron modelos más grandes y una comparación con uno pequeño; no confundir esa conversación con una comparación experimental ya terminada.

El usuario pidió Inicio con todos sus proyectos en carpetas, creación de cuadernos con contexto y color, y luego un panel derecho de **Post-its** personales. El grafo debe quedar oculto por defecto, disponible mediante un botón para demostrar el funcionamiento al profesor.

## Ubicación y ejecución

- Workspace: raíz del repositorio; aplicación en `prototipo/`.
- Aplicación: subcarpeta `prototipo`.
- Plataforma: Windows, PowerShell. Frontend administrado exclusivamente con **pnpm**.
- Interfaz/API: `http://127.0.0.1:8787/`.
- Modelo configurado: `Qwen3.5-4B-Q4_K_M`, servido por llama.cpp en `http://127.0.0.1:18083/v1`.
- Configuración: `prototipo/.env`; no imprimir, copiar ni incluir claves en informes o capturas.
- Memoria por defecto: `%LOCALAPPDATA%\RutaDIA\notebooks.sqlite3` y `checkpoints.sqlite3`, fuera de OneDrive. `RUTA_DIA_DATA_DIR` permite cambiarla; consultar `Settings` si hay dudas.

Desde `prototipo`, iniciar o reutilizar los procesos locales:

```powershell
.\scripts\start_interface.ps1 -NoBrowser
```

El script inicia Qwen si hace falta y reutiliza la interfaz propia si está activa. Construye el frontend si no existe `dist`; después de editar fuentes, construir explícitamente antes de recargar.

```powershell
Set-Location frontend
pnpm run build
Set-Location ..
```

Después de modificar Python, reiniciar la interfaz:

```powershell
.\scripts\stop_interface.ps1
.\scripts\start_interface.ps1 -NoBrowser
```

Para detener también el modelo:

```powershell
.\.venv\Scripts\python.exe scripts/local_model.py stop
```

La interfaz se está entregando en Inicio: `http://127.0.0.1:8787/`. Comprobar `/api/status` al retomar; la disponibilidad observada durante las pruebas no garantiza que los procesos sigan activos.

## Arquitectura implementada

FastAPI sirve el frontend Vite/TypeScript y la API en el mismo origen. La API del modelo se utiliza desde Python; la clave no llega al navegador. Se restringen host, origen de las mutaciones y conexión al modelo local.

LangGraph separa Orquestador, Metodólogo y Verificador. El orquestador elige etapa/ficha; el metodólogo trabaja con una ficha; el verificador entrega un dictamen. Un rechazo admite un reintento; un segundo rechazo entrega respuesta segura. El frontend recibe eventos SSE reales de nodos, tiempos y verificación. No muestra candidatos ni razonamiento interno antes de verificar la respuesta. Se serializa la generación del modelo y se guarda el intercambio final.

Hay diez etapas y quince fichas metodológicas. La selección de una ficha y su contenido respaldan la respuesta. **No se ha implementado RAG vectorial ni una base de embeddings.** No afirmar que las relaciones semánticas entre proyectos ya se recuperan mediante vectores.

### Clases de información distintas

1. Historial de chat: turnos y metadatos persistidos por cuaderno.
2. Contexto inicial: reto, entorno, objetivo, hipótesis, criterio de aceptación y ambición. Llega a los prompts, pero las hipótesis siguen siendo supuestos y las metas no son evidencia.
3. Campos metodológicos verificados: solo actualizaciones aceptadas con respaldo del usuario y del verificador; separados del contexto inicial.
4. Post-its personales: anotaciones del usuario guardadas por cuaderno. **No se convierten en campos verificados ni se envían al modelo.** Conservar esta separación salvo nueva decisión explícita de producto.
5. Agenda personal: tareas con fecha, hora, prioridad y proyecto opcional; tampoco entran en los prompts ni constituyen evidencia metodológica.

SQLite de negocio es independiente de los checkpoints técnicos de LangGraph. Las migraciones conservan cuadernos anteriores.

## Interfaz y cambios realizados

### Inicio y creación de cuadernos

Inicio muestra proyectos reales en carpetas, con búsqueda, orden, etapa, fecha y número de mensajes. No crea proyectos automáticamente. El color del cuaderno se elige entre azul, amarillo, verde, naranja, morado y gris.

El formulario exige nombre y reto al crear desde la interfaz. Entorno/objetivo son opcionales; Más detalles contiene hipótesis, criterio, ambición y etapa inicial. Vista previa de carpeta coloreada. Editar cuaderno actualiza perfil/color sin reemplazar historial, etapa ni memoria verificada; se bloquea durante generación para mantener contexto consistente.

Se corrigió el recorte del contorno de foco dentro del formulario desplazable: margen interior de 6px. Validación en línea, foco al primer campo incompleto y texto conservado; sin burbuja nativa que tape campos.

### Post-its: última extensión

- Panel derecho principal con una sola pila vertical, según las referencias del usuario.
- Título (hasta 100 caracteres), texto (hasta 3000), categoría y color.
- Categorías: Idea, Prototipo, Observación, Pregunta, Decisión y Otro.
- Colores de nota: amarillo, rosa, azul, verde, morado y naranja. Son independientes del color de la carpeta.
- Nueva nota permite escribir manualmente. Guardar selección del chat abre el editor con el fragmento elegido. Cada respuesta tiene Guardar en post-it para el texto completo.
- Editor como diálogo del color elegido, validación en línea, foco protegido y botones fuera del área desplazable.
- Notas ordenadas de más nueva a más antigua; editar conserva fecha de creación y fragmento original. El origen se consulta mediante desplegable.
- Edición y eliminación tienen botones accesibles. La eliminación pide confirmación dentro de la nota.
- Papel de color con tinta oscura legible, sombra suave y esquina doblada de 19px; sin texturas simuladas.
- Grafo cerrado por defecto mediante `flow-details`; botón de cabecera Ver flujo de agentes permanece disponible aunque crezca la pila. En móvil ese acceso es un icono con nombre accesible.
- Contexto, memoria verificada y ficha quedan en desplegables secundarios.
- Hasta 980px el inspector se coloca debajo del chat y mantiene una columna.

### API de notas

`GET /api/notebooks/{id}` devuelve `state`, `turns` y `notes`.

```text
POST   /api/notebooks/{id}/notes
PUT    /api/notebooks/{id}/notes/{note_id}
DELETE /api/notebooks/{id}/notes/{note_id}
```

Cuerpo de creación/edición: `title`, `text`, `color`, `category`, `source_text` opcional. La edición preserva el origen almacenado aunque el cliente envíe otro. Cada operación se limita al cuaderno correspondiente; IDs de otro cuaderno no permiten editar o borrar. Eliminar un cuaderno elimina sus notas por clave foránea en cascada.

## Archivos clave

Rutas relativas al workspace:

| Archivo | Responsabilidad |
|---|---|
| `PRODUCT.md` | Objetivo, restricciones y decisiones de producto |
| `DESIGN.md` y `.impeccable/design.json` | Sistema visual registrado, esquema 2 y componentes |
| `prototipo/frontend/index.html` | Estructura de Inicio, chat, inspector y diálogos |
| `prototipo/frontend/src/main.ts` | Navegación, SSE, selección de chat y CRUD de notas |
| `prototipo/frontend/src/style.css` | Identidad visual, carpetas, Post-its y adaptación móvil |
| `prototipo/src/ruta_dia_agents/web.py` | API, SSE, perfil y rutas de notas |
| `prototipo/src/ruta_dia_agents/notes.py` | Validación de notas y enumeraciones admitidas |
| `prototipo/src/ruta_dia_agents/memory.py` | SQLite, migraciones, historial, perfil y notas |
| `prototipo/src/ruta_dia_agents/contracts.py` | Contratos de agentes, estado y contexto |
| `prototipo/src/ruta_dia_agents/runtime.py` | Prompts y comprobaciones de respaldo/contexto |
| `prototipo/src/ruta_dia_agents/direct_runtime.py` | Integración directa con modelo local |
| `prototipo/src/ruta_dia_agents/langgraph_workflow.py` | Grafo y eventos reales de ejecución |
| `prototipo/src/ruta_dia_agents/config.py` | Configuración y rutas de almacenamiento |
| `prototipo/docs/interfaz-local.md` | Uso, API, pruebas y ejecución local |
| `prototipo/docs/arquitectura-langgraph.md` | Arquitectura y decisiones del grafo |
| `prototipo/tests/test_web.py` | Pruebas de API, notas y persistencia |
| `prototipo/data/interface-qa/` | Capturas, contrato y revisión de la extensión |

## Validaciones realizadas

Extensión de Post-its: **72 pruebas de backend aprobadas**, Ruff correcto y compilación TypeScript/Vite correcta. La extensión posterior de agenda eleva el total a **79 pruebas backend y 5 frontend**; sus comprobaciones y cierre se detallan en «Cambios recientes de Hilo y agenda».

```powershell
# Desde prototipo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
# Desde prototipo/frontend
pnpm run build
```

Las pruebas de notas cubren persistencia tras reabrir, separación de cuadernos, edición/origen inmutable, eliminación/cascada, límites, datos vacíos, categoría/color inválidos, cuaderno inexistente y mismo origen. Comprobación manual en navegador: crear nota escrita, seleccionar realmente 43 caracteres, guardar respuesta completa, editar título, personalizar categoría/color, recargar, cancelar confirmación de borrado y recuperar formulario inválido.

Escritorio 1440×900 y móvil 390×844 revisados. Captura adicional del grafo completo en 1440×1100. Detector visual ejecutado una vez sin hallazgos (`[]`). Reviewer fresco: **ship**, sin hallazgos materiales; la limitación inicial de captura del grafo se cerró con `postits-flow-visible-desktop.png`. Documentación de diseño y JSON/YAML validados. Registro: `prototipo/data/interface-qa/postits-review.md`.

Una prueba real previa del modelo con contexto y PESTEL tardó aproximadamente 38,5 segundos, terminó con observaciones y sin guardar campos no respaldados. Es una observación aislada, **no un benchmark ni evidencia de precisión general**. En la extensión de Post-its se comprobó conectividad del modelo; los mensajes de demostración fueron sintéticos, no nuevas inferencias usadas como evaluación de Qwen.

## Datos que deben conservarse

En la extensión de agenda se observaron estos cuatro cuadernos; conservar sus nombres y turnos:

| Cuaderno | Mensajes |
|---|---:|
| Estretegias de negocio POWER BI | 0 |
| App de Reserva | 2 |
| Mi proyecto | 2 |
| Prueba de interfaz | 10 |

El cuaderno Prueba de Post-its (temporal), sus tres notas sintéticas y sus datos de prueba fueron eliminados mediante la API. Se retiraron los scripts temporales de creación/limpieza. Las capturas se conservan como evidencia y contienen datos claramente sintéticos. No insertar notas de demostración en los cuadernos reales ni borrar conversaciones del usuario para probar la interfaz.

## Pendientes y continuidad

### Cambios recientes de Hilo y agenda

Otro agente cambió la identidad visual a **Hilo**, incorporó logos locales y una barra lateral azul con Navegación, Proyectos, Herramientas y tres proyectos recientes. El perfil permite editar el nombre en `localStorage` (`hilo-perfil`). Hay una biblioteca de quince fichas y cuatro herramientas destacadas en Inicio. Esas decisiones se conservaron en la extensión actual.

Inicio ahora presenta un calendario mensual en español a la izquierda y **Tu agenda** a la derecha, después de las carpetas y de Herramientas. En móvil ambos apartados se apilan. El calendario usa una base lavanda y retícula violeta con números blancos; el día actual usa un círculo verde suave y la selección es blanca. Los puntos cálidos indican tareas y los azules, conversaciones reales. Seleccionar un día filtra las tareas; las flechas cambian de mes y «Hoy» vuelve al mes actual y a las tareas de hoy.

«Nueva tarea» abre un formulario dentro de la agenda: título, fecha, hora, importancia Alta/Media/Baja y proyecto opcional. Se puede editar, completar y reabrir una tarea. Filtros: Hoy, Próximas (pendientes, incluidas vencidas) y Todas. Las fechas más cercanas van primero; las completadas quedan al final. El plazo tiene etiquetas Vencida/Hoy/Mañana/En N días y color independiente de la prioridad. No hay alertas programadas ni notificaciones.

Persistencia: tabla `tasks` en la misma SQLite de negocio. Fechas con zona horaria, normalizadas a UTC en Python y mostradas en la zona local del navegador. La asociación opcional al proyecto usa `ON DELETE SET NULL`, para conservar la tarea si ese proyecto se elimina. API: `GET /api/tasks`, `POST /api/tasks`, `PUT /api/tasks/{id}`, `DELETE /api/tasks/{id}`. La interfaz ofrece completar/editar; DELETE es una operación de API. Mutaciones protegidas por el mismo origen.

Archivos principales de esta extensión: `prototipo/src/ruta_dia_agents/tasks.py`, `memory.py`, `web.py`; `prototipo/frontend/src/agenda.ts`, `main.ts`, `style.css` e `index.html`. Pruebas nuevas: `prototipo/frontend/tests/agenda.test.mjs` y casos en `prototipo/tests/test_web.py`.

Validación actual: **79 pruebas de backend y 5 de agenda aprobadas**, Ruff sin hallazgos y build pnpm correcto. Las pruebas de agenda cubren vencimiento, cercanía, zona horaria y completadas. Ejecutar las cinco pruebas frontend desde `prototipo/frontend` con `pnpm exec node --experimental-strip-types --test tests/agenda.test.mjs`. Se comprobó manualmente creación, validación, edición, completar/reabrir, recarga, selección de día, cambio de mes y filtro Hoy. Capturas de escritorio 1440×1400 y móvil 390×844: `prototipo/data/interface-qa/agenda-*.png`; contienen cuatro tareas claramente marcadas «prueba temporal», usadas solo para QA. El registro de cierre y limpieza está en `agenda-review.md`.

No quedaron correcciones materiales pendientes en la extensión de Post-its. El usuario puede realizar ajustes adicionales de diseño sobre lo ya implementado.

Si se retoma trabajo funcional más amplio: definir y evaluar RAG vectorial, recuperación de relaciones entre proyectos y una comparación reproducible de modelos siguen siendo temas abiertos. No implementarlos automáticamente por leer este documento: confirmar el objetivo de la nueva petición y respetar el alcance del usuario.

Antes de continuar, leer PRODUCT.md, DESIGN.md y la documentación local; comprobar `/api/status` y el contenido actual del código. No asumir que el estado de Git está listo para publicar: en esta sesión el proyecto y documentación aparecían como archivos sin seguimiento; no se creó commit ni se pidió publicar/deploy.

Para interacción gráfica usar las APIs disponibles de `mcp__cua_repl`; las automatizaciones nativas de Windows no estaban habilitadas en esta sesión. Restablecer cualquier override de viewport al terminar. No usar scripts que muten el navegador por fuera de esas APIs. Las pruebas de backend por terminal son independientes.

El usuario prefiere avanzar sin confirmaciones repetidas para trabajo reversible ya autorizado. Comunicar avances en español y conservar sus datos. Si una tarea requiere permisos específicos o afecta datos irreversiblemente, aplicar las instrucciones vigentes de la sesión que retome el agente.

Ajuste visual posterior solicitado por el usuario: conservar Herramientas antes del calendario y aproximar la referencia lavanda. Se modificaron solo HTML/CSS y documentación; build correcto, navegación mensual/Hoy y orden DOM comprobados en escritorio 1440×900 y móvil 390×844, sin desbordamiento. Capturas calendar-lavender-*.png. El usuario agregó turnos a App de Reserva: ahora se observaron 6 mensajes; no modificar ni restaurar el recuento anterior.

Refinamiento posterior de agenda: el usuario pidió extender el estilo del calendario. Se añadió
agenda-lavender en HTML y CSS scoped: panel lavanda, filtros violetas y tarjetas/formulario blancos.
Build y comprobación escritorio/móvil correctos; no cambia la API o persistencia. Se observaron
una tarea real «Revistar Prototipo» vinculada a App de Reserva y dos tareas sintéticas de QA,
retiradas únicamente por ID/título después de capturar agenda-lavender-*.png. Conservar la tarea real.

Última referencia de agenda: panel blanco y filas compactas como lista de asignaciones, iconos
circulares violetas que controlan la casilla nativa, título/fecha, prioridad y estado a la derecha.
Completada verde, Pendiente amarillo, Vencida rojo. Sin calificaciones ni progreso ficticio.
Móvil distribuye prioridad/estado debajo. UI real de completar/reabrir comprobada con una tarea
temporal, retirada por ID/título; tarea Revistar Prototipo conservada. Build correcto y móvil sin
desbordamiento; capturas agenda-assignments-*.png. Orden Herramientas antes de calendario conservado.

Ajuste final de espaciado solicitado: conservar el diseño aprobado y conectar títulos con contenido.
CSS scoped home-view: margen de encabezado 16px, contador 12px/12px, carpetas gap20, secciones
24px margen/18px padding, descripción de herramientas 5px/10px y agenda 24px/20px con gap28.
Móvil reduce más los intervalos; no cambia orden, datos ni flujos. Build correcto, escritorio
1440×900 y móvil 390×844 sin desbordamiento. Capturas home-spacing-*.png.

Ajuste posterior de ancho: usuario detectó demasiado blanco a ambos lados. CSS scoped
home-view elimina los límites de 1090px y usa márgenes clamp(24px,2.2vw,42px); móvil 20px.
Desde 1280px, cuatro columnas de proyectos y calendario de hasta 440px con agenda flexible.
Herramientas ocupa el mismo ancho. En 1920px contenido observado x294/1569px, márgenes
42px más scrollbar (antes x534/1090px). Build correcto; escritorio 1920×900 y móvil 390×844
comprobados sin desbordamiento. Capturas home-width-*.png; no se modificaron datos.

Refinamiento solicitado: añadir algo de margen y ampliar calendario/reducir agenda.
Sustituye el ajuste anterior: laterales clamp(28px,4vw,76px), móvil20px. Desde1280px
retícula minmax(440px,.95fr)/minmax(0,1.05fr), fechas52px, círculo38px, texto14px.
En1920px calendario699.67px/agenda773.31px (antes440/1101). Build correcto y
1920,1280,390px sin desbordamientos. Captura home-balance-desktop.png. Datos intactos.

Refinamiento del chat solicitado con cuatro referencias: mismo azul #294eb8, blanco y tonos
fríos. Se cambió index.html (marca en encabezado), main.ts (turnHeader con avatar y hora real
created_at; pending reutiliza header; actualizar iniciales al editar perfil) y CSS scoped
project-workspace. Usuario azul/derecha, Hilo blanco/izquierda, footer separado con acciones,
compositor hasta820px y enviar44px; Markdown/tablas/código conservados y saneados.
Build correcto; escritorio1440×900, intermedio800×900 y móvil390×844 sin desbordamiento.
Guardar respuesta abre editor con fragmento correcto, cancelado sin guardar; flujo abre/cierra;
escritura multilínea y foco Tab/enviar verificados sin enviar. No hubo inferencia ni escrituras
API. App de Reserva conserva6 mensajes y3 notas reales (ejemplo2, Pregunta · ejemplo de prueba,
diseño), NO borrar esas notas por parecer de prueba. Capturas chat-refresh-*.png.

### Diagnóstico del árbol de problemas (23 sep 2026)

Botón **Diagnosticar** en la cabecera del árbol. Diagnostica la versión guardada
(`POST /api/projects/{id}/problem-tree/diagnosis`) en dos capas, en `tree_diagnosis.py`:

1. **Reglas** (código, instantáneas): carril vacío, tarjetas sin fuente, ninguna causa de fondo,
   causas redactadas como «falta de / no hay / sin…», tarjetas repetidas o muy breves.
2. **Contenido** (Qwen3.5-4B, rol `tree_reviewer`): solo revisa si el problema central describe
   una solución. Debe citar literalmente el fragmento; si la cita no aparece, se descarta.
   Si el modelo está ocupado o no responde, se devuelven solo las reglas (`model_status`).

Cada observación se muestra junto a lo que señala (tronco, carril o tarjeta), no en un informe
aparte: es el efecto de atención dividida de la Teoría de la Carga Cognitiva. Al editar, el
diagnóstico se marca como desactualizado. El diagnóstico **nunca modifica el árbol**.

**No volver a pedirle al modelo** «tarjeta en el lado equivocado» ni «causa muy general»: con el
4B dieron hasta 7 alarmas falsas por corrida y llegaron a marcar las cinco tarjetas de un árbol
correcto. «Falta de…» pedida al modelo la aplicaba a casi todas las causas; por eso es una regla.
Resultado final con dos árboles y dos semillas: 4/4 errores plantados, 0 alarmas falsas en el
árbol correcto, 1,4 s por árbol. Detalle y cifras en el docstring de `tree_diagnosis.py`.
Pruebas: `tests/test_tree_diagnosis.py` (12).

**El diagnóstico llega al agente.** Cada diagnóstico se guarda como texto breve en la tabla
`project_tree_diagnoses` (una fila por proyecto, con `tree_version`) y se agrega a
`shared_context`, que reciben los tres agentes. Solo se incluye mientras `tree_version`
coincide con la versión actual del árbol: si el árbol cambia, el diagnóstico viejo deja de
enviarse. El texto usa frases fijas por hallazgo (`summary_text`), no las explicaciones del
modelo, y cabe en unas 300 letras.

### 5 porqués desde el árbol (23 sep 2026)

Botón «Profundizar con 5 porqués» en las **causas principales** del árbol (una causa de fondo
no admite otra debajo: el árbol tiene dos niveles). Abre el chat junto al árbol y el agente
pregunta «¿por qué?» una vez por turno. Módulos: `why_analysis.py`, tabla
`project_why_analyses` en `sharing.py`, barra `frontend/src/why-analysis.ts`.

- **El código registra, el agente pregunta.** Cada mensaje de la persona ya es el paso de la
  cadena y se guarda antes de que responda el agente. El primer mensaje solo abre el análisis;
  durante la revisión no se registran pasos; un «no sé» pasa a dudas y el mensaje siguiente es
  el plan para averiguarlo, no un paso.
- **Herramienta fija por código** (`ProjectState.locked_tool`, no se guarda con el cuaderno)
  mientras el análisis está en curso. Un solo análisis en curso por proyecto.
- **Sin campos `porque_N` durante el análisis**: el Metodólogo intentaba llenarlos y el
  Verificador lo rechazaba.
- **Sin historial reciente durante el análisis**: el 4B copiaba preguntas anteriores del
  historial. La cadena en `shared_context` es la fuente de verdad; `load()` rehace el historial.
- **Pregunta literal en cada estado** (siguiente, pausa tras el plan, revisión). Con
  instrucciones generales el 4B cedía ante el historial; el texto literal sí lo sigue.
  `as_clause()` quita «porque» / «creo que» para formar la pregunta.
- **Excepción del Verificador** (`five_whys_asks_user_why`): en 5 porqués, preguntar «¿por qué…?»
  a la persona no es inversión de roles, salvo que le pida hacer preguntas («hazme», «pregúntame»).
- **Ficha ajustada** (pendiente de validación experta): el cierre entrega causa candidata,
  evidencia y dudas, no una acción; la cadena se puede revisar en cualquier momento.
- Al terminar, la persona elige la causa candidata; «Incorporar al árbol» la agrega como causa
  de fondo de la tarjeta de partida con origen «Análisis de 5 porqués». Nunca se incorpora sola.

Validación con Qwen3.5-4B (recorrido: respuesta, «no sé», plan, hipótesis, revisión): 6/6 turnos
aprobados al primer intento. Antes de los ajustes: 2 respuestas de seguridad y 1 retroceso.
Pruebas: `tests/test_why_analysis.py` (14).

**Respuestas flojas (24 sep 2026).** Una prueba con respuestas malas mostró que todo entraba a la
cadena y que el agente preguntaba «¿Por qué ocurre que por muchas cosas?». Ahora
`why_analysis.apply_turn` decide y deja un aviso (`notice`, columna nueva con migración):
- `vaga` («por muchas cosas») y `solucion` (herramienta que falta: «no hemos comprado Power BI»)
  **no entran la primera vez**; si la persona insiste, entran. `pregunta` nunca entra.
- «tampoco sé» tras un «no sé» deja «Plan: sin definir»; un tercer «no sé» da `sin_hipotesis` y
  el agente deja de insistir.
- Revisión: `reviewing` ahora cuenta mensajes (`review_turns`). Antes el agente repetía la
  pregunta de revisión en bucle; ahora responde al comentario o propone terminar.
- Cada texto literal es **una sola pregunta sin comillas anidadas**: el Verificador exige
  exactamente una pregunta por respuesta.
- **`source_sections` con tope de 4** (`runtime.guide`): el 4B repetía el mismo encabezado hasta
  agotar los 384 tokens y el JSON quedaba cortado (turno caído, 2/2 reproducido; 2/2 bien tras
  el tope). Pendiente aparte: un JSON inválido tumba el turno en vez de contar como intento.

### Carpeta compartida entre Windows y Linux (6 oct 2026)

El repositorio se movió de OneDrive a un disco NTFS que abren los dos sistemas del mismo
equipo (arranque dual): `D:\hilo\proyecto` en Windows, `/mnt/d/hilo/proyecto` en Linux. La
carpeta superior tiene un `CLAUDE.md` de entrada, los documentos de la tesis y el contexto de
las sesiones anteriores, que es privado y **no** entra a este repositorio.

- **Implementado:** copia verificada archivo por archivo, entornos de Windows recreados en la
  ruta nueva, y `core.autocrlf=true` / `core.fileMode=false` en `.git/config` para que ambos
  sistemas vean los mismos cambios.
- **Implementado, sin ejecutar todavía en un Linux real:** soporte de Linux en los scripts.
  - `scripts/local_runtime.py` (nuevo, solo biblioteca estándar) reúne lo que cambia entre
    sistemas: carpeta local (`%LOCALAPPDATA%` o `~/.local/share`), dónde está `llama-server`,
    identidad de procesos (PowerShell o `/proc`) y cómo detenerlos. `local_model.py` e
    `install_local_model.py` lo usan; la rama de Windows hace lo mismo que antes.
  - El instalador baja para Linux los paquetes oficiales de la misma compilación (b11146), con
    el tamaño y el SHA-256 que publica GitHub: `cuda` (12.8, si el controlador de NVIDIA es 570
    o posterior), `vulkan` o `cpu`. `--backend` fuerza uno y queda anotado en
    `llama-backend.txt`. No se asume la estructura interna del paquete: `llama-server` y las
    `.so` se buscan después de extraer. **El contenido de esos paquetes no se inspeccionó.**
  - `scripts/interface.py` con `start_interface.sh` / `stop_interface.sh` equivalen a los `.ps1`.
    El entorno va en `~/.venvs/hilo` (`UV_PROJECT_ENVIRONMENT`), fuera del disco compartido.
  - `build_frontend.sh` construye sobre una copia en `~/.cache`, porque `node_modules` en el
    disco compartido es el de Windows.
  - `config.py`: en Linux la memoria va a `~/.local/share/RutaDIA`, no a `data/` dentro del
    disco NTFS. Los proyectos creados en Hilo no se comparten entre sistemas.
  - Una carpeta `modelos` junto al repositorio sirve de copia compartida del `.gguf`: el
    instalador la copia si el SHA-256 coincide, en vez de descargar 2,7 GB.
  - `.gitattributes` fija LF en los `.sh`.
  - Pruebas: `tests/test_local_runtime.py` (20). En Windows hoy solo corren con
    `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, por el bloqueo de abajo.
  - Sin adaptar: `scripts/compare_local.py` (usa `ctypes.windll` para medir memoria).
- **Bloqueo abierto en Windows:** Smart App Control impide cargar `uuid_utils` 0.17.1
  (`_uuid_utils.cp313-win_amd64.pyd`), así que `pytest` no llega a recolectar. Falla igual en
  la ruta anterior: no lo causó la mudanza. La última corrida completa (131 pruebas) es del
  24 de septiembre. No se cambiaron políticas de Windows.

### Primera ejecución real en Linux (6 oct 2026)

Hecha en Ubuntu 26.04.1 (kernel 7.0), RTX 4060 Ti con controlador de NVIDIA 595.91, `uv` 0.12.21.
Los scripts de Linux funcionaron sin cambios de código.

- **Comprobado:** `uv sync --extra dev --frozen` crea `~/.venvs/hilo` con Python 3.13.15 (el del
  sistema es 3.14 y el proyecto pide `<3.14`; uv descarga el suyo). 151 pruebas aprobadas en Linux
  (`pytest -q -p no:cacheprovider`, para no escribir cachés en el disco compartido).
- **Comprobado:** el instalador copió el `.gguf` desde `modelos/`, eligió `cuda` y bajó los dos
  paquetes oficiales b11146 con su SHA-256. `llama-server` arranca en ~2 s, ocupa ~3 GB de la GPU y
  genera a ~73 tokens/s. `start_interface.sh` dejó Hilo en `http://127.0.0.1:8787` con
  `/api/status` en `available: true`.
- **Comprobado:** `git status` muestra en Linux los mismos 30 cambios que en Windows.
- **Sin hacer:** el disco no está en `/etc/fstab`. Hoy lo monta el explorador de archivos en
  `/run/media/cristian/Nuevo vol` (controlador `ntfs3`), solo después de abrirlo a mano. Montarlo
  fijo en `/mnt/d` requiere `sudo` y es decisión del usuario.
- **Ojo al cambiar el punto de montaje:** el entorno instala el paquete en modo editable y guarda la
  ruta absoluta del proyecto. `start_interface.sh` solo sincroniza si falta el Python del entorno,
  así que tras mover la ruta hay que repetir `uv sync --extra dev --frozen` con
  `UV_PROJECT_ENVIRONMENT=~/.venvs/hilo` (o borrar `~/.venvs/hilo`). No se cambió el script.
- **Sin hacer:** cuenta de Hilo en Linux (la base `~/.local/share/RutaDIA` está vacía),
  `build_frontend.sh` (falta `pnpm`) y un turno completo de los tres agentes desde la interfaz.

### Batería exploratoria del agente en Linux (6 oct 2026)

33 turnos reales por el flujo completo, una semilla, calificados por el asistente (no es
evaluación ciega). Informe, script y datos crudos: `../tesis/pruebas-agente-2026-10-06/`
(fuera del repositorio). Nota media 2,6 sobre 5; español correcto en 31 de 33.

- **Solo se probó; no se cambió código ni prompts.**
- **Sin resolver:** no hay salida «fuera de alcance» (el Orquestador siempre elige una ficha);
  el Metodólogo solo puede preguntar, así que no explica ni recomienda; el mensaje de seguridad
  salió en 3 de 12 peticiones directas de una ficha (PESTEL, Lean Canvas, matriz).
- **Defecto sin corregir:** `grounded_verdict` deja pasar `template_updates` con valor vacío
  (`if value and not supported`) y `memory.py` los guarda con `DO UPDATE`: un turno aprobado
  puede vaciar un campo ya verificado.
- **Disco en Linux:** las carpetas de `proyecto/` tienen el atributo de solo lectura de NTFS y
  `ntfs3` lo respeta. Se pueden editar archivos existentes, pero no crear archivos nuevos ni
  escribir en `.git` (sin commit desde Linux) ni en `data/evaluations`. Sin resolver.

### Inicio como cuaderno (6 oct 2026)

Pedido del usuario con cinco referencias (carpeta `referencia inicio/`, fuera del repositorio):
Inicio en dos columnas que aprovechen el ancho, estética de cuaderno con letra de esfero y
materiales distintos, formas variadas (no solo rectángulos) y animaciones al interactuar, tipo
juego. **El encabezado no se toca** y las carpetas se conservan, solo con añadidos.

- **Implementado.** Todo vive en `frontend/src/home-cuaderno.css` y `frontend/src/home-fx.ts`,
  con selectores bajo `#app #home-view`: ninguna otra vista cambia.
  - `index.html`: Inicio se divide en `.home-main` (portada, proyectos, herramientas) y
    `.home-rail` (calendario y agenda). Desde 1240 px son dos columnas; debajo, una.
  - Portada `.home-hero`: saludo según la hora con el nombre de la cuenta, fecha, tres contadores
    reales (proyectos, pendientes, para hoy) y un lápiz que responde al clic. `main.ts` solo
    agrega `renderHero()` y la llama desde `renderProjects`, `tasksChanged` y `renderProfile`.
  - Materiales: fondo cuadriculado con margen rojo, portada y agenda en hoja rayada, cinta,
    argollas en el calendario, gancho en la agenda, bordes de tinta irregulares.
  - Formas: contadores en óvalo, círculo y mancha; botones en píldora que se hunden; días en
    círculo; fichas y tareas con esquinas irregulares distintas entre sí.
  - Animaciones: entrada escalonada, folios que asoman de la carpeta al pasar el cursor,
    subrayado que se dibuja, día encerrado a mano, tachado al completar, y estallidos de emojis
    y hojas al abrir una carpeta, completar una tarea, crear algo o tocar el lápiz.
  - Fuentes Caveat y Patrick Hand (OFL), servidas desde `frontend/public/fonts`, sin internet.
  - Con «reducir movimiento» del sistema no hay animaciones ni estallidos.
- **Se conservó:** colores y forma de las carpetas, lavanda del calendario, colores semánticos
  de prioridad y plazo, la expansión de las fichas al pasar el cursor, y todos los `id` que usa
  `main.ts`.
- **Comprobado en Linux:** build correcto, 151 pruebas de backend y 5 de agenda aprobadas,
  revisión en 1920, 1440, 1280, 1100 y 375 px sin desbordamiento horizontal.
- **Sin hacer:** no se probó en Windows ni con un proyecto compartido (avatares en la carpeta);
  `.impeccable/design.json` no se actualizó; no hay capturas en `data/interface-qa`.
- **Para la tesis:** la carga cognitiva extrínseca es la variable dependiente. Estas animaciones
  y adornos entran en lo que se mide en las sesiones; decidir si la evaluación se hace con ellas.
- `scripts/build_frontend.sh` ahora copia con `--chmod=u+rwX`: las carpetas del disco NTFS
  venían de solo lectura y `pnpm` no podía escribir en la copia de trabajo.

**Ajuste del mismo día, a pedido del usuario («más elegante», carpetas «más largas», tarjeta
para agregar):** trazo de 2.5 a 1.6 px, sombras suaves en vez de sólidas, paneles sin giro,
pasteles y cuadrícula más claros, relieve de botones de 5 a 3 px. Carpetas más anchas: mínimo
de 205 a 320 px, con el alto original de 245. `renderProjects` antepone la tarjeta `.project-add` («Agregar nuevo proyecto»), que abre
el mismo formulario; no aparece al buscar ni cuando no hay proyectos. «Más largas» significa
más anchas (horizontal): el usuario lo aclaró después de ver una versión más alta.

### Calendario como cuaderno (6 oct 2026)

El usuario pidió llevar la misma temática a la vista Calendario del menú (no al calendario
pequeño de Inicio, que ya la tenía).

- **Implementado** en `frontend/src/calendario-cuaderno.css`, bajo `#app #calendar-view` y
  `.calv-dialog`. Ni `index.html` ni la lógica del calendario cambiaron.
  - Cuadrícula como planificador de argollas: cabecera lavanda, líneas punteadas, días fuera del
    mes rayados, hoy en círculo azul, día elegido resaltado y encerrado a mano.
  - Entradas como etiquetas con borde de su color; conservan color por proyecto, tachado de
    completada y punto rojo de vencida.
  - Panel del día como bloc perforado y rayado; casillas dibujadas a mano (siguen siendo
    `input` reales); filtros en píldora.
  - Barra: título y mes a mano, «Hoy» en óvalo, flechas en círculo, Mes/Semana en píldora.
  - Diálogo de entrada con la misma letra, bordes y botones.
  - `home-fx.ts` → `initCalendarFx()`: la hoja se desliza al cambiar de periodo o de vista, sale
    un lápiz al elegir un día y hay estallido al completar una entrada o crear una.
- **Compartido:** los colores, fuentes y botones del cuaderno pasaron a un selector común en
  `home-cuaderno.css` (`#app :is(#home-view,#calendar-view),.calv-dialog`).
- **Restricción respetada:** `fitMonthCells` cuenta píxeles; no se tocó el alto de
  `.calv-cell-top` (24), `.calv-chip` (20) ni `.calv-more` (16).
- **Decisión:** las horas (columna de la semana y hora de cada etiqueta) siguen en la fuente del
  sistema. En letra manuscrita el 14 y el 17 se confundían.
- **Comprobado en Linux:** build, 151 pruebas de backend y 5 de agenda; mes, semana, diálogo y
  celular (375 px) sin desbordamiento. **Sin probar:** Windows, y un mes con muchas entradas por
  día (el «+N más»).

### Chat como cuaderno (6 oct 2026)

El usuario pidió «aplicar lo mismo» al chat.

- **Implementado** en `frontend/src/chat-cuaderno.css`, bajo `#app #project-workspace`, más la
  barra flotante `.project-floating-toolbar`. Ni `index.html` ni la lógica del chat cambiaron.
  - El panel del chat es una hoja perforada con margen rojo sobre fondo cuadriculado.
  - **Lo que escribe la persona va a mano** (Patrick Hand, burbuja de tinta azul) y el cuadro
    de texto también. **Lo que responde Hilo va en letra de imprenta** sobre ficha blanca: es
    el texto que hay que leer con cuidado. Decisión del asistente, no pedida por el usuario.
  - El veredicto es un sello punteado e inclinado; conserva verde, ámbar y rojo y su texto.
  - Ficha citada en píldora punteada, «Guardar en post-it» en nota amarilla, copiar en círculo.
  - Mientras responde: lápiz que se mueve y renglones garabateados en vez de barras grises.
  - Bienvenida con título a mano y tres fichas pegadas con cinta, cada una con forma distinta.
  - Barra flotante en píldora con borde de tinta; la herramienta activa es una pestaña de papel.
  - `home-fx.ts` → `initChatFx()`: estallido al enviar, al llegar la respuesta verificada, al
    guardar en post-it, al copiar y al elegir una tarjeta de bienvenida.
- **Sin tocar:** paneles de Post-its, Agentes y Árbol (quedan con su diseño sobre el fondo
  nuevo), diálogos del proyecto, y el alto de línea de 24 px del cuadro de texto, del que
  depende `fitMessageInput`.
- **Corregido de paso:** la nota bajo el cuadro de texto quedaba tapada por la barra flotante;
  ahora hay espacio.
- **Comprobado en Linux:** build, 151 pruebas de backend y 5 de agenda; bienvenida, dos turnos
  reales con el modelo, estado «pensando», Post-its al lado y celular (375 px). **Sin probar:**
  Windows, respuestas largas con tablas o código, un turno rechazado y proyectos compartidos.

### Inicio: color por vencimiento (6 oct 2026)

Pedido del usuario: en Inicio, que el recuadro sea rojo si la tarea venció, amarillo si está
cerca de vencer y verde si todavía tiene tiempo.

- **Implementado** (solo en Inicio; la vista Calendario sigue coloreando por proyecto):
  - Cada tarea de «Tu agenda» toma fondo y borde según `data-tone`, que ya calculaba
    `taskTiming`: `overdue` rojo; `soon` y `near` (tres días o menos) amarillo; `later` verde;
    `done` gris.
  - En el calendario pequeño, el recuadro del día toma el plazo más urgente de sus tareas
    pendientes (`dayTone` en `main.ts`); reemplaza al punto de tareas.
  - Leyenda nueva en el calendario y bajo la agenda (`index.html`).
- **Decisión:** dentro de la tarjeta, la prioridad y el estado pasan a etiquetas neutras. Antes
  tenían color propio (rosa, ámbar, verde) y competían con el color del plazo. El texto
  «Prioridad alta/media/baja» se conserva.
- **El color no va solo:** cada tarea mantiene su etiqueta de plazo («Vencida», «Hoy», «En 5
  días»), y la leyenda explica los tres colores.
- **Comprobado:** los cuatro tonos en tareas y en días del calendario, con datos de ejemplo.
  El rojo se comprobó por estilos calculados, no a la vista (el panel del navegador estaba
  oculto). Build, 151 pruebas de backend y 5 de agenda.

### Post-its, Agentes y Árbol como cuaderno (6 oct 2026)

El usuario pidió «aplicar lo mismo» a los tres paneles del tablero.

- **Implementado** en `frontend/src/tablero-cuaderno.css`, bajo `#app #project-workspace`. Ni el
  HTML ni la lógica cambiaron.
  - **Post-its:** hoja punteada; cada nota conserva su color y va pegada con cinta; título y
    texto de la nota a mano; contador en círculo.
  - **Agentes:** el grafo se dibuja con trazo de tinta y letra a mano. El nodo en ejecución es
    amarillo con borde que avanza; completado verde; fallido rojo. La memoria verificada sigue
    en letra de imprenta, con una marca de resaltador.
  - **Árbol:** conserva hojas verdes, tronco naranja y raíces cafés. Las tarjetas pasan a borde
    completo de su color (se quitó la franja lateral gruesa); lo que escribe la persona va a
    mano; diagnóstico y hallazgos siguen en imprenta.
  - **Barra de 5 porqués:** misma letra y botones, en su tono café.
  - `home-fx.ts` → `initBoardFx()`: estallidos al crear una nota, añadir un efecto o una causa,
    guardar el árbol, diagnosticar y abrir o avanzar un análisis de 5 porqués.
- **Regla de letra, ahora en todo el proyecto:** a mano lo que escribe la persona; en imprenta
  lo que produce el sistema.
- **Corregido de paso:**
  - En pantallas angostas la cabecera del árbol se encogía por debajo de su contenido y pisaba
    el carril «Efectos» (`flex-shrink` en una columna de alto fijo).
  - Con el árbol abierto, el chat queda angosto: ahí se quitan las perforaciones y el margen
    (consulta de contenedor `chat` en `chat-cuaderno.css`).
- **Comprobado en Linux:** build, 151 pruebas de backend y 5 de agenda; los tres paneles con
  datos de ejemplo (cuatro notas, un árbol con causa de fondo) y el árbol en celular.
  **Sin probar:** Windows; el grafo durante un turno real (nodos en ejecución, completado y
  fallido); el diagnóstico del árbol con hallazgos; un análisis de 5 porqués en curso; arrastrar
  tarjetas; editar y borrar notas; los diálogos de nota y de proyecto, que no se tocaron.


## Arreglos al agente tras la batería (6–7 oct 2026, Linux)

Responden a los hallazgos de `tesis/pruebas-agente-2026-10-06/INFORME.md`. Solo cambia la ruta LangGraph; la línea base CrewAI (`service.py`) queda igual a propósito. Resultado y calificación por turno: `tesis/pruebas-agente-2026-10-06/INFORME-TRAS-ARREGLOS.md` (nota media 2,6 → 4,1, puesta por el mismo asistente que hizo los arreglos: no es evaluación ciega).

**Implementado** (218 pruebas pasan, ruff limpio; pruebas nuevas en `tests/test_request_kind.py`):

- `contracts.py`: `RequestKind` (`trabajo`, `explicacion`, `recomendacion`, `saludo`, `fuera`, `concepto`), `DIRECT_KINDS` y `has_value`. El `HandoffContract` lleva `kind`.
- `runtime.py`, clasificación: el Orquestador devuelve `kind`, pero decide `resolve_kind` (código): saludo corto, intento de cambiar instrucciones, explicación, recomendación y fuera de tema. Con una ficha nombrada, «¿cómo empiezo?», «¿cuál es el primer paso?» y «¿qué criterios debo…?» son explicación (`_HOW_TO_START`). Una ficha nombrada o ya en uso nunca se «recomienda». El índice de ruta incluye `use_when` de cada ficha.
- `langgraph_workflow.py`: saludo, fuera de tema y concepto sin ficha salen con respuesta fija por `knowledge_gap`, sin perder la etapa ni la ficha activa. En `explicacion` y `recomendacion` se antepone texto literal de la ficha («Qué es», «Cuándo se usa», «Cómo se usa»); el modelo solo aporta la pregunta. Al degradar se muestran los pasos de la ficha en vez del mensaje de seguridad.
- `runtime.py`, verificación en código (`grounded_verdict`):
  - ya no exige «exactamente una pregunta»: vale una pregunta o una sola acción pedida, incluida la forma «necesito que…»;
  - `role_reversal` del Verificador solo cuenta si el texto le pide a la persona preguntar o dirigir (`asks_user_to_lead`); el modelo lo marcaba en preguntas normales;
  - «campo repetido» mira solo la oración interrogativa, no todo el mensaje.
- `runtime.py`, salida del Metodólogo (`guide`): se descartan antes de verificar los campos vacíos y los valores que el mensaje no respalda (`update_supported_by_message`); en cinco porqués `porque_N` exige un marcador de causa («porque», «debido a»…), así el enunciado del problema no llena `porque_1`. Se añade el «¿» de apertura que el modelo omite (`open_question_marks`).
- `memory.py`: no guarda valores vacíos; un campo en blanco no pisa uno verificado.
- Interfaz: las respuestas fijas se rotulan «Sin ficha» (`main.ts`, `FIXED_REPLY_CODES`).
- Ficha `knowledge/tools/Pestel.md`: «situación económica de los afiliados» pasó a «de los clientes o usuarios». El modelo copiaba «afiliados» a preguntas de otros proyectos. Es el único cambio de contenido en las fichas; revertir si la redacción validada debe conservarse.

**No implementado:**

- F01.2: cuando la persona da un dato, el modelo a veces no lo guarda y repite la pregunta.
- E07: el modelo da por llenos bloques del Lean Canvas y el Verificador no lo detecta.
- E08: sin tratamiento para mensajes de desánimo.
- C01, C03: conceptos generales sin ficha (Design Thinking, producto mínimo viable); falta escribir y validar esas fichas.
- E01: una ficha pedida en inglés («5 whys») no se reconoce como nombrada y sale «Te recomiendo…».
- La fórmula «¿qué observación específica…?» sigue repitiéndose (hallazgo 5 del informe).
- Limpieza del repositorio público (16 oct 2026): las fichas ya no nombran a la organización ni a la persona experta en los archivos actuales. Falta reescribir el historial y el correo de autor de los commits viejos (ver la sección del 16 oct).
- El resultado varía entre corridas: en cuatro corridas completas hubo entre uno y tres turnos degradados cada vez, en casos distintos.
- Las respuestas con explicación rondan las 109 palabras (antes 18): entra en la medición de carga cognitiva de la tesis.
- Sin commit: `.git` sigue de solo lectura desde Linux.


## Segunda ronda: seguimiento del dato, temas sensibles y desánimo (7 oct 2026, Linux)

Pedido del usuario: corregir lo que quedó pendiente de la ronda anterior y que el agente «no toque temas sensibles». Resultado y casos: `tesis/pruebas-agente-2026-10-06/INFORME-SEGUNDA-RONDA.md` (batería de 43 turnos; los 33 originales 4,1 → 4,2, grupo sensible 4,8; nota del asistente, no ciega). Solo cambia la ruta LangGraph.

**Implementado** (287 pruebas pasan, ruff limpio; pruebas nuevas en `tests/test_sensitive.py`):

- `sensitive.py` (nuevo): reglas y textos fijos, sin modelo. `sensitive_topic()` devuelve `crisis`, `dano`, `sexual`, `odio`, `opinion` o `consejo`; `shows_distress()` reconoce desánimo con el proyecto; `asks_personal_data()` revisa lo que pide el asistente. Un proyecto *sobre* un tema delicado no se bloquea: las reglas buscan la petición personal, la opinión o el contenido dañino.
- `langgraph_workflow.py`: si el mensaje es sensible, `_orchestrate` no llama al modelo y arma un `HandoffContract` con `kind="sensible"` (nuevo en `RequestKind` y `DIRECT_KINDS`); responde `SENSITIVE_REPLIES[categoría]` con hallazgo `sensitive_topic`. `_opening()` antepone `DISTRESS_OPENING` si hay desánimo y `_stage_notice()` si la ficha es de una etapa posterior a la del cuaderno.
- `web.py`: un mensaje sensible no se registra como paso de un análisis de cinco porqués en curso.
- `runtime.py`, salida del Metodólogo (`guide`):
  - `named_field_update`: «En lo político, …» se guarda por código en el campo nombrado, con las palabras de la persona, aunque el modelo lo omita; el prompt se lo avisa al modelo;
  - `drop_filler`: quita frases que ni preguntan ni piden nada ni repiten algo dicho por la persona («Aplicaremos la técnica SCAMPER.»); las que declaran un avance se conservan para que se juzguen;
  - línea «Esta ficha apenas empieza… primer paso» solo cuando piden explicación o el mensaje no trae datos (8 palabras o menos).
- `runtime.py`, verificación en código (`grounded_verdict`):
  - `repeated_question`: la pregunta repite la del turno anterior del asistente (solo `kind="trabajo"`);
  - `unsupported_progress_claims`: «ya tienes el Problema, los Segmentos…» cuando nombra dos o más bloques que la persona no mencionó ni tiene validados;
  - `sensitive_content`: la respuesta toca un tema sensible o pide datos personales;
  - `asks_first_step`: el primer elemento de «Cómo se usa» nunca cuenta como paso adelantado;
  - los signos de interrogación dentro de un nombre citado («¿Qué piensa y siente?») no cuentan como segunda pregunta; un verbo de acción vale en cualquier parte de la oración.
- Prompts: reglas del Metodólogo reducidas a cinco líneas cortas (una sola parte de la ficha por mensaje, citar la plantilla de la ficha, no repetir, sin relleno ni consejo). Se quitó «pregunta por una observación disponible», origen de la fórmula repetida. El Verificador recibe una definición más estrecha de «paso adelantado».
- `direct_runtime.py`: si el JSON del modelo llega cortado, se repite una vez con `seed + 1` (visto una vez en el Orquestador).
- Interfaz: `sensitive_topic` entra a `FIXED_REPLY_CODES`; interfaz reconstruida.

**Decisiones que conviene conocer:**

- Más reglas en el prompt empeoraron al modelo de 4B (pidió los seis factores del PESTEL de una vez). Lo que deba cumplirse siempre va en código, no en el prompt.
- `drop_filler` y `named_field_update` modifican la salida del Metodólogo antes de verificarla. El Verificador ve menos afirmaciones sin respaldo que antes: afecta cualquier métrica de hallazgos del Verificador.
- La respuesta de crisis cita el 123 y la línea 106 de Bogotá (bogota.gov.co, 7 oct 2026). Falta que la universidad confirme los teléfonos.

**No implementado:**

- Los temas sensibles se detectan por palabras; una redacción no prevista llega al modelo.
- La línea base CrewAI (`service.py`) no tiene filtro de temas sensibles.
- El dato etiquetado solo se captura por código para campos de una palabra nombrados al inicio del mensaje.
- El Verificador aún marca «paso adelantado» sin razón en algunas preguntas correctas (cuesta un segundo intento).
- B01, F01.1, A04, C01, C03 y E01 del informe siguen como estaban.
- Sin probar en Windows ni a mano en el navegador. Sin commit.


## Vista propia de PESTEL (11 oct 2026, Linux)

Tercera herramienta con interfaz propia, después del árbol y los 5 porqués. El usuario pidió investigar si había una forma interactiva demostrada como mejor que la tradicional: no se encontró ninguna comparación con usuarios (solo propuestas de puntaje y de decisión multicriterio validadas con paneles de expertos), así que la vista sigue la forma tradicional de la ficha `knowledge/tools/Pestel.md`, paso por paso.

**Implementado** (301 pruebas pasan, ruff limpio, `tsc` y build correctos; probado en el navegador en 1440×900 y 375×812 con una instancia y una cuenta de prueba temporales):

- `pestel.py`: `PestelUpdate` con el reto y los seis factores (`politico`, `economico`, `social`, `tecnologico`, `ecologico`, `legal`, los mismos `template_fields` de la ruta). Cada elemento: texto, `kind` (vacío, `oportunidad` o `amenaza`), fuente opcional y `priority`. Topes: 8 elementos por factor y 5 prioritarios. `context_lines()` resume el PESTEL para el agente.
- `sharing.py`: tabla `project_pestels` y `pestel()` / `save_pestel()`, con versión y conflicto 409 igual que el árbol; solo propietario y editores guardan.
- `web.py`: `GET` y `PUT /api/projects/{id}/pestel`; el resumen entra a `shared_context` como «PESTEL (borrador del equipo, no verificado)…».
- `frontend/src/pestel.ts` y `pestel.css`: `PestelController`. Muestra los cuatro pasos de la ficha con su avance, el reto (se copia del cuaderno como borrador), los seis factores, marcas de oportunidad o amenaza, ★ para priorizar y el resumen «Lo más relevante para tu reto». La fuente de cada elemento se abre a pedido para no recargar.
- Rediseño pedido por el usuario el mismo día, con tres referencias (tablero de columnas con notas): cada factor es una **columna** con su letra grande (P·E·S·T·E·L) y su pregunta guía, y **todo lo que la persona escribe va en un post-it** («donde la persona escriba, sí o sí, sean post-its»). El color del post-it dice qué es: amarillo sin marcar, verde oportunidad, rosado amenaza, siempre con la palabra. Un post-it punteado con «+» agrega otro. Seis columnas a lo ancho; tres por dos con el chat abierto (consultas de contenedor sobre `.pestel-view`); en celular cada factor es una franja horizontal.
- Enlace con el chat, en los dos sentidos: «Preguntarle a Hilo» en un factor guarda y envía «Quiero seguir con el PESTEL: factor X.»; un dato que el agente guardó en `validated_fields.pestel` aparece en su factor como «Lo dijiste en el chat… Agregar» (no se inserta solo).
- `main.ts`: vista `pestel` (`#pestel=<proyecto>`), botón «PESTEL» en la barra del proyecto; `inProject()` e `inTool()` reemplazan las listas de vistas repetidas. Usa la misma disposición del árbol (`board-primary-tree`).
- `runtime.py` (`guide`): si la ficha ya está en el tablero (su resumen llega en `shared_context` y empieza por el nombre de la ficha) no se añade la línea «esta ficha apenas empieza»; si el mensaje nombra un factor (`named_part`) se le indica al modelo que pregunte por un elemento nuevo de esa parte. Sin esto, «Preguntarle a Hilo» devolvía «Define el reto…» con el reto ya escrito.
- `chat-cuaderno.css`: en pantallas de hasta 480 px la barra del proyecto oculta los iconos; con cinco herramientas no cabía.

- Segundo rediseño, el mismo día. El usuario dijo que «el PESTEL se ve todo igual» y pidió dos cosas: reutilizar el post-it normal del tablero, con su hoja emergente, y dejar de repetir el estilo del resto de la interfaz, tomando como referencia una lámina de infografía (cintas en flecha, degradados, números en círculo) «manteniendo el formato». Quedó así:
  - Cada elemento es un `.sticky-note` dentro de un `.notes-wall` (clase extra `pestel-wall`), así hereda el aspecto de los Post-its. Ya no se escribe en la columna: «Nuevo post-it», el lápiz o tocar el texto abren `#pestel-dialog`, que usa las clases `note-dialog note-sheet`. En `style.css` los selectores `#note-dialog` de la hoja pasaron a `:is(#note-dialog,#pestel-dialog)`.
  - Campos de la hoja: texto, «¿Qué es para tu reto?» (Oportunidad, Amenaza, Aún no sé), prioridad y fuente. El papel cambia de color en vivo: amarillo, verde o rosado.
  - Cada post-it se guarda al cerrarlo (`autosave`), igual que en el tablero; también al cambiar la estrella, al quitar una nota y al salir del campo del reto. Sin reto no se guarda (el servidor lo exige) y el estado dice «Escribe el reto para guardar».
  - Columnas, pasos, reto y resumen usan degradados y cintas; el encabezado de la vista sigue igual al del árbol.
  - Colores: la primera versión tenía un degradado distinto por factor y el usuario la encontró «muy colorida». Pidió usar los colores de la página y otro color solo si es necesario. Los pasos, el reto y el resumen usan el azul de la página (`--g1:#294eb8`, `--g2:#5f88ec`) y tinta. Al verlo todo azul aclaró que «PESTEL sí mantiene los colores que estaban antes»: las seis columnas conservan un degradado por factor (variables en `.pestel-factor[data-factor]`, que no llegan al resumen). En los post-its el color significa algo: verde oportunidad, rosado amenaza y amarillo de resaltador para lo prioritario.

**No implementado:**

- Diagnóstico del PESTEL (el árbol sí lo tiene) y reordenar elementos.
- Los elementos que se agregan en la vista no pasan a `validated_fields`: son borrador del equipo, como el árbol.
- Puntaje de impacto o matrices: la ficha no los pide y no hay evidencia de que ayuden a un principiante.
- Sin probar en Windows. Sin commit.


## Vista propia del Mapa de empatía (11 oct 2026, Linux)

Cuarta herramienta con interfaz propia y primera de la etapa 3. Igual que con el PESTEL, el usuario pidió investigar antes si había una forma interactiva distinta a la tradicional. No hay estudios que comparen formatos; sí hay respaldo del método (un ensayo con 120 estudiantes de enfermería) y una versión de 2017 del propio autor (Dave Gray) que cambia los bloques, sin prueba de que sea mejor. Se construyó la forma tradicional de la ficha `knowledge/tools/mapa_empatia.md`. La ficha sigue marcada como borrador: si cambian sus bloques, cambia la vista.

**Implementado** (314 pruebas pasan, ruff limpio, `tsc` y build correctos; probado en el navegador en 1440×900 y 375×812 con datos de prueba):

- `empathy_map.py`: `EmpathyMapUpdate` con el usuario y los seis bloques (`piensa_siente`, `ve`, `oye`, `dice_hace`, `dolores`, `necesidades`). Cada nota: texto, `basis` (vacío, `observado` o `supuesto`) y fuente opcional. Tope de 8 por bloque. `context_lines()` resume el mapa para el agente y dice qué es observado y qué supuesto.
- `sharing.py`: tabla `project_empathy_maps`. El guardado por versiones de PESTEL y mapa pasó a dos funciones comunes, `_board()` y `_save_board()`; el árbol conserva las suyas.
- `web.py`: `GET` y `PUT /api/projects/{id}/empathy-map`; el resumen entra a `shared_context`.
- `frontend/src/empatia.ts` y `empatia.css`: `EmpathyController`. La vista lleva las clases `pestel-view empathy-view` y reutiliza de `pestel.css` la caja, los pasos, la cinta del usuario, los post-its, el botón de agregar y la sugerencia del chat. Lo propio es el mapa: el bloque 01 arriba, 02 y 03 a los lados de la persona (un círculo con la descripción del usuario), 04 debajo y dolores y necesidades al final. Con el chat abierto o en celular pasa a una columna en el orden de la ficha.
- Hoja emergente `#empathy-dialog`, con las mismas clases de la hoja de post-it (`:is(#note-dialog,#pestel-dialog,#empathy-dialog)` en `style.css`). Campos: texto, «¿De dónde sale?» (Lo observé o me lo dijeron, Lo supongo, Aún no sé) y fuente. Papel verde observado, naranja supuesto, amarillo sin marcar.
- Lo único que se añadió a la forma tradicional es esa marca de observado o supuesto: llenar el mapa con suposiciones es la falla más documentada del método y la ficha ya pide anotar «lo que sabes/observas».
- Enlace con el chat igual al del PESTEL: «Preguntarle a Hilo» envía «Quiero seguir con el mapa de empatía: bloque «…».»; los datos de `validated_fields['mapa-empatia']` aparecen como sugerencia (`esfuerzos_N` en Dolores y `resultados_N` en Necesidades).
- `runtime.py`: `named_part` reconoce también «bloque …»; en `grounded_verdict` el nombre de un bloque de la ficha que lleva signos de interrogación (en negrilla en la ficha, como «¿Qué oye?») no cuenta como segunda pregunta. Sin esto el agente degradaba en este mapa.
- Barra del proyecto: botón «Empatía». En pantallas de hasta 700 px la fila de herramientas se desliza de lado.
- Sin tira de pasos: la primera versión traía la del PESTEL con tres pasos y el usuario preguntó si era necesaria. Se quitó: la ficha del mapa no tiene una secuencia numerada y la tira repetía lo que ya se ve (el usuario escrito, el contador de cada bloque y el color de cada post-it). En el PESTEL sí se conserva, porque corresponde a los cuatro pasos de su ficha.

**No implementado:**

- `pestel.ts` y `empatia.ts` son casi iguales; conviene sacar un controlador común antes de la siguiente herramienta con tablero.
- Las clases compartidas siguen llamándose `pestel-*` aunque las usan las dos vistas.
- Las notas del mapa no pasan a `validated_fields`: son borrador del equipo.
- Sin probar en Windows. Sin commit.


## Vista propia del Customer Journey Map (11 oct 2026, Linux)

Quinta herramienta con interfaz propia. Antes se analizaron las quince fichas para decidir cuáles necesitan vista (criterio: la entrega es una estructura de varias partes que hay que ver junta). Necesitan: Customer Journey, Lean Canvas, Propuesta de valor y una sola vista «Priorizar ideas» para Matriz y MoSCoW. Con algo pequeño: Ficha de hipótesis (formulario) y Arquetipo (dentro del mapa de empatía). No necesitan: SCAMPER, SIT, 6 sombreros y Trabajo de campo.

Investigación pedida por el usuario, en dos partes:

- Forma: no hay estudios que comparen formatos de journey map. La curva de emoción es práctica extendida, no resultado medido. Sí hay evidencia de que los mapas tratan todos los puntos de contacto como igual de importantes y no lo son (Rosenbaum y otros, 2017), de ahí la marca de etapa crítica, que la ficha también pide.
- Agente: tres usos. Generar el mapa solo (descartado: Nielsen Norman Group repitió tres estudios con usuarios simulados y los encontró demasiado superficiales); ordenar notas reales de entrevistas (posible, sin medición seria); y facilitar con preguntas (el mejor respaldado, en otra tarea: 39 de 42 personas diseñaron mejor un experimento guiadas por un agente que con una hoja). El usuario pidió hacer el tercero ahora y el segundo después.

**Implementado** (328 pruebas pasan, ruff limpio, `tsc` y build correctos; probado en el navegador en 1440×900 y 375×812, incluido el ida y vuelta con el modelo real):

- `journey.py`: `JourneyUpdate` con usuario, escenario y hasta 8 etapas en orden. Cada etapa: nombre, `emotion` (0 sin marcar, 1 a 5), `critical` y cuatro filas de notas (`acciones`, `contacto`, `dolores`, `oportunidades`, hasta 6 cada una). `context_lines()` le dice al agente qué tiene y qué le falta a cada etapa («Puntos de contacto: sin anotar»).
- `sharing.py` y `web.py`: tabla `project_journeys`, `GET` y `PUT /api/projects/{id}/journey`, y el resumen en `shared_context`.
- `frontend/src/journey.ts` y `journey.css`: `JourneyController`. Diseño pedido con cuatro referencias y la consigna «diferente pero que no se despegue»: tarjeta azul con la persona y el escenario a la izquierda, y a la derecha una columna por etapa, encadenadas con flechas, como los días de una agenda. Las filas se alinean entre columnas con `subgrid`. La etapa crítica oscurece su cabecera. En la fila de emoción la altura de la cara es el nivel y un SVG une las caras con una línea punteada (`drawCurve`, se recalcula con `ResizeObserver`). Conserva la caja y el encabezado de `pestel.css`, los post-its y la hoja emergente (`#journey-dialog`); el papel sigue a la fila: amarillo, azul, rosado, verde. En celular cada etapa es una tarjeta con sus filas rotuladas y sin curva.
- Método con agente (facilitar con preguntas): «Preguntarle a Hilo» en una etapa envía «Quiero seguir con el customer journey: etapa «…».» y el agente pregunta por lo que le falta a esa etapa. Lo que la persona responde en el chat se ofrece en esa etapa como «Lo dijiste en el chat… Pasarlo a un post-it» (`noteChatMessage`, llamado desde `sendMessage`). La fila sugerida sale de la última pregunta del agente (`askedLane`) y se puede cambiar en la hoja. Nada entra al mapa sin aceptarlo. Esto lo hace el navegador, no el modelo: esta ficha no tiene `template_fields`.
- `runtime.py`: `named_part` reconoce también «etapa …».
- Barra del proyecto: botón «Journey» (ya son siete). La vista se abre sin el chat al lado porque necesita el ancho.

**No implementado:**

- Revisión del recorrido por reglas (etapa sin emoción, dolor sin oportunidad, ninguna etapa crítica).
- Agrupar las herramientas de la barra en un menú.
- La sugerencia del chat vive en memoria del navegador: se pierde al recargar.
- Sin probar en Windows. Sin commit.


## Customer Journey: notas de entrevista (método 2, 11 oct 2026, Linux)

Lo pidió el usuario al terminar la vista. El agente lee un trozo de notas o transcripción y propone post-its; la regla que importa está en código: una frase solo se propone si está literal en el texto pegado.

**Implementado** (340 pruebas pasan, ruff limpio, `tsc` y build correctos; probado en el navegador con el modelo real):

- `journey_extract.py`: `NotesRequest` (20 a 1.800 caracteres por tanda, por el tamaño del modelo local), `extraction_prompt`, `extraction_model` (salida restringida: etapa es un número que existe, fila es una de las cuatro, máximo 8 frases) y `grounded_quotes`, que busca cada frase en el texto original y devuelve la versión tal como está escrita. Tolera diferencias de espacios, mayúsculas y comillas o puntos en los bordes; descarta la que cambió una palabra, la de menos de tres palabras y la que pasa de 240 caracteres. Las repetidas y las que ya son un post-it del mapa se omiten sin contarlas como error.
- El esquema pide un campo `moment` antes de `stage` (qué está haciendo la persona en ese momento). Sin él, el modelo repartía las frases en orden, una etapa tras otra: en la prueba acertó 2 de 6 etapas; con él, 6 de 6. El prompt lleva además hasta tres notas ya anotadas de cada etapa.
- `direct_runtime.py`: rol `journey_extractor` (900 tokens de salida) y `extract_journey()`.
- `web.py`: `POST /api/projects/{id}/journey/extract`. No guarda nada. Exige que el recorrido tenga etapas (409). Si el modelo está ocupado con el chat o no responde, devuelve `model_status` `ocupado` o `no_disponible` con la lista vacía, igual que el diagnóstico del árbol.
- Interfaz (`journey.ts`, `journey.css`, `#journey-notes-dialog`): botón «Pegar notas de entrevista» en la tarjeta de la persona. La hoja tiene dos pasos: pegar el texto, y revisar las propuestas. Cada propuesta muestra la frase, deja cambiar etapa y fila, y tiene «Agregar» y «Descartar»; toma el color del papel de su fila. Al agregar se guarda sola. «Pegar otro trozo» vuelve al primer paso.
- Medido con el modelo real: 6 frases literales de 6 en unos 5 s, todas en su etapa y fila correctas, sobre notas de 370 a 640 caracteres. Es una observación con dos textos de prueba, no una evaluación.

**No implementado:**

- Las notas no se guardan ni queda registro de qué frase salió de cuál entrevista; el post-it es solo texto.
- Un texto más largo que 1.800 caracteres hay que pegarlo por partes a mano.
- El modelo tiende a copiar oraciones completas; no parte una oración con dos ideas.
- Sin probar con transcripciones reales, que traen muletillas y cortes.


## Prueba de todas las herramientas en un proyecto y arreglos de flujo (11 oct 2026, Linux)

El usuario pidió probar todas las herramientas sobre un proyecto y dejarlo guardado en su cuenta local para verlo completo. Informe: `tesis/pruebas-herramientas-2026-10-11/INFORME.md`. Quedó el proyecto «Academia de programación para niños» en los datos de Linux (`~/.local/share/RutaDIA`): 37 intercambios, árbol, un análisis de 5 porqués cerrado e incorporado, PESTEL, mapa de empatía, Customer Journey, 4 post-its y 2 tareas. Se creó con `prueba_completa.py`, que abre una sesión temporal del usuario con `AuthStore.create_session` y la cierra al terminar; no usa su contraseña. La primera versión del proyecto, hecha antes de los arreglos, se borró por la API y se rehízo.

Esta prueba encontró fallos que las baterías no veían, porque allá cada pregunta empieza en un cuaderno limpio y aquí cada turno hereda el estado del anterior.

**Implementado** (361 pruebas pasan, ruff limpio; pruebas nuevas en `tests/test_tool_flow.py`):

- `runtime.py`, `keeps_active_tool`: una respuesta no cambia de ficha. Si el Orquestador elige otra ficha, se conserva la que está en curso salvo que la persona la nombre o pida cambiar (`_SWITCH_REQUEST`: «necesito», «ahora quiero», «pasemos»…).
- `resolve_kind`: el modelo no puede recomendar con una ficha en curso; su «explicacion» solo vale si el mensaje trae «?»; una señal clara de pedido ajeno (`_OFF_TOPIC`) basta aunque el modelo diga «trabajo»; un agradecimiento corto (`is_thanks`) recibe respuesta fija.
- `knowledge.py`, `prompt_card`: una ficha de más de 7.000 caracteres se le pasa al modelo con las secciones que quepan, en orden, y una nota de cuáles se omitieron. `trabajo_de_campo.md` (26 mil caracteres) rebasaba la ventana de 8.192 tokens y el turno fallaba. `card_section("what")` acepta «TL;DR» y conserva las listas.
- `grounded_verdict`: la pregunta repetida ahora le indica al reintento el paso siguiente de la ficha (`next_step_hint`); también se detecta una instrucción repetida; pedir el paso siguiente al que se acaba de responder no cuenta como «paso adelantado» (`follows_previous_step`).
- `langgraph_workflow.py`, `_degrade`: si el único hallazgo es la pregunta repetida, el mensaje es «Ya tengo tu respuesta…» con el paso que sigue, no la ficha entera.
- Prompt del Metodólogo: ante «no sé», preguntar qué revisar o a quién preguntar. Se había perdido al acortar el prompt y en cinco porqués hacía repetir la pregunta.

**No implementado / observado:**

- El cuaderno avanza de etapa solo por usar una ficha de una etapa posterior (pasó de la 1 a la 6 conversando). Hay aviso, pero no se le pregunta a la persona.
- En las fichas sin tablero ni campos, lo que la persona responde queda solo en la conversación.
- Voseo ocasional del modelo («Completá»), y preguntas confusas en 6 sombreros.
- Los dos últimos arreglos (degradación por repetición y paso siguiente) tienen prueba automática, no una corrida completa nueva.


## Pruebas del día siguiente: partir de lo que la persona respondió (12 oct 2026, Linux)

El usuario pidió probar lo corregido el 11 de octubre. Informe y resultados: `tesis/pruebas-herramientas-2026-10-12/`. La misma conversación de 37 intercambios se corrió tres veces con el modelo real, **en proceso y con datos temporales** (`prueba_aislada.py`: `TestClient` sobre `create_app` con `memory_path`, `checkpoint_path` y `audit_path` en una carpeta temporal y una cuenta desechable), sin tocar la cuenta la cuenta del usuario. `repetir_turnos.py` repite turnos sueltos con el historial de una corrida y muestra los hallazgos de cada intento.

Los dos arreglos que solo tenían prueba automática (degradación por pregunta repetida y paso siguiente) quedaron confirmados: corrida 1, con el código del día anterior, 33 aprobados, 4 respuestas fijas, 0 rechazos. Al leer las respuestas apareció otra debilidad: en los turnos donde la persona **responde**, el modelo no partía de lo dicho y volvía a pedirlo con otras palabras o pedía confirmarlo.

**Implementado** (386 pruebas pasan, ruff limpio; pruebas nuevas en `tests/test_tool_flow.py`):

- `runtime.py`, `answered_block`: cuando la persona responde dentro de la ficha en curso (sin «?», tipo `trabajo`, misma ficha, sin análisis bloqueado), el prompt del Metodólogo lleva un bloque con su pregunta anterior, la respuesta y el paso que sigue en la ficha. Si la respuesta ya cubre también ese paso, la pista salta al siguiente. `next_step_hint` acepta `minimum` (palabras compartidas para dar un paso por cubierto).
- `state_for_new_card`: al pasar a otra ficha en un turno de trabajo, el Metodólogo ya no ve sus propias preguntas de la ficha anterior (seguía preguntando por las «alegrías» del canvas al abrir el arquetipo); lo que dijo la persona se conserva. No se aplica si piden explicar la ficha ni si el mensaje señala la conversación («esta causa»). Se probó contra la alternativa de añadir un aviso al prompt en los 14 turnos de cambio de ficha: el aviso dejó 1 rechazo y este recorte, ninguno.
- `asks_to_confirm_answer`: hallazgo `repeated_question` cuando la pregunta solo devuelve lo que la persona acaba de decir o pide confirmarlo («¿Puedes confirmarlos…?»). No cuenta un «¿por qué…?», una pregunta abierta, ni una pregunta que añade un término de la ficha (pedir clasificar en Must la lista que dio la persona es válido; la primera versión lo rechazaba).
- `drop_filler` conserva la frase que cita la ficha (la plantilla «Creemos que…»), que antes se iba como relleno.
- `grounded_verdict`: más verbos de las fichas cuentan como instrucción («Evalúa», «Ubícalas», «Aplica», «Reformula»…) y una pregunta escrita entera en negrita cuenta como pregunta.
- `langgraph_workflow.py`, `_degrade`: si pidieron explicar la ficha y la pregunta del modelo no pasa, se entrega la explicación literal de la ficha con «¿Con qué parte de la ficha quieres que te acompañe?». Antes, una ficha sin «Cómo se usa» (trabajo de campo) caía en «No puedo confirmar esa orientación…».

**Resultado.** Corrida 3, con todo lo anterior salvo los dos últimos ajustes: 32 aprobados, 4 respuestas fijas y 1 rechazo (MoSCoW, por la primera versión del detector de confirmación). Ese turno y otros tres se repitieron después del ajuste y pasaron. No se corrió una cuarta conversación completa tras los dos últimos ajustes.

**No implementado / observado:**

- El modelo a veces le habla al arquetipo como si fuera la persona usuaria («Carolina, ¿qué frustración te impide…?»).
- En trabajo de campo la pregunta inicial se va hacia el mapa de empatía; la guía es larga (26 mil caracteres, se recorta a 7.000) y sigue en borrador.
- Preguntas pobres que el filtro no detecta: «¿Quieres aplicar SIT para generar ideas?», «¿Está claro ese umbral?».
- Con modelo de 4B cada cambio del prompt mueve otras respuestas: entre corridas la calidad de un mismo turno sube o baja. Los conteos de aprobados no distinguen una pregunta buena de una pasable.
- El proyecto de demostración guardado en la cuenta del usuario conserva las respuestas del agente del 11 de octubre.



## Límite de intentos de acceso y tope de tamaño de petición (12 oct 2026, Linux)

El usuario dio el visto bueno a los tres hallazgos de `tesis/seguridad-2026-10-12/INFORME.md`.

**Implementado** (391 pruebas pasan, ruff limpio; pruebas nuevas en `tests/test_auth.py`):

- `auth.py`, `AttemptLimiter`: ventana deslizante en memoria (`attempt(clave)` anota el intento y devuelve 0, o los segundos que faltan). Un intento rechazado no se anota, así que no alarga la espera.
- `web.py`: `login_attempts` (5 por minuto por usuario, en minúsculas y sin espacios; se borra al acertar) y `access_attempts` (20 por minuto por dirección de origen, compartido entre `/api/auth/login` y `/api/auth/register` porque los dos cuestan un hash). Al pasar el tope: 429 con `Retry-After` y el texto fijo `TOO_MANY_ATTEMPTS`. El texto es fijo porque la interfaz traduce los errores de acceso por coincidencia exacta (`auth-language.ts`, clave `tooManyAttempts`).
- `auth.py`, `_HASHING`: semáforo que deja correr dos `scrypt` a la vez. Es lo que acota la memoria; el contador solo acota cuántos intentos se aceptan.
- `LoginRequest`: `username` hasta 40 y `password` hasta 128, igual que el registro y que `reset_local_password.py`. Antes no tenían tope.
- `web.py`, `BodyLimitMiddleware` (`MAX_BODY_BYTES`, 1 MB): 413 por `Content-Length` o, si el cuerpo llega por trozos, al pasar el tope mientras se lee.
- README: sección «Protección del acceso» y el límite conocido de datos sin cifrar.
- Medido contra un `uvicorn` real con datos temporales en otro puerto: 60 inicios de sesión simultáneos dan 20 respuestas 401 y 40 respuestas 429 en 1,6 s, y el pico de memoria del proceso pasa de 186 a 275 MB. Un cuerpo de 2 MB da 413 con `Content-Length` y por trozos. No se midió la misma ráfaga con el código anterior.

**No implementado / decidido:**

- Los datos en reposo siguen sin cifrar. Se deja como límite conocido (README); no se añadió SQLCipher.
- No hay espera creciente: el tope es el mismo en cada ventana.
- La interfaz solo escucha en `127.0.0.1`, así que todas las peticiones llegan de la misma dirección y el cupo por origen es un cupo para toda la computadora. Si algún día se publica detrás de un proxy, hay que decidir de dónde sale la dirección real; hoy no se lee `X-Forwarded-For`.
- Quien conozca un nombre de usuario puede dejarlo sin entrar un minuto con 5 intentos fallidos.
- Los contadores no sobreviven a un reinicio.


## Revisión de seguridad y correcciones (12 oct 2026, Linux)

El usuario pidió revisar la seguridad de Hilo. Informe: `tesis/seguridad-2026-10-12/INFORME.md`. Se revisó el código (`auth.py`, `sharing.py`, `web.py`) y se probó contra la instancia local con cuentas de prueba que luego se borraron (la cuenta del usuario y sus tres proyectos quedaron intactos).

**Lo que ya estaba bien:** contraseñas con `scrypt` y sal por usuario; comparación en tiempo constante; token de sesión de 256 bits guardado como SHA-256, caduca a 12 h; cookie `HttpOnly` + `SameSite=Strict`; bloqueo de peticiones de otro origen; consultas parametrizadas; un usuario no puede leer ni escribir el proyecto de otro (se revisa en el endpoint y otra vez en el SQL); sin sesión, 401.

**Implementado** (392 pruebas pasan, ruff limpio; pruebas en `tests/test_auth.py`):

- `auth.py`, `AttemptLimiter`: ventana deslizante en memoria. `web.py` limita el acceso a 20 intentos por minuto por origen (registro y login comparten cupo) y a 5 intentos fallidos por minuto por cuenta; responde 429 con `Retry-After`. Un login correcto borra los fallos de esa cuenta.
- `auth.py`, `_HASHING`: como máximo dos `scrypt` a la vez (cada uno usa 64 MB). Sin este tope, muchas peticiones de login simultáneas agotaban la memoria.
- `web.py`, `BodyLimitMiddleware`: cuerpos de más de 1 MB → 413, también los que llegan por trozos sin `Content-Length`. `LoginRequest` limita usuario (40) y contraseña (128).
- `web.py`, `restrict_data_dir`: al arrancar, en Linux la carpeta de datos queda en 700 y sus archivos en 600. Antes estaban en 775/644 y otro usuario del equipo podía leer cuentas, hashes y cuadernos. En Windows no hace nada (`%LOCALAPPDATA%` ya es privada). Si la carpeta está en un disco sin permisos POSIX, solo deja un aviso.

**No implementado:**

- Los datos no están cifrados en disco (las contraseñas sí van con hash). Para cifrarlos haría falta SQLCipher y guardar la clave en algún lado; en un equipo personal es más sensato el cifrado de disco del sistema (BitLocker, LUKS). Queda como límite conocido.
- El limitador vive en memoria: se reinicia al reiniciar la interfaz. Basta para una app local.
- `sessions.user_id` no tiene `ON DELETE CASCADE`: borrar un usuario con sesiones abiertas falla. Hoy no hay función de borrar cuenta.
- No se hizo ninguna prueba de denegación de servicio. El riesgo de sobrecarga se trató en el código (límite de intentos, tope de hashes simultáneos, tope de tamaño).

## Limpieza del repositorio público (16 oct 2026, Linux)

El usuario pidió limpiar el repo antes de subirlo. El repositorio es público
(`github.com/crparra4/sma-metodologias-innovacion`).

**Hecho en el árbol de trabajo** (cero menciones de la organización aliada o de la persona experta; 392 pruebas pasan):
- Las 13 fichas de `knowledge/tools/` y `knowledge/source/ruta_dia.md`: la nota de borrador dice
  «validar con la persona experta en metodología»; el título de la ruta y la ficha SIT ya no nombran
  a la organización aliada.
- `.env.example` revisado: la clave es un marcador local, no una credencial externa.
- `.gitignore` cubre `.env`, `*.sqlite3`, `*.gguf`, claves; `contexto/` no está versionado.

**NO hecho — requiere decisión del usuario y hacerse desde Windows:**

1. **`.git` es de solo lectura desde Linux** (disco NTFS): el commit, la reescritura y el push
   se hacen desde Windows.
2. **El historial público todavía tiene los nombres.** GitHub solo tiene `main` (5 commits, firmados
   con el correo noreply); sus fichas aún nombran a la organización y a la persona. La rama `master` existe solo
   en el equipo: son 5 commits viejos, sin historia común con `main`, firmados con el correo
   corporativo. Ese correo **no está publicado**.
3. **Guion listo:** `D:\hilo\limpieza-historial\limpiar-historial.ps1` (fuera del repositorio, con
   `mailmap.txt` y `expresiones.txt`). Confirma los cambios pendientes, guarda un respaldo espejo,
   reescribe el historial con `git-filter-repo` en una copia aparte y verifica que no quede nada.
   **No sube nada**: muestra el `git push --force-with-lease` para que el usuario decida. Se ensayó
   en Linux sobre un clon temporal: 0 archivos y 0 correos con los nombres en las 10 revisiones; el
   árbol final queda igual al de trabajo. El guion de PowerShell no se pudo ejecutar en Linux.
4. El force-push reemplaza el historial público; GitHub puede conservar un tiempo los commits viejos
   accesibles por su identificador. Para borrarlos del todo hay que pedirlo al soporte de GitHub o
   borrar y recrear el repositorio.
5. **Ramas (decisión del usuario, 16 oct):** `main` (estable; la que se congela para la validación),
   `develop` (desarrollo) y `staging` (pruebas antes de pasar a `main`). El guion las crea desde el
   `main` ya limpio, para no publicar el historial viejo en ramas nuevas. Ensayado en un clon: las
   tres ramas sin coincidencias. Pendiente: subirlas junto con el push de `main`.

**Resultado (16 oct, hecho desde Linux):** se dio escritura a `.git` (`chmod -R u+w .git`), se
confirmó el trabajo pendiente en `main` y se reescribió el historial con `git-filter-repo` en
`D:\hilo\limpieza-historial\repo-limpio`. El usuario hizo el push desde ahí: GitHub tiene `main`,
`develop` y `staging` en `c27bcc3`, con 6 commits publicados, 0 archivos con los nombres y solo el
correo noreply. La carpeta `proyecto` quedó alineada con `git reset --hard origin/main`.
- Un push hecho por error desde `proyecto` volvió a subir un momento el historial viejo; se corrigió
  repitiendo el push desde `repo-limpio`. Desde ahora se trabaja en `proyecto`, en `develop`.
- La rama local `master` conserva los 5 commits viejos con el correo corporativo: **no subirla**.
- Respaldo del historial anterior: `D:\hilo\limpieza-historial\respaldo-20261016-1259.git`.
- GitHub puede mantener un tiempo los commits viejos accesibles por su identificador; para borrarlos
  del todo hay que pedirlo al soporte de GitHub.

