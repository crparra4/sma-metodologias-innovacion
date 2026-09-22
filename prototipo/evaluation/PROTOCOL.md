# Protocolo del piloto técnico local — versión 1

## Propósito y alcance

Comparar la viabilidad de dos configuraciones locales para el prototipo Ruta DIA en este equipo:
Qwen3.8-27B Q4_K_M y Qwen3.5-4B Q4_K_M. La comparación cambia tanto tamaño como versión del
modelo; no permite atribuir causalmente las diferencias solo al número de parámetros.

Es un piloto técnico reproducible, anterior a la evaluación con participantes. No mide carga
cognitiva ni demuestra eficacia educativa o metodológica. Las fichas son borradores pendientes
de validación experta; el control de fidelidad aquí se refiere al contenido cargado.

## Diseño fijado antes de ejecutar la comparación

- Cuatro casos de `cases.json`, dos semillas (42 y 43), dos modelos: 16 observaciones previstas.
- F01 recorre `RutaDiaService` y `CrewAIRuntime` reales, con sus tres contratos Pydantic, filtros,
  auditoría y un reintento metodológico cuando corresponda. No se cambian los prompts de los roles.
- G01 comprueba la ruta de ausencia de fichas (solo Orquestador y respuesta determinista).
- V01 y V02 evalúan al Verificador por separado con controles positivo y negativo.
- Cada caso se ejecuta en un proceso nuevo, sin memoria conversacional entre casos.
- Orden de modelos invertido en la segunda semilla; orden de casos aleatorizado de forma
  reproducible con la misma semilla para ambos modelos.
- Un servidor a la vez, contexto de 8.192 tokens, lotes de 128, 6 hilos CPU, ajuste de GPU con
  margen de 1.024 MiB, razonamiento desactivado, temperatura 0,7, top_p 0,8, máximo 384 tokens
  por llamada. No se usa caché de prompts entre consultas.
- El presupuesto de salida puede provocar truncamientos: se registran como fallos de esta
  configuración, sin concluir por ello que el modelo sea intrínsecamente incapaz.
- Se conserva un calentamiento separado por bloque, excluido de las métricas de casos.
- Se desactivan los reintentos de transporte y reinicio del agente para no ocultar fallos ni
  multiplicar las llamadas. Se conserva el reintento metodológico explícito del servicio.
- Límite de 240 segundos por llamada HTTP, 600 segundos por caso y 420 segundos de carga.
  Un timeout de caso detiene su bloque; los restantes se registran como no ejecutados.
- Una semilla fija no garantiza determinismo bit a bit entre arquitecturas o equipos.

## Métricas y criterios provisionales de ingeniería

1. **Finalización técnica:** resultado válido frente a excepción, timeout o no ejecución.
2. **Contratos:** validación real de salidas y controles mecánicos esperados por caso.
3. **Tiempo de turno F01:** duración completa de `handle_turn`, incluidos filtros y reintento.
   Umbral exploratorio propuesto: 60 segundos para esta interacción breve. No es un umbral
   validado de usabilidad ni una medida de carga cognitiva.
4. **Tiempo por rol, tokens y llamadas:** se registran también llamadas internas de CrewAI.
5. **RAM y VRAM:** muestreo cada aproximadamente 5 segundos del sistema completo; las otras
   aplicaciones no se cierran. No interpretar estas cifras como memoria exclusiva del modelo.
6. **Fidelidad:** revisión independiente de las respuestas y actualizaciones contra la ficha y
   los datos del caso. Un aprobado del propio Verificador no demuestra que una respuesta sea fiel.

Para considerar una configuración candidata al siguiente piloto, se propone exigir ausencia de
fallos críticos observados de fidelidad, finalización de todos los casos y contratos correctos.
Son criterios de desarrollo sobre una muestra pequeña, no estimaciones de rendimiento poblacional.

## Revisión cualitativa

Revisar F01 contra sus cuatro criterios, G01 por ausencia de invenciones y los controles V01/V02
contra las etiquetas previstas. Registrar `cumple`, `no_cumple` o `indeterminado`, evidencia textual
y quién revisó. La revisión inicial del asistente debe identificarse como tal: no sustituye la
validación por una persona experta ni debe presentarse como evaluación ciega.

Conservar los errores como parte de los resultados. No cambiar prompts, fichas, parámetros ni
etiquetas dentro de una ejecución. Una corrección posterior exige un nuevo identificador y un
nuevo conjunto de resultados; no sobrescribir la línea base.

## Reproducción

Desde `prototipo`, con los archivos GGUF y llama.cpp instalados en
`%LOCALAPPDATA%/QwenLocalTest`:

```powershell
.\.venv\Scripts\python.exe scripts/compare_local.py
```

Prueba de integración previa, excluida del piloto:

```powershell
.\.venv\Scripts\python.exe scripts/compare_local.py --models small --seeds 42 --cases V01
```

Cada ejecución crea `data/evaluations/<fecha UTC>/` con manifiesto de versiones y hashes,
copia de fuentes y fichas, resumen, solicitudes/respuestas HTTP, tiempos por rol, auditoría y
memoria por bloque. No se registran cabeceras de autenticación. El servidor solo escucha en
127.0.0.1, utiliza una clave temporal y se cierra al terminar cada bloque. La telemetría de CrewAI
y OpenTelemetry se desactiva para los procesos de evaluación.

## Siguiente fase

Después de este piloto: ampliar escenarios y repeticiones, incorporar conversaciones de varios
turnos y pruebas de regresión derivadas de los errores, validar las fichas y la rúbrica con una
persona experta, y definir el protocolo con participantes para estudiar carga cognitiva.
