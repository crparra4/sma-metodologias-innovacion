# Prototipo real · Sistema multiagente Ruta DIA

Prototipo del núcleo de agentes. Reemplaza el agente monolítico del beta por tres
responsabilidades aisladas y verificables:

1. **Orquestador:** recibe mensaje, estado e índice de la ruta; devuelve un contrato de
   traspaso con etapa, nivel de experticia y máximo tres herramientas.
2. **Metodólogo:** recibe ese contrato y **una sola ficha**; produce la respuesta candidata.
3. **Verificador:** recibe la respuesta candidata y la misma ficha; dictamina, pero no corrige.

El runtime predeterminado es **LangGraph** y consulta Qwen directamente mediante su API local.
CrewAI se conserva como línea base comparativa. Antes del verificador semántico existe un filtro
estructural sin LLM. Si el verificador rechaza, el grafo vuelve una vez al Metodólogo; un segundo
rechazo produce una respuesta segura y explícita.

## Preparación

Requiere Windows, Python 3.10–3.13, `uv`, Node.js y `pnpm`. En PowerShell,
desde la carpeta del repositorio:

```powershell
cd .\prototipo
python -m uv --system-certs sync --extra dev --link-mode copy
Copy-Item .env.example .env
```

Edita `.env` y reemplaza `RUTA_DIA_API_KEY` por una clave local privada de tu elección.
El instalador descarga el modelo y llama.cpp fuera del repositorio; no se publican
cuentas, proyectos ni credenciales. Para usar Gemini en lugar de Qwen, consulta
los comentarios de `.env.example`.

## Comandos

```powershell
# Comprueba que la ruta solo referencie fichas existentes
python -m uv run ruta-dia validate

# Prueba real de los tres agentes
python -m uv run ruta-dia chat --message "¿Qué sigue en mi proyecto?" --stage 1

# Conversación persistente; el mismo nombre recupera el cuaderno al reiniciar
python -m uv run ruta-dia interactive --stage 1 --notebook mi-prueba

# Consultar el estado recordado o eliminar todo el cuaderno
python -m uv run ruta-dia memory show --notebook mi-prueba
python -m uv run ruta-dia memory clear --notebook mi-prueba

# Ejecutar explícitamente la línea base CrewAI
python -m uv run ruta-dia chat --runtime crewai --message "¿Qué sigue?" --stage 1

# Calidad local
python -m uv run pytest
python -m uv run ruff check .
```

El frontend se administra exclusivamente con **pnpm**. La interfaz local usa Vite y TypeScript,
servidos junto con la API de FastAPI para conversar y observar el grafo de LangGraph.

## Interfaz gráfica local

En una computadora nueva, `start_interface.ps1` descarga automáticamente los archivos del modelo
y de llama.cpp si faltan (aproximadamente 3,4 GB). Se guardan en `%LOCALAPPDATA%\QwenLocalTest`,
fuera de OneDrive. También puedes preparar la descarga por separado:

```powershell
.\.venv\Scripts\python.exe scripts/install_local_model.py
```

Si la descarga se interrumpe, ejecuta el mismo comando de nuevo para reanudarla.
Solo se descarga una vez en cada entorno local.

```powershell
# Inicia Qwen y abre Inicio con todos los proyectos
.\scripts\start_interface.ps1

# Detiene la interfaz
.\scripts\stop_interface.ps1
```

Abre `http://127.0.0.1:8787`. La primera cuenta que registres conservará los proyectos ya guardados;
las cuentas siguientes tendrán conversaciones, post-its y tareas separados. Puedes cerrar sesión desde
tu perfil, en la parte inferior del menú. «Inicio» reúne los proyectos como carpetas con búsqueda y orden.
Al abrir un proyecto puedes enviar mensajes, ver agentes activos y reintentos, revisar el veredicto
y consultar la ficha y memoria guardada. Los detalles están
en [interfaz-local.md](docs/interfaz-local.md).

## Estado del conocimiento importado

El beta aporta 15 fichas utilizables. La ruta declaraba más herramientas sin ficha; esas opciones
no se habilitan todavía. `ruta-dia validate` vuelve este faltante visible y evita que un agente
complete los vacíos con conocimiento general.

La justificación y los límites de la arquitectura están en
[`docs/arquitectura.md`](docs/arquitectura.md).

## Evaluación real con modelos locales

El runtime permite conectar un servidor local mediante `RUTA_DIA_BASE_URL` y
`RUTA_DIA_API_KEY`, manteniendo los agentes y sus contratos. El modelo se selecciona con
`RUTA_DIA_MODEL`; los ejemplos adicionales están en `.env.example`.

El [protocolo del piloto comparativo](evaluation/PROTOCOL.md) define casos, parámetros,
criterios y límites. `scripts/compare_local.py` ejecuta ambos modelos secuencialmente,
registra errores además de aciertos y cierra los servidores al terminar. Las descargas
grandes permanecen fuera del repositorio; los resultados se guardan en `data/evaluations/`.

## Configuración local actual: LangGraph + Qwen3.5-4B

La configuración de desarrollo usa `Qwen3.5-4B-Q4_K_M` en llama.cpp, disponible únicamente en
`127.0.0.1:18083`. LangGraph ejecuta el flujo y el cliente de OpenAI consulta el endpoint compatible
de llama.cpp. El Orquestador y el Metodólogo generan salidas cortas sin razonamiento extendido; el
Verificador sí usa un presupuesto de razonamiento para revisar respaldo y método.

```powershell
# Iniciar, consultar o detener el modelo configurado
.\.venv\Scripts\python.exe scripts/local_model.py start
.\.venv\Scripts\python.exe scripts/local_model.py status
.\.venv\Scripts\python.exe scripts/local_model.py stop

# Ejecutar un turno real
.\.venv\Scripts\ruta-dia.exe chat --message "Quiero aplicar cinco porqués." --stage 1

# Conversar varios turnos; /salir termina la sesión
.\.venv\Scripts\ruta-dia.exe interactive --stage 1 --notebook prueba-personal

# Repetir la batería LangGraph con Qwen local
.\.venv\Scripts\python.exe scripts/evaluate_langgraph.py --seeds 42 43
```

La línea base CrewAI ejecutó ocho escenarios con dos semillas y obtuvo **16/16 controles
mecánicos**. La implementación LangGraph obtuvo **8/8** en su batería completa final y volvió a
probar con ambas semillas los controles afectados por las últimas correcciones. El informe y los
límites de la línea base están en
[`docs/configuracion-qwen3.5-4b-2026-09-09.md`](docs/configuracion-qwen3.5-4b-2026-09-09.md).
La arquitectura de la nueva implementación está en
[`docs/arquitectura-langgraph.md`](docs/arquitectura-langgraph.md).

## Memoria persistente

El prototipo guarda la memoria en `%LOCALAPPDATA%\RutaDIA`, fuera del proyecto sincronizado por
OneDrive. `notebooks.sqlite3` contiene el avance, los turnos, el contexto inicial, los Post-its
personales y, por separado, los campos aportados y aprobados por el verificador. `checkpoints.sqlite3` conserva los checkpoints técnicos de
LangGraph. La base de conocimiento continúa versionada como fichas: no se copia dentro de la
conversación ni se modifica con respuestas del modelo.

Usar el mismo valor de `--notebook` reanuda la memoria. Un nombre diferente inicia otro cuaderno.
Para trasladar o respaldar las conversaciones, detén el proceso y copia los dos archivos SQLite.

## Post-its del cuaderno

El panel derecho permite crear notas personales con título, texto, categoría y color.
Usa **Nueva nota**, **Guardar selección del chat** o **Guardar en post-it** en una respuesta.
Las notas se guardan por cuaderno en SQLite; puedes editarlas y eliminarlas con confirmación.
El flujo real de agentes se consulta mediante **Ver flujo de agentes**, cerrado por defecto.
Las notas son personales y se mantienen separadas de la memoria verificada del modelo.
