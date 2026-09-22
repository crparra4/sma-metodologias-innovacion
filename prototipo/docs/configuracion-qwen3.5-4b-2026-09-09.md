# Configuración local de Qwen3.5-4B para Ruta DIA

**Fecha:** 9 de septiembre de 2026.  
**Ejecución final:** `20260909T153923Z`.

## Decisión de configuración

El prototipo queda configurado para `Qwen3.5-4B-Q4_K_M` mediante llama.cpp en
`http://127.0.0.1:18083/v1`. El archivo GGUF y el runtime permanecen fuera del repositorio, en
`%LOCALAPPDATA%\QwenLocalTest`. La API solo escucha en la dirección local y usa una clave guardada
fuera de Git.

Se dividió el presupuesto de generación según la tarea:

- Orquestador y Metodólogo: razonamiento extendido desactivado y máximo de 384 tokens.
- Verificador: razonamiento activado, presupuesto de razonamiento de 1.024 tokens y máximo de
  1.536 tokens de salida.
- Temperatura 0,7, `top_p` 0,8, semilla configurable y contexto de 8.192 tokens.

Esta separación conserva la rapidez de las decisiones sencillas y asigna más cómputo a la revisión
de respaldo. No constituye todavía una optimización definitiva de latencia.

## Cambios de precisión

- La selección de etapa y herramienta está restringida a pares existentes en la ruta.
- La respuesta solo puede citar encabezados reales de la ficha activa y campos de plantilla
  declarados para esa herramienta.
- El Metodólogo recibe una ficha por turno, pide una sola acción y tiene un reintento cuando la
  revisión falla.
- El Verificador elige afirmaciones únicamente entre fragmentos reales de la respuesta.
- Un control determinista detecta respuestas sin una pregunta concreta.
- Las paráfrasis cercanas de información aportada por el usuario se reconocen antes de consultar al
  Verificador. Las cifras nuevas nunca se consideran respaldadas por similitud.
- Si una etapa no tiene ficha habilitada o dos intentos son rechazados, el sistema responde de forma
  segura sin completar pasos con conocimiento general.

## Resultado de la batería final

Se ejecutaron ocho escenarios en las semillas 42 y 43: dos turnos completos, una etapa sin ficha,
dos controles válidos y tres controles negativos. Los 16 resultados completaron la ejecución y
cumplieron sus expectativas mecánicas.

| Escenario | Resultado en ambas semillas |
|---|---|
| Turno con 5 porqués sin causas conocidas | Herramienta correcta, una pregunta, sin causas inventadas |
| Turno PESTEL con reto ya definido | Avanza al factor Social sin repetir el reto ni inventar datos |
| Etapa 7 sin ficha | Degradación explícita y sin orientación inventada |
| Orientación válida | Aprobada |
| Entrevistas obligatorias y PESTEL inventados | Rechazados |
| Inversión de roles | Rechazada |
| Causa no aportada por el usuario | Rechazada |
| Misma causa aportada por el usuario | Aprobada |

La mediana del turno completo de 5 porqués fue **19,32 segundos**. Los verificadores aislados
estuvieron entre **14,57 y 16,04 segundos**. PESTEL tardó **19,56 segundos** en una semilla y
**36,29 segundos** en la otra porque necesitó el reintento de corrección.

Se revisaron manualmente las respuestas finales de los dos turnos completos. En 5 porqués el modelo
reformuló el problema aportado y preguntó por su causa sin proponer una respuesta. En PESTEL preguntó
por comportamientos o necesidades observables del factor Social, sin fabricar leyes, cifras ni
hallazgos.

## Verificación de software

- 27 pruebas de `pytest` aprobadas.
- `ruff check src tests scripts` aprobado.
- Catálogo validado: 10 etapas y 15 fichas habilitadas.
- Turno ejecutado desde el comando instalado contra el servidor normal, con veredicto aprobado en el
  primer intento.

## Alcance de la evidencia

Dos semillas y ocho escenarios sirven como prueba de ingeniería y regresión; no estiman una tasa
general de exactitud. La comparación anterior mostró que el modelo local de 27B era mucho más lento
en este equipo. La configuración de 4B es adecuada para continuar el desarrollo, pero las fichas, la
rúbrica y una muestra más amplia deben revisarse con una persona experta antes de realizar sesiones
con participantes o sostener conclusiones académicas sobre efectividad.

## Reproducción

Desde la carpeta `prototipo`:

```powershell
.\.venv\Scripts\python.exe scripts/local_model.py start
.\.venv\Scripts\ruta-dia.exe validate
.\.venv\Scripts\python.exe scripts/compare_local.py --models small --seeds 42 43 `
  --cases F01 G01 V01 V02 V03 V04 V05 F02 --thinking
```

El resumen generado está en
`data/evaluations/20260909T153923Z/summary.md`. Los resultados de evaluación permanecen fuera de Git
porque contienen trazas completas de las solicitudes y respuestas.
