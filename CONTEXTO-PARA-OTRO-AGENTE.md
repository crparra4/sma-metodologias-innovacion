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
