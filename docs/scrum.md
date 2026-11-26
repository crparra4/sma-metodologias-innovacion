# Cómo se organizó el desarrollo de Hilo con Scrum

> **De dónde sale este registro.** El tablero de GitHub Projects que se usó durante los sprints no
> conservó sus tarjetas. Este archivo reconstruye, el 26 de noviembre de 2026, el registro de Scrum
> tal como quedó en el trabajo de grado entregado: sección 1.11.8, Tablas 7, 8 y 11, sección 2.2.1,
> Anexo A (Tablas A.1 a A.10) y Anexo C (Tabla C.2). No agrega datos que no estén en el documento.

Scrum no fue la metodología de la investigación —que es Design Science Research en seis fases—,
sino la forma de organizar el desarrollo de las fases 2 a 6: **siete sprints de dos semanas, del 3
de agosto al 8 de noviembre de 2026**. Se eligió frente a Kanban, XP, RUP, Cascada y Design Sprint
(Tabla A.1) porque entrega algo que funciona cada dos semanas, deja ajustar en cada sprint —clave
con un modelo de lenguaje, que no siempre se comporta igual— y es el marco ágil más usado.

## Roles

| Rol | Quién | Responsabilidad |
|---|---|---|
| Product Owner | Estratega de innovación de la organización aliada | Ordena el Product Backlog, va a cada Sprint Review, aprueba lo entregado y armó con el equipo el contenido de las fichas |
| Scrum Master y desarrollador principal | Cristian (autor) | Dirige los eventos, resuelve los problemas técnicos y programa el sistema |
| Equipo de desarrollo | William (autor) | Apoyo en tareas técnicas, sin acceso a información sensible de la organización |
| Interesadas clave | Directora del área de Salud y líder de Innovación en Salud | Identificaron el problema y dieron el contexto en el diagnóstico |

## Artefactos y su compromiso

| Artefacto | Compromiso | Cómo se manejó |
|---|---|---|
| **Product Backlog** | **Objetivo del producto:** un prototipo funcional de sistema multiagente que guíe paso a paso el uso de la metodología de innovación, probado con usuarios y expertos | 5 épicas, 12 historias de usuario y 62 puntos, más 4 historias técnicas de deuda. El Product Owner lo ordenó por dependencias técnicas, riesgo (el modelo local se probó desde el sprint 1) y valor para el usuario |
| **Sprint Backlog** | **Objetivo del sprint** (tabla de sprints, abajo) | Las historias escogidas en la planeación y sus tareas, en el tablero con las columnas Por hacer, En progreso, En revisión y Terminado |
| **Incremento** | **Definición de terminado:** cumple sus criterios de aceptación, las pruebas automáticas pasan (desde el sprint 7, solas en la integración continua), el código está subido y la documentación al día | Se mostraba en cada Sprint Review |

## Eventos

| Evento | Cómo se hizo |
|---|---|
| **Sprint** | 7 sprints de dos semanas, del 3 de agosto al 8 de noviembre de 2026. No hubo sprint 8 |
| **Sprint Planning** | Al inicio de cada sprint se escogían las historias que cumplían su objetivo |
| **Daily Scrum** | Por escrito en GitHub Projects: el equipo era de dos personas con horarios distintos |
| **Sprint Review** | Sesión de trabajo con el Product Owner, que a veces invitaba a otros estrategas. Como la Guía de Scrum no dice cómo registrarla, se usó una plantilla propia: datos, asistentes, objetivo e historias, incremento presentado, retroalimentación y ajustes al backlog |
| **Sprint Retrospective** | Qué salió bien, qué falló, la acción de mejora y cuándo se aplicó |

Se mantuvieron los tres pilares de Scrum: transparencia, inspección y adaptación.

## Sprints y objetivos (Sprint Goals)

| Sprint | Fechas | Épicas | Historias | Puntos | Objetivo del sprint |
|---|---|---|---|---|---|
| 1 | 3 al 16 de agosto | 1 | HU-01, HU-02 | 9 | Preparar el entorno de desarrollo, instalar el modelo de lenguaje local e integrar LangGraph |
| 2 | 17 al 30 de agosto | 1 y 2 | HU-03, HU-04 | 8 | Completar la arquitectura base e iniciar el diseño UX de la conversación |
| 3 | 31 de agosto al 13 de septiembre | 2 y 3 | HU-05, HU-06 | 11 | Completar el flujo conversacional y estructurar el Agente Orquestador |
| 4 | 14 al 27 de septiembre | 3 y 4 | HU-07, HU-08 | 13 | Completar el Agente Orquestador e integrar las primeras instrucciones del Agente Metodólogo |
| 5 | 28 de septiembre al 11 de octubre | 4 | HU-09 | 8 | Desarrollar las instrucciones y las fichas de la fase de Incubación |
| 6 | 12 al 25 de octubre | 4 | HU-10 | 5 | Completar la fase de Aceleración, incorporar el Agente Verificador e integrar el SMA |
| 7 | 26 de octubre al 8 de noviembre | 5 | HU-11, HU-12 | 8 | Realizar las sesiones de evaluación, aplicar la encuesta y analizar los resultados |

Los puntos son los **planeados**. El avance se siguió en el tablero y con la definición de terminado;
no se llevó un burndown.

## Product Backlog

Épicas: (1) entorno y arquitectura base, (2) diseño de la conversación, (3) Agente Orquestador,
(4) agentes Metodólogo y Verificador, (5) evaluación con usuarios.

| HU | Historia | Usuario | Sprint | Puntos | Criterios de aceptación | Estado al cierre |
|---|---|---|---|---|---|---|
| HU-01 | Configuración del entorno de desarrollo | Desarrollador | 1 | 4 | Con un script se crea el entorno con versiones fijadas en Windows y en Linux; el modelo y la interfaz se inician y el servicio informa que están disponibles | Cumplida |
| HU-02 | Integración del marco de orquestación multiagente (LangGraph) | Desarrollador | 1 | 5 | El grafo de LangGraph se construye con sus siete nodos y un turno de prueba recorre Orquestador, Planificador, Metodólogo y Verificador emitiendo eventos | Cumplida |
| HU-03 | Definición de arquitectura de comunicación entre agentes | Desarrollador | 1 / 2 | 3 | Los cuatro contratos se validan con Pydantic y una respuesta del modelo que no cumple el esquema se rechaza | Cumplida |
| HU-04 | Diseño del flujo conversacional del sistema | Colaborador | 2 | 5 | Cada respuesta formula una sola pregunta o acción; saludos y consultas fuera del alcance reciben respuestas predefinidas | Cumplida |
| HU-05 | Validación del flujo conversacional con usuarios reales | Colaborador | 2 / 3 | 3 | La conversación se prueba con baterías de prueba y con personas de fuera del desarrollo antes de las sesiones de evaluación | Parcial |
| HU-06 | Análisis del contexto del usuario por el Agente Orquestador | Colaborador | 3 | 8 | El Orquestador clasifica la solicitud en uno de siete tipos e identifica la etapa; los temas sensibles se detectan sin llamar al modelo | Cumplida |
| HU-07 | Enrutamiento automático a la fase correcta de la metodología | Colaborador | 3 / 4 | 5 | Se selecciona una ficha de la etapa; si pertenece a una etapa posterior se avisa, y si la etapa no tiene ficha se informa sin generar pasos | Cumplida |
| HU-08 | Guía autónoma en herramientas de la fase Descubrimiento | Colaborador | 4 | 8 | Las 14 fichas de las etapas 1, 3, 4 y 5 guían paso a paso; el recorrido de prueba de las fichas se completa con salida segura en los casos rechazados | Cumplida |
| HU-09 | Guía autónoma en herramientas de la fase Incubación | Colaborador | 5 | 8 | La ficha de la etapa 6 (Lean Canvas) guía paso a paso; la etapa 7 se excluye por diseño y la etapa 8 queda por incorporar | Parcial |
| HU-10 | Guía autónoma en herramientas de la fase Aceleración | Colaborador | 5 / 6 | 5 | La ruta original no asigna herramientas a las etapas 9 y 10; el sistema ubica a la persona en ellas e informa que no hay ficha | No aplica |
| HU-11 | Ejecución de sesiones de prueba con colaboradores | Colaborador | 7 | 5 | Se hacen las sesiones con consentimiento informado y se anota la terminación y el abandono de cada participante | Parcial |
| HU-12 | Aplicación de la encuesta de evaluación (15 preguntas) | Investigador | 7 | 3 | Se aplican la encuesta de 15 ítems y la rúbrica de expertos, y se calculan los indicadores del KPI 3 | Cumplida |
| HT-01 | Dividir la capa de entrada en un enrutador por contexto | Desarrollador | Posterior | Sin estimar | Deuda técnica encontrada al organizar Hilo con DDD | Pendiente |
| HT-02 | Separar el almacenamiento de las prácticas de entrevista | Desarrollador | Posterior | Sin estimar | Deuda técnica | Pendiente |
| HT-03 | Pasar el acceso al modelo de herencia a composición | Desarrollador | Posterior | Sin estimar | Deuda técnica | Pendiente |
| HT-04 | Retirar la dependencia heredada de CrewAI | Desarrollador | Posterior | Sin estimar | Deuda técnica | Pendiente |

**Al cierre del sprint 7:** 8 historias cumplidas (41 puntos), 3 parciales (16 puntos) y 1 que no
aplica (5 puntos). Algunas historias pasaron de un sprint al siguiente (HU-03, HU-05, HU-07 y HU-10).

## Sprint Reviews

| Sprint | Fecha y asistentes | Incremento presentado | Retroalimentación | Ajustes al Product Backlog |
|---|---|---|---|---|
| 1 | Al cierre del sprint. Equipo Scrum y Product Owner | Versión beta de un solo agente (proyecto Hermes), probada con Gemini y con el modelo local Qwen | El agente no entendía el problema de la persona, no resolvía sus dudas y a veces no era claro | Las tres fallas se volvieron reglas de diseño: ubicar a la persona antes de responder, resolver dudas con la ficha de cada herramienta y revisar cada respuesta antes de mostrarla. De aquí salió la arquitectura multiagente |
| 2 | 19 de agosto. Equipo, Product Owner y representantes de la organización aliada | Prototipo base del diseño de la interfaz | Cuadernos por proyecto, guardar el avance y mostrar las herramientas poco a poco; la organización pidió además guía según el avance, ayuda con plantillas, ejemplos de proyectos anteriores y un panel para estrategas | Entraron los cuadernos, el avance y las herramientas poco a poco; la ayuda con plantillas se limitó a las 15 fichas; los ejemplos y el panel quedaron por fuera |
| 3 | Al cierre del sprint. Equipo, Product Owner y otro estratega | Primera interfaz web con cuadernos, conectada al modelo local, y grafo de agentes en LangGraph | Qué información pedir al crear el cuaderno; los estrategas dieron el contenido metodológico (PESTEL, recorrido del cliente, Design Thinking) | Se definieron los datos iniciales del cuaderno y las fichas se empezaron a hacer con los estrategas |
| 4 | Al cierre del sprint. Equipo, Product Owner y estrategas | Versión multiagente con LangGraph; inicio, cuadernos, notas y agenda; árbol de problemas y cinco porqués con pantalla propia | Un proyecto de innovación necesita una interfaz más creativa, parecida a trabajar en papel | Se rediseñó la interfaz: el diseño visual que tiene Hilo hoy |
| 5 | Al cierre del sprint. Equipo y Product Owner | Notas tipo post-it y proceso de cada herramienta; ejecución en Windows y Linux; pantallas de PESTEL, mapa de empatía y recorrido del cliente | Se revisaron las herramientas de la etapa de investigación | Se escogieron las herramientas de investigación que se quedan |
| 6 | 21 de octubre. Equipo, Product Owner y representantes de la organización aliada | Demostración con un caso ficticio; comparación entre agente único y arquitectura multiagente; Planificador y Cliente simulado | Gustaron el Planificador y la práctica de entrevistas; propusieron adaptar la conversación al nivel de experiencia | Los niveles de experiencia pasaron al sprint 7; no se alcanzaron a construir y quedaron como trabajo futuro |
| 7 | 28 de octubre: la sesión de prueba hizo de revisión, con el Product Owner, los estrategas y el director | El incremento completo, probado por los participantes | Ver la sección 3.3 del documento | Cambios al backlog de la sección 3.3 |

## Retrospectivas

| Hallazgo | Acción de mejora | Cuándo se aplicó |
|---|---|---|
| Respuestas repetidas: la beta 1 no atendía lo que se pedía y repetía respuestas aprendidas | Arquitectura de varios agentes: el Orquestador clasifica, el Planificador decide a partir del avance y el Verificador rechaza respuestas que repiten | Beta 2 (Hilo) |
| Temas sensibles: con un caso simulado de depresión, el agente seguía como si nada | Detectar los temas sensibles con reglas antes de llamar al modelo y dar una respuesta fija | Sprint 5 |
| Uso de datos sin permiso en escenarios simulados | Datos separados por persona, permisos revisados en cada consulta; notas y agenda nunca van al modelo | Beta 2 (Hilo) |
| Diseño: la primera interfaz no gustó | Cuadernos y herramientas poco a poco; después, el diseño parecido a trabajar en papel | Sprints 2 y 4 |
| Fallas al leer archivos PDF y Word | Corrección de los errores de extracción | Beta 2 (Hilo) |
| Caídas del servidor | Se arreglaron las causas y se agregó el respaldo cuando el modelo local no está | Beta 2; respaldo en el sprint 6 |
| La encuesta no se hizo en la sesión de prueba, así que terminación y abandono solo se midieron con los expertos | Hacer la encuesta y medir la terminación en la misma sesión | Sprint 7; práctica para próximas evaluaciones |
| El piloto se hizo con un evaluador de IA y no con personas | Piloto con personas antes de evaluar y revisar qué modelo responde | Sprint 7; práctica para próximas evaluaciones |
| Los niveles de experiencia no cupieron junto con la evaluación | Priorizar la evaluación y pasar los niveles al trabajo futuro | Sprint 7 |

## Trazabilidad

Cada objetivo específico se convierte en historias de usuario; cada historia tiene criterios de
aceptación que se pueden comprobar, y la Tabla C.6 del documento une cada capacidad del sistema con
su objetivo, su historia, su requisito, su componente y la evidencia. Los sprints 1 y 2 son la fase
de diseño (objetivo 1), del 3 al 6 la construcción y la evaluación técnica (objetivo 2) y el 7 la
prueba con personas (objetivo 3).
