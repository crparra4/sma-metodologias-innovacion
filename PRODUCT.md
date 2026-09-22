# Ruta DIA

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

El autor del trabajo de grado utiliza su computadora para probar orientación metodológica de
proyectos de innovación. Esta interfaz inicial es una herramienta local de evaluación.

## Product Purpose

Acompañar proyectos con fichas de Ruta DIA y observar las decisiones y verificaciones del grafo.
El usuario solicita una interfaz rápida para conversar con el modelo local.

## Operating Context

Windows, LangGraph, Qwen3.5-4B en llama.cpp y memoria SQLite fuera de OneDrive.
Las conversaciones se identifican por cuaderno. El frontend se administra con pnpm.

## Capabilities and Constraints

Quince fichas metodológicas, diez etapas, tres responsabilidades: Orquestador, Metodólogo y
Verificador. Un rechazo permite un reintento; un segundo rechazo produce una respuesta segura.
El RAG vectorial se ha discutido y todavía no está implementado.
La interfaz debe mostrar ejecución real, estado del modelo y memoria recuperable.
La sección «Inicio», solicitada por el usuario, reúne todos sus proyectos y permite abrirlos.
Las tarjetas tipo carpeta toman como referencia la imagen proporcionada por el usuario.
Cada cuaderno permite elegir entre seis colores y registrar un reto inicial, entorno, objetivo,
hipótesis, criterio de aceptación y ambición. El nombre y el reto son obligatorios en la creación
desde la interfaz; los demás campos son opcionales. El contexto y el color se pueden editar después.
Las hipótesis y metas iniciales se identifican como supuestos; no se convierten en campos verificados.
El panel derecho prioriza Post-its personales, apilados verticalmente. Cada nota tiene título,
texto, categoría y color; se escribe manualmente o desde un fragmento seleccionado del chat,
con un atajo para guardar una respuesta completa. El fragmento original se conserva al editar.
Las notas se guardan por cuaderno en SQLite, separadas de los campos verificados y del contexto
enviado al modelo. El panel de Post-its contiene solo notas, cada una firmada por su autor.
Agentes es otra herramienta del tablero, con el recorrido y la memoria verificada; la ficha se
abre desde la respuesta y el contexto se consulta en Editar cuaderno.

La identidad actual de la interfaz es **Hilo**, conservando Ruta DIA como metodología del asistente.
Inicio incluye agenda con calendario y tareas al lado, después de las herramientas destacadas.
Las tareas tienen título, fecha/hora, importancia y proyecto opcional; permiten edición y
completar/reabrir. Se guardan en SQLite, separadas del modelo y de los Post-its. Color de plazo
y color de importancia cumplen funciones distintas y siempre se acompañan de etiquetas.
El calendario lavanda marca hoy en verde suave, selección en blanco sobre violeta y puntos para tareas/conversaciones.
El Calendario (menú principal) reúne tareas, recordatorios y reuniones, con hora de fin opcional; el color identifica el proyecto y el icono el tipo. La campanita avisa dentro de Hilo lo vencido, lo de hoy y los próximos tres días; no hay avisos del sistema operativo ni correos. Las cuentas locales separan proyectos, conversaciones, Post-its y tareas por usuario. El acceso usa usuario y contraseña; no hay proveedores externos conectados.

## Evidence on Hand

Código y fichas en `prototipo/`, pruebas y resultados locales documentados.
El frontend operativo y sus reglas visuales están registrados en `DESIGN.md`.

## Assumptions for This Surface

Se adopta un chat con Post-its contiguos y un grafo desplegable para demostración académica.
Se utiliza Vite con TypeScript para una interfaz pequeña y FastAPI para servirla en localhost.
Inicio presenta los proyectos; chat y Post-its aparecen al abrir uno. El grafo y la memoria se consultan a demanda.

El calendario conserva estilo lavanda; la agenda usa panel blanco y filas compactas neutras con filtros violetas,
con colores semánticos de prioridad/plazo preservados. Herramientas permanece antes de ambos.
