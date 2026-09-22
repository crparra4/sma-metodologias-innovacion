# Interfaz local de Ruta DIA

La pantalla permite conversar con Qwen3.5-4B, observar el grafo real de LangGraph y consultar la
memoria de cada cuaderno. FastAPI sirve la API y el frontend compilado por Vite en la misma dirección.
Solo escucha en `127.0.0.1`; la clave del modelo permanece en el backend.

## Iniciar

En PowerShell, desde `prototipo`:

```powershell
.\scripts\start_interface.ps1
```

El comando inicia Qwen si hace falta, construye la interfaz si no existe y abre
`http://127.0.0.1:8787`. Los procesos auxiliares se ejecutan sin ventanas adicionales.
Se puede usar `-NoBrowser` o `-Port 8788`.

Al abrir Hilo, crea una cuenta local con nombre, usuario y contraseña. La primera cuenta conserva
los proyectos previos; las siguientes tienen memoria y checkpoints propios. Para cambiar de cuenta,
abre tu perfil en el menú lateral y pulsa «Cerrar sesión». La sesión caduca a las 12 horas; las
contraseñas no se guardan en texto claro y la cookie de sesión es HttpOnly y SameSite Strict.
Los archivos de cuentas y sesiones están en `auth.sqlite3`, junto al SQLite de los cuadernos;
los datos de cuentas adicionales están en `users/<id>/` dentro de la misma carpeta local.
Si olvidas una contraseña, puedes restablecerla desde la computadora que guarda la base:
`.\.venv\Scripts\python.exe scripts/reset_local_password.py NOMBRE_DE_USUARIO`.
El comando pide la nueva clave sin mostrarla, crea una copia de `auth.sqlite3` y cierra las
sesiones anteriores de esa cuenta. Los proyectos y mensajes se conservan.

Para detener solo la interfaz:

```powershell
.\scripts\stop_interface.ps1
```

Para detener también Qwen:

```powershell
.\.venv\Scripts\python.exe scripts/local_model.py stop
```

## Probar

1. En «Inicio» puedes ver todos tus proyectos como carpetas, buscarlos y ordenarlos por nombre
   o última actualización. Cada tarjeta muestra la etapa, el número de mensajes y la fecha de actualización.
2. Abre una carpeta o pulsa «Nuevo proyecto»: nombre y reto o pregunta de negocio son obligatorios.
   Entorno y objetivo son opcionales. «Más detalles» incluye hipótesis, criterio de aceptación,
   ambición 10X y etapa inicial. Elige un color y consulta la vista previa antes de crear el cuaderno.
3. Escribe el reto o usa una sugerencia para completar el campo de mensaje.
4. Envía con Enter o el botón de enviar.
5. Observa los agentes activos, duraciones, posibles reintentos y veredicto final.
6. Consulta la ficha utilizada y los campos aprobados en el panel derecho.
7. Recarga: la conversación y sus veredictos se recuperan de SQLite. Pulsa «Inicio» para volver
   a todos los proyectos. Las direcciones `#inicio` y `#proyecto=…` permiten reabrir la misma vista.

### Árbol de problemas interactivo

Dentro de un proyecto, la barra azul inferior permanece visible y «Árbol» cambia el panel
principal del chat por el árbol. El árbol puede ocupar todo el espacio o compartir el tablero
con **Post-its** o **Agentes**; solo se muestran dos paneles a la vez. Al pulsar de nuevo «Árbol»,
se vuelve al chat. En pantallas estrechas, el panel complementario aparece debajo del árbol.

El árbol contiene efectos, problema central y causas. Cada
tarjeta admite texto y un origen opcional; el origen registrado **no** convierte la afirmación en
evidencia verificada. Se pueden añadir, reordenar, arrastrar, cambiar de zona y quitar tarjetas.
«Guardar árbol» conserva una versión común en `auth.sqlite3`. Quien tiene permiso de lectura
puede consultarlo; propietario y editores pueden modificarlo. Si otra persona guardó antes,
la versión antigua se rechaza con 409 y el borrador local permanece visible hasta recargar.
Al abrir un árbol vacío, el reto inicial del proyecto se propone como borrador del problema
central. El árbol guardado se entrega al agente como contexto compartido explícitamente
marcado «no verificado»; «Revisar con Hilo» prepara una pregunta en el chat para que la
persona decida si enviarla. La ruta `#arbol=<id>` reabre el tablero del proyecto.

La etiqueta «Último abierto» identifica el proyecto recordado en ese navegador. El color pertenece
al usuario: azul, amarillo, verde, naranja, morado o gris. «Proyecto» es el nombre
en pantalla de cada cuaderno persistente existente; esta vista utiliza los mismos datos de SQLite.
Los proyectos nuevos se crean únicamente cuando se envía el formulario.

«Editar cuaderno», dentro del proyecto, permite cambiar el color y completar o corregir el contexto
sin modificar el historial, la etapa de trabajo ni los campos verificados. Los cuadernos anteriores
siguen disponibles y pueden completar su contexto al editarlos.

«Contexto del proyecto» muestra declaraciones iniciales, separadas de «Memoria del cuaderno».
Los agentes reciben ese contexto en cada turno. Las hipótesis son supuestos por contrastar; los
criterios y la ambición son metas, nunca evidencia de causas o resultados confirmados.
El contexto inicial no se copia automáticamente a los campos metodológicos verificados.
Los campos obligatorios muestran errores debajo de la entrada y conservan el texto ya escrito.
El primer campo incompleto recibe foco; el contorno queda completo dentro del área desplazable.

«Eliminar este cuaderno» pide una confirmación dentro de la pantalla y elimina historial, campos
y checkpoints del cuaderno seleccionado. No borra las fichas metodológicas.

## Desarrollo

```powershell
$env:NODE_USE_SYSTEM_CA = '1'
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
.\.venv\Scripts\ruta-dia.exe web
```

Para recarga automática del frontend, deja el backend activo y ejecuta
`pnpm --dir frontend dev`. Vite reenvía `/api` al backend local.

## Eventos y memoria

`POST /api/chat` transmite eventos SSE obtenidos de `graph.stream()` con modos `tasks` y `updates`.
La interfaz recibe inicio/fin de nodos, handoff y verificación. El texto candidato y el razonamiento
interno del modelo no se transmiten. La respuesta se publica después de verificarla y guardar el
intercambio en SQLite. Una generación ocupa el modelo a la vez; solicitudes concurrentes reciben 409.
Si el navegador se cierra durante un turno, el backend continúa y guarda el resultado: puede
recuperarse volviendo a abrir el cuaderno.

Cada nuevo turno limpia el veredicto y los datos técnicos de la ejecución anterior, conservando
únicamente la memoria de negocio recuperada. El RAG vectorial sigue pendiente: esta entrega conserva
la recuperación de fichas mediante índice y herramienta autorizada.

Cuando el usuario pide explícitamente una herramienta habilitada, su selección tiene prioridad
sobre la clasificación del modelo. Si la orientación es válida pero el modelo propone guardar
datos ausentes del mensaje actual, el veredicto es «con observaciones» y ninguna actualización
de campos se incorpora a la memoria. Errores en la orientación siguen provocando rechazo y reintento.

## Límites

Es una interfaz de pruebas local con cuentas separadas en esta computadora. El grafo refleja
ejecución real, pero no garantiza que un veredicto aprobado sea metodológicamente perfecto. La
precisión de Qwen3.5-4B requiere evaluación humana y pruebas de progresión adicionales.

## Validación de esta entrega

- 63 pruebas automáticas aprobadas; Ruff sin hallazgos y build TypeScript/Vite correcto.
- Consulta real de cinco porqués: respuesta aprobada después de un reintento.
- Cambio explícito a PESTEL: selección controlada y último turno aprobado en 19 segundos.
- Recuperación después de recargar el navegador y reiniciar el servidor de la interfaz.
- Pantallas de 1440 × 900 y 390 × 844, sin desbordamiento horizontal.
- El cambio de tamaño conserva visible el final de la conversación cuando ya se estaba al final.
- Arista de reintento sin resaltar en el turno final, que utilizó un solo intento.

## Validación de Inicio

- Build TypeScript/Vite correcto y detector visual sin hallazgos.
- Búsqueda con coincidencia y sin resultados; orden por nombre y actualización.
- Apertura de un proyecto existente con historial y retorno a Inicio desde el menú móvil.
- Creación real de un proyecto temporal en etapa 2; sus datos de prueba se retiraron después.
- Capturas de escritorio y móvil revisadas: disposición `ship`, sin correcciones materiales.

## Validación de contexto y color

- Migración de cuadernos anteriores sin perder su historial ni campos verificados.
- Creación con contexto y amarillo; edición a verde y recuperación después de recargar.
- El contexto llega al grafo y a los prompts. Hipótesis y metas no respaldan hechos confirmados.
- Prueba real PESTEL usando el contexto inicial: pregunta sobre comportamiento de los estudiantes,
  sin solicitar de nuevo el reto; 38,5 segundos, con observaciones y sin guardar campos no respaldados.
- Edición bloqueada durante una generación para conservar un contexto consistente en el turno.
- El cuaderno temporal de prueba fue retirado; los cuadernos existentes se conservan.
- Formulario de escritorio y móvil revisado: `ship`, sin hallazgos materiales pendientes.

## Post-its personales

Al abrir un cuaderno, el panel derecho muestra una pila vertical de Post-its. Pulsa **Nueva nota**
para escribirla, o selecciona un fragmento del chat y pulsa **Guardar selección del chat**.
Cada respuesta también tiene **Guardar en post-it** para llevar el texto completo al editor.
Completa título y texto, elige categoría y color, y pulsa **Guardar post-it**.

Categorías: Idea, Prototipo, Observación, Pregunta, Decisión, Otro. Colores: amarillo, rosa,
azul, verde, morado, naranja. Título: hasta 100 caracteres; texto: hasta 3000. Las notas se
ordenan de más nueva a más antigua. La edición conserva el fragmento original del chat,
consultable en un desplegable. La eliminación requiere confirmación dentro de la nota.

Se guardan en la tabla `notes` de SQLite, por cuaderno, y sobreviven al cierre o recarga.
Son anotaciones personales: no se convierten en campos verificados, no se envían al modelo
y no constituyen RAG vectorial. Eliminar un cuaderno elimina también sus Post-its.

La cabecera del chat deja visible solo el menú de tres puntos a la derecha. Reúne
**Ir a Inicio**, **Ver flujo de agentes**, **Editar cuaderno** y la indicación
**Sesión local**. Ver flujo de agentes también aparece
debajo de las notas y abre el grafo real y sus eventos. Por defecto está cerrado.
En móvil, el menú conserva los nombres completos de las acciones y las notas siguen
apiladas debajo del chat.

API: `GET /api/notebooks/{id}` incluye `notes`; `POST /api/notebooks/{id}/notes` crea;
`PUT /api/notebooks/{id}/notes/{note_id}` edita; `DELETE` en esa misma ruta elimina.
Las operaciones están limitadas al cuaderno correspondiente y al mismo origen de la interfaz.

Validación de esta extensión: 72 pruebas de backend aprobadas, Ruff y compilación TypeScript/Vite
correctos. Prueba manual en navegador: nota escrita, selección real de 43 caracteres, respuesta
completa, edición, categorías/colores, persistencia tras recarga, confirmación cancelada,
validación recuperable y grafo opcional. Capturas de escritorio/móvil en `data/interface-qa/`.

## Calendario y agenda de Inicio

En **Inicio**, debajo de tus proyectos, el calendario lavanda muestra el día actual en verde suave y señala
las fechas con tareas y conversaciones. Pulsa un día para consultar sus tareas o usa **Hoy**
para volver al día actual. Las flechas permiten consultar otros meses.

Pulsa **Nueva tarea**, escribe lo pendiente, elige fecha y hora, asigna importancia alta,
media o baja y, si corresponde, vincúlala a un proyecto. **Guardar tarea** la conserva en tu
computadora. El lápiz permite editarla; la casilla permite completarla o volver a abrirla.
Los filtros **Hoy**, **Próximas** y **Todas** cambian la lista. Próximas incluye las vencidas
para que sigan visibles, con las fechas más cercanas primero.

Cada tarea muestra dos indicadores: prioridad (alta, media o baja) y plazo (vencida, hoy,
mañana o días restantes). Ambos tienen texto y color; una tarea de prioridad baja también
puede estar vencida. La agenda no envía notificaciones ni incorpora las tareas a la memoria
metodológica verificada o a los prompts del modelo.

API: `GET /api/tasks`, `POST /api/tasks`, `PUT /api/tasks/{id}` y `DELETE /api/tasks/{id}`.
Fechas con zona horaria, almacenadas en UTC y presentadas en la hora local del navegador.
Tabla `tasks` en SQLite, con proyecto opcional: borrar el proyecto conserva su tarea sin
asociación. Es una agenda personal local, sin cuentas o calendarios externos.

Validación: 79 pruebas backend y 5 frontend aprobadas; Ruff y build correctos. Prueba manual
de crear, editar, completar/reabrir, validación, persistencia y filtros de calendario. Capturas
en `data/interface-qa/agenda-*.png` y registro de revisión en `agenda-review.md`.
