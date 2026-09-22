# Plan de proyectos compartidos en Hilo

Fecha: 18 de septiembre de 2026. Actualizado: 19 de septiembre de 2026. Estado: primera versión local implementada y probada; las ampliaciones pendientes figuran al final.

## Objetivo

El propietario invita a otra cuenta a acceder a una misma carpeta de proyecto. La persona invitada consulta los avances existentes y las actualizaciones posteriores: fase y etapa, Post-its, memoria compartida, resultados de herramientas y tareas del proyecto. Cada integrante conserva su conversación privada; los agentes reciben el contexto relevante del proyecto mediante una memoria común. Compartir no crea una copia independiente ni implica compartir la contraseña de la cuenta.

## Punto de partida antes de implementar

- `src/ruta_dia_agents/web.py` resuelve memoria y checkpoints según la cuenta autenticada.
- Cada cuenta dispone de almacenamiento local separado; no existe membresía de proyectos ni infraestructura remota de colaboración.
- `src/ruta_dia_agents/memory.py` vincula conversaciones, notas y campos validados a `notebook_id`, actualmente usado como nombre e identificador.
- Las tareas pueden tener `notebook_id` o ser personales. No se debe exponer la agenda completa del propietario al compartir una carpeta.
- Las cuentas actuales tienen usuario y nombre visible; no disponen de correo verificado ni envío de invitaciones por correo.
- El botón Compartir actual comparte o copia un resumen de nombre, fase y etapa. Se sustituirá por la gestión de acceso cuando se implemente esta función.

## Alcance elegido por el usuario

1. Acceso desde cuentas distintas en este mismo computador. No se desplegará un servicio remoto en esta versión.
2. El propietario elige entre Puede ver y Puede editar al invitar. Puede cambiar el permiso o revocarlo después.
3. Los chats son privados por cuenta y proyecto. Ningún integrante ve el chat de otra persona, incluido el propietario.
4. Post-its y resultados de las futuras herramientas de etapas son recursos compartidos.
5. Ambos agentes usan los avances relevantes guardados en una memoria común, sin recibir el historial privado de los demás.

Cada participante entra con sus propias credenciales y ve los proyectos compartidos en su cuenta. Trabajar desde computadores distintos queda para una ampliación posterior. El usuario autorizó la implementación después de esta planificación.

## Experiencia propuesta

1. El propietario pulsa Compartir en la cabecera del proyecto.
2. Un panel muestra el propietario, las personas con acceso y las invitaciones pendientes.
3. Selecciona una cuenta destinataria y el permiso disponible. Para el prototipo se utiliza el usuario existente; invitar por correo requiere ampliar el sistema de cuentas.
4. Se crea una invitación dirigida a esa cuenta. La destinataria inicia sesión con su propia cuenta y acepta o rechaza.
5. Al aceptar, el proyecto aparece en Compartidos conmigo, con propietario y permiso visibles.
6. La invitada abre el mismo proyecto y ve sus avances. Si es lectora, los controles de modificación no están disponibles.
7. El propietario puede cancelar una invitación o retirar el acceso. La persona invitada puede abandonar el proyecto.

La primera versión puede mostrar invitaciones dentro de la aplicación. Correo, notificaciones automáticas y enlaces públicos no se dan por existentes.

## Contenido y límites del acceso

| Elemento | Tratamiento propuesto |
| --- | --- |
| Título, fase, etapa y contexto | Compartidos dentro del proyecto |
| Chat y borradores de cada integrante | Privados por cuenta y proyecto; tampoco se entregan al agente de otra cuenta |
| Avances relevantes guardados | Compartidos como información estructurada del proyecto, con autoría y estado |
| Post-its actuales de la carpeta | Compartidos; avisar de este alcance antes de invitar |
| Memoria verificada y resultados de herramientas | Compartidos, conservando origen y estado de verificación |
| Tareas y calendario de la carpeta | Solo tareas vinculadas al proyecto |
| Agenda personal y otras carpetas | Privadas |
| Credenciales y configuración de cuenta | Privadas |
| Nuevas herramientas | Sus recursos deben pertenecer a un proyecto y aplicar los mismos permisos |

Si posteriormente se necesitan notas privadas dentro de un proyecto compartido, se diseñará una visibilidad explícita. No se mezclará esa ampliación con el primer alcance.

## Permisos propuestos

| Acción | Propietario | Lector | Editor |
| --- | --- | --- | --- |
| Consultar avances y tareas del proyecto | Sí | Sí | Sí |
| Añadir o modificar Post-its y tareas compartidas | Sí | No | Sí |
| Consultar a Hilo en el chat privado propio | Sí | Sí | Sí |
| Guardar avances comunes y modificar herramientas | Sí | No | Sí |
| Invitar, cambiar permisos y revocar acceso | Sí | No | No |
| Eliminar el proyecto | Sí | No | No |
| Abandonar el proyecto | No; requiere resolver propiedad | Sí | Sí |

Transferencia de propiedad, comentarios y permisos diferentes por herramienta quedan fuera del primer alcance.

## Modelo y autorización

- Asignar un identificador estable y único a cada proyecto, separado de su título. Dos cuentas pueden tener proyectos con el mismo nombre.
- Registrar propietario y miembros: proyecto, cuenta, rol y fecha de incorporación.
- Registrar invitaciones: proyecto, remitente, destinatario, permiso, estado y vencimiento. Estados: pendiente, aceptada, rechazada, cancelada o vencida.
- Mantener una sola fuente de datos para cada proyecto. No copiar carpetas completas entre cuentas ni dar acceso a toda la base de datos del propietario.
- Comprobar membresía y permiso en el servidor para cada lectura y modificación: chat, notas, tareas, herramientas, memoria y futuros recursos.
- Separar el estado compartido del proyecto del historial y los checkpoints privados. Cada conversación y checkpoint pertenece a la combinación proyecto + cuenta; ningún agente lee el historial privado de otra cuenta.
- Antes de cada turno, cargar la última versión de la memoria común y el estado del proyecto. La fase, etapa y resultados compartidos no se reemplazan por valores antiguos de un checkpoint privado.
- Registrar autor y fecha de los cambios. La actividad común identifica a su autor, sin publicar el texto de su conversación privada. Los editores pueden modificar las notas y tareas compartidas de la carpeta; no administrar integrantes ni eliminar la carpeta.
- Usar versiones para detectar cambios simultáneos; comunicar el conflicto sin sobrescribir silenciosamente.
- Revisar el permiso nuevamente antes de confirmar una operación prolongada, para respetar revocaciones mientras se procesa un turno.

Un eventual enlace de invitación debe permitir aceptar una invitación con una cuenta autorizada, no abrir públicamente el proyecto. Los tokens tendrán vencimiento y se almacenarán mediante hash.

## Memoria común y chats privados

El proyecto tiene dos espacios de información:

- **Privado:** historial, borradores y checkpoints de la conversación de cada cuenta con Hilo. La membresía de un proyecto no permite acceder a conversaciones ajenas. Los chats anteriores permanecen privados después de compartir.
- **Compartido:** contexto del reto, fase y etapa, avances guardados, decisiones, hallazgos, hipótesis, pendientes, Post-its, tareas y resultados de herramientas.

### Cómo guardar los avances

Propuesta de interacción: el agente identifica un avance relevante y prepara una síntesis breve. El autor revisa y pulsa Guardar avance en el proyecto, pudiendo corregir el texto. Se guarda el avance confirmado, sin publicar la conversación completa. Esta confirmación es una recomendación de producto para preservar la privacidad del chat; no es una decisión ya elegida por el usuario.

Los Post-its creados dentro de la carpeta y los resultados guardados explícitamente en herramientas compartidas son visibles directamente a los integrantes. No necesitan convertirse en un resumen de chat para estar disponibles.

Un avance registra proyecto, contenido, tipo, autor, fecha, fuente compartida cuando exista, estado y versión. Estados sugeridos: propuesta, confirmado o sustituido; una confirmación humana no equivale a verificación factual. Las hipótesis y notas conservan su naturaleza y las evidencias su origen. No se añade información personal o de otras carpetas mediante un resumen automático.

### Qué recibe el agente

Antes de responder, combina el chat privado de su interlocutor con el estado compartido vigente y una selección acotada de avances relevantes, notas y resultados de herramientas. Los Post-its se consideran aportaciones de sus autores, no hechos verificados automáticamente. El historial ajeno no forma parte de esa selección.

Una síntesis común sirve para orientar al modelo, pero los avances y recursos estructurados son la fuente de información. Debe conservar decisiones, contradicciones y pendientes, identificar su versión y permitir rastrear una afirmación a un recurso compartido. Una síntesis desactualizada no puede prevalecer sobre un avance corregido o eliminado.

La sincronización inicial ocurre al abrir la carpeta y antes de cada nuevo turno. Si alguien guarda un avance durante una respuesta, se incorpora al turno siguiente; no se promete modificar una respuesta ya en curso.

### Ejemplo

Ana trabaja en su chat privado y guarda el avance: El reto se centrará en organizar entrevistas con estudiantes. Luis abre su propia conversación y su agente conoce esa definición, pero no ve las preguntas ni respuestas privadas de Ana. Luis agrega un Post-it con una duda y completa una herramienta de etapa; Ana ve esos recursos y su agente los puede utilizar como contexto en el siguiente turno.

### Futuras herramientas de etapas

Los tableros, formularios o ejercicios que sustituyan al chat se vinculan al proyecto, no a una conversación particular. Lectores consultan; editores guardan cambios. Sus resultados alimentan la memoria común con procedencia y estado, aplicando permisos, autoría y versiones desde el principio. Se diseña esta conexión ahora; no se implementan herramientas aún no definidas.

## Ampliación futura: acceso desde distintos computadores

Requiere un servidor común, cuentas compartidas en ese servicio y almacenamiento persistente respaldado. La dirección `127.0.0.1` actual solo apunta al computador de cada persona y no sirve para invitar a alguien desde otro equipo.

Antes de desplegar habrá que definir dónde se guardarán los proyectos, cómo se migrarán los datos locales y dónde se ejecutará el modelo. El servidor remoto también necesitará configuración propia de autenticación, HTTPS y acceso; no basta con cambiar el botón o abrir el puerto local.

Para la primera colaboración, actualizar los datos al abrir el proyecto y mediante refresco periódico puede ser suficiente. La edición en tiempo real mediante conexiones permanentes se evaluará después según necesidad.

## Secuencia de desarrollo propuesta

1. Revisar el panel y el recorrido de invitación con el alcance elegido: cuentas del mismo computador y permisos de lectura o edición.
2. Preparar migración con respaldo: identificadores estables, propiedad, referencias de notas, tareas, campos validados, historial y checkpoints. Preservar los proyectos existentes y comprobar la recuperación antes de usar datos reales.
3. Implementar autorización común por proyecto para propietario, lector y editor.
4. Implementar invitación, aceptación, listado Compartidos conmigo, abandono y revocación.
5. Integrar memoria común, Post-its, calendario y herramientas con la autorización del proyecto; separar chats y checkpoints por cuenta y proyecto; sustituir el botón de resumen por la gestión de acceso.
6. Incorporar guardado de avances desde el chat privado, autoría visible en los recursos compartidos, versiones y coordinación de turnos del modelo; validar modificaciones desde la cuenta editora.
7. Validar el recorrido completo con tres cuentas locales: propietario, lector y editor. El acceso remoto se planificará por separado.

## Criterios de aceptación

- Dos cuentas diferentes acceden al mismo proyecto tras aceptar una invitación.
- La invitada ve los Post-its, avances comunes, herramientas y tareas existentes, y sus actualizaciones posteriores; su chat comienza como una conversación propia.
- Ninguna cuenta puede recuperar el historial ni checkpoints de otra, aunque conozca sus identificadores. Compartir conserva privados los chats anteriores.
- El agente de cada integrante utiliza los avances comunes nuevos en su siguiente turno; no recibe ni reconstruye automáticamente la conversación ajena.
- Un resumen automático del chat no se publica en la memoria común sin confirmación del autor.
- Una nota marcada como idea no se presenta como dato verificado. La eliminación o corrección de un avance se refleja en el contexto común vigente.
- No puede consultar proyectos ajenos sin invitación ni tareas personales, aunque conozca identificadores.
- El lector puede consultar a Hilo en su chat privado. No modifica recursos comunes ni invoca herramientas que los escriben; el servidor rechaza esas operaciones.
- Solo el propietario administra acceso y elimina la carpeta.
- Cancelar, rechazar o vencer una invitación no concede acceso. Repetir su aceptación no duplica miembros.
- Revocar acceso bloquea solicitudes posteriores y evita confirmar modificaciones pendientes sin permiso.
- Los nombres de proyectos repetidos no mezclan datos ni checkpoints.
- Un editor puede crear y modificar notas, tareas y resultados del proyecto y conversar con Hilo, pero no administrar miembros ni eliminar la carpeta.
- Cambiar un editor a lector impide nuevas modificaciones. Abandonar el proyecto quita su membresía, sin borrar los avances comunes.
- Los cambios conservan autoría y versión; los conflictos no sobrescriben silenciosamente.
- Los datos existentes permanecen íntegros después de la migración.
- Si el alcance incluye equipos distintos, se prueba con cuentas en dos computadores; una prueba local no reemplaza esa comprobación.

## Fuera del primer alcance

Publicación anónima, enlaces públicos, edición simultánea de texto, transferencia de propiedad, roles personalizados, correo de invitaciones, modo sin conexión con sincronización y compartir carpetas completas de una cuenta. Estas ampliaciones requerirán decisiones posteriores.

## Estado de implementación (19 sep 2026)

**Implementado y probado** (`tests/test_sharing.py`, `tests/test_sharing_integrity.py`, 99 pruebas automatizadas en total y recorrido en navegador con propietario, lector y editor):

- Invitar como lector o editor, aceptar, rechazar, cancelar, cambiar permiso, revocar y abandonar. Las invitaciones se muestran en la aplicación y la aceptación abre el proyecto. Los chats son privados por persona.
- El proyecto conserva un identificador estable. Los Post-its y las tareas vinculadas al proyecto son compartidos; el lector solo puede consultarlos. El servidor comprueba permisos, incluso si se llama a la API directamente. Los Post-its muestran su autor.
- Los avances confirmados y los Post-its alimentan el contexto común con procedencia. El agente recibe ese contexto y su propio historial, nunca el chat de otro participante. El verificador también recibe los aportes comunes sin tratarlos como evidencia verificada.
- Cambiar de cuenta desde un proyecto abierto vuelve a `#inicio`, evitando que el siguiente usuario vea un error por el enlace privado de la cuenta anterior.
- Los avances comunes llegan al contexto de los agentes. Un editor puede **corregirlos**, con control de versión: si otra persona lo corrigió antes, recibe un 409, conserva su borrador y ve la versión vigente. También puede **retirarlos**: el avance queda como `superseded`, sale del contexto y su registro se conserva. Un lector no puede hacer ninguna de las dos cosas.
- **Conflictos en Post-its y en entradas del calendario:** el cliente envía `base_updated_at`. Si el registro cambió, el servidor responde 409 con la versión actual y no sobrescribe. La interfaz recarga esa versión y conserva lo que la persona escribió. Si guarda de nuevo, el reemplazo es deliberado. Sin `base_updated_at` se mantiene el comportamiento anterior.
- **Revocación durante un turno:** antes de guardar la respuesta del chat se vuelve a consultar el acceso. Si se retiró, la respuesta no se guarda y se avisa. Si el rol bajó a lector, se guarda como chat privado.

**Pendiente:**

- El agente propone un avance y el autor lo confirma. Hoy los avances solo se escriben a mano.
- Decidir si los Post-its se envían al modelo: hoy se envían todos, también en proyectos no compartidos.
- Respaldo automático antes de futuras migraciones. Antes de activar esta versión se creó y verificó manualmente una copia de las tres bases de datos reales en `%LOCALAPPDATA%\RutaDIA\backups\before-sharing-20260919-062921`.
- Vencimiento de invitaciones.
- Sección separada "Compartidos conmigo".
- Al eliminar un proyecto quedan checkpoints de integrantes huérfanos. Además, los chats privados de los integrantes viven en la base del propietario.
- El calendario asigna colores y filtros por nombre de proyecto, así que dos proyectos con el mismo nombre se mezclan visualmente.
- Prueba manual del chat con Qwen en línea: las pruebas automatizadas cubren el aislamiento y el contexto, pero el modelo estaba apagado durante el recorrido de interfaz con cuentas de prueba.
