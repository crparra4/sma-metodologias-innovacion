# Comparación local de Qwen para Ruta DIA

**Fecha:** 7 de septiembre de 2026. **Ejecución:** `20260907T163510Z`.

## Resultado principal

El prototipo pudo ejecutar ambos modelos con los tres agentes CrewAI y sus contratos reales.
Qwen3.5-4B Q4_K_M resolvió el turno completo en **6,95–7,80 segundos**; Qwen3.8-27B Q4_K_M
necesitó **265,76–266,07 segundos** (aproximadamente 4 minutos y 26 segundos).

Los dos pasaron los controles mecánicos previstos. La revisión textual del asistente encontró
problemas de claridad y hallazgos falsos adicionales en el modelo pequeño. Las respuestas del
modelo grande revisadas fueron más claras y sus hallazgos se mantuvieron centrados en la ficha.
Esto describe estos casos, no una tasa general de exactitud ni una evaluación experta humana.

**Recomendación de desarrollo:** continuar experimentando con el 4B en este computador, corregir
las instrucciones que produjeron los problemas observados y repetir la evaluación. El 27B queda
como referencia comparativa local; su espera actual resulta poco práctica para acompañamiento
interactivo. No adoptar todavía ninguna configuración como validada para sesiones con participantes.

## Qué se ejecutó

- 4 casos × 2 semillas × 2 modelos = **16 observaciones completas**.
- **24 llamadas reales** al modelo (12 por configuración), sin llamadas de reparación adicionales.
- F01: `RutaDiaService.handle_turn` → Orquestador → Metodólogo → Verificador, con contratos
  Pydantic, filtros y auditoría reales. Los cuatro turnos terminaron en el primer intento.
- G01: etapa 7 sin fichas, con respuesta de degradación determinista.
- V01/V02: control positivo y negativo del Verificador, separados del turno completo.
- Misma biblioteca y prompts del prototipo, contexto de 8.192 tokens, razonamiento desactivado,
  temperatura 0,7, máximo 384 tokens por llamada, servidor de un usuario y ejecución secuencial.
- Respuestas restringidas mediante JSON Schema por CrewAI/llama.cpp. El cumplimiento de formato
  observado no demuestra que los modelos lo produzcan sin esa restricción.
- Calentamiento separado y excluido. Las 24 respuestas informaron cero tokens reutilizados
  de caché y finalizaron por `stop`; no hubo truncamientos por el límite de salida ni timeouts.
- Se verificaron SHA-256 de los modelos y que los archivos del prototipo permanecieran
  idénticos al manifiesto durante la comparación.

El [protocolo](../evaluation/PROTOCOL.md) fija el diseño y sus límites. Los
[casos](../evaluation/cases.json) conservan las expectativas anteriores a la ejecución.
La prueba previa de conexión no se incluyó en los resultados comparativos.

## Tiempos medidos

Mediana de dos ejecuciones por caso; tiempos de respuesta completos, sin descarga ni carga inicial.

| Caso | Qwen3.5-4B Q4_K_M | Qwen3.8-27B Q4_K_M |
|---|---:|---:|
| Turno completo: tres agentes | 7.38 s | 265.91 s |
| Etapa sin fichas | 2.78 s | 81.73 s |
| Verificador: control válido | 2.13 s | 34.13 s |
| Verificador: pasos inventados | 3.70 s | 120.98 s |

| Indicador | Qwen3.5-4B | Qwen3.8-27B |
|---|---:|---:|
| Observaciones que completaron y pasaron controles mecánicos | 8/8 | 8/8 |
| Mediana de velocidad de generación entre llamadas | 73.99 tokens/s | 2.36 tokens/s |
| Tokens de salida totales en casos medidos | 1462 | 1774 |
| Pico muestreado de RAM del sistema | 63 % | 99 % |
| Pico muestreado de VRAM del sistema | 3999 MiB | 7002 MiB |

Las cifras de memoria incluyen otras aplicaciones y se muestrearon aproximadamente cada
5 segundos; no equivalen al consumo exclusivo del modelo. El ajuste de GPU fue automático.
Las respuestas tuvieron distinta longitud, por lo que el tiempo completo refleja tanto
velocidad de cálculo como comportamiento de generación. No se cerraron las aplicaciones del usuario.

Equipo: Intel Core i5-12400F, 16 GB RAM, RTX 4060 Ti de 8 GB, Windows 11 Pro.
La configuración grande incumplió en ambos turnos el umbral **exploratorio de ingeniería** de
60 segundos fijado antes de la comparación; ese umbral no está validado como medida de usabilidad.

## Hallazgos cualitativos que los controles mecánicos no detectaron

### Modelo pequeño: orientación del siguiente paso

- Semilla 42: pidió «Hazme la pregunta inicial», invirtiendo el papel del facilitador y dejando
  poco claro quién debe responder. El Verificador lo aprobó.
- Semilla 43: declaró que el primer paso era enunciar el problema, pero pidió «Describe exactamente
  por qué los clientes abandonan», mezclando la enunciación del problema con la explicación causal.
  El usuario había indicado que aún no había investigado las causas. El Verificador lo aprobó.
- En ninguna de esas dos respuestas se observaron causas inventadas ni datos fabricados en
  `template_updates`. El fallo observado es de claridad y secuenciación, no la invención causal
  detectada en la prueba breve anterior.

### Modelo pequeño: hallazgos falsos adicionales del Verificador

Aunque rechazó correctamente las entrevistas obligatorias y PESTEL en ambas ejecuciones de V02:

- Semilla 42: trató `template_updates`, un campo del contrato que estaba vacío, como contenido
  metodológico inventado por no aparecer en la ficha.
- Semilla 43: afirmó que no existía el encabezado «Cómo se usa (paso a paso)», que sí está presente.

Por tanto, acertar la etiqueta `rejected` no significa que todos los argumentos del dictamen sean
correctos. La prueba conserva estas observaciones aunque el control mecánico global pase.

### Modelo grande

En F01 pidió la primera respuesta o la confirmación del problema sin inventar causas. Sus controles
negativos identificaron los requisitos ajenos a la ficha sin los hallazgos falsos adicionales
anteriores. Las respuestas fueron relativamente extensas y lentas. La muestra no permite afirmar
que el modelo esté libre de errores.

## Revisión independiente del Verificador del prototipo

Revisor: **asistente Codex**, inspección textual no ciega contra ficha y caso. Pendiente de validación
por una persona experta. `cumple_con_observacion` conserva el acierto del dictamen y señala problemas
adicionales; no debe agregarse sin más como un acierto de fidelidad completa.

| Modelo | Semilla | Caso | Revisión | Evidencia interpretada |
|---|---:|---|---|---|
| large | 42 | F01 | cumple | Reformula el problema aportado y pide al usuario la primera respuesta sin inventar una causa ni escribir actualizaciones de plantilla. Conserva un siguiente paso reconocible, aunque la respuesta es relativamente extensa. |
| large | 42 | G01 | cumple | La respuesta determinista informa la falta de ficha y no inventa pasos. |
| large | 42 | V01 | cumple | Aprueba el control válido sin hallazgos falsos. |
| large | 42 | V02 | cumple | Rechaza los requisitos no respaldados y centra los hallazgos en el contenido metodológico. |
| large | 43 | F01 | cumple | Pide confirmar el problema aportado antes de avanzar, sin inventar causas ni completar datos. El siguiente paso es coherente. |
| large | 43 | G01 | cumple | Reporta la falta de fichas sin inventar instrucciones. |
| large | 43 | V01 | cumple | Aprueba correctamente la orientación respaldada. |
| large | 43 | V02 | cumple | Los hallazgos señalan contenido ajeno a la ficha. La explicación es redundante, pero no añade el falso señalamiento sobre el contrato técnico. |
| small | 42 | F01 | no_cumple | Invierte el papel del facilitador al pedir al usuario que le haga la pregunta al asistente. No inventó una causa ni guardó datos, pero la siguiente acción no queda clara para un usuario novel. |
| small | 42 | G01 | cumple | Conserva la etapa 7, informa la brecha y no llama al Metodólogo ni al Verificador. |
| small | 42 | V01 | cumple | Aprueba correctamente el control respaldado por la ficha. |
| small | 42 | V02 | cumple_con_observacion | Rechaza correctamente los requisitos de 100 clientes y PESTEL, pero añade un hallazgo incorrecto: template_updates es parte del contrato y está vacío. Ese campo técnico no constituye un paso metodológico inventado. |
| small | 43 | F01 | no_cumple | Anuncia el paso de enunciar el problema, pero solicita explicar su causa aunque el usuario aún no la investigó. next_step también dice enunciar el problema. La inconsistencia entre el paso declarado y la petición dificulta la guía progresiva. No se observan causas fabricadas ni actualizaciones inventadas. |
| small | 43 | G01 | cumple | Conserva la etapa y comunica el vacío sin generar pasos. |
| small | 43 | V01 | cumple | Aprueba correctamente el control positivo. |
| small | 43 | V02 | cumple_con_observacion | Rechaza correctamente las entrevistas y PESTEL, pero inventa una discrepancia de fuente: el encabezado sí existe literalmente en la ficha. El dictamen global es correcto; no todos sus hallazgos lo son. |

## Qué quedó implementado

- Conexión configurable de CrewAI a un servidor local mediante `RUTA_DIA_BASE_URL`, sin modificar
  los prompts metodológicos para esta línea base.
- Banco de casos versionado y [ejecutor comparativo](../scripts/compare_local.py).
- Registros de contratos, solicitudes/respuestas HTTP, tokens, tiempos, errores y auditoría.
- Manifiesto y copia congelada de fuentes, fichas y parámetros para reproducibilidad.
- Revisión cualitativa separada de controles mecánicos y del propio modelo evaluado.
- **16 pruebas de software aprobadas** (11 existentes y 5 nuevas); `ruff check` aprobado.

## Próximas correcciones y ampliaciones

1. Aclarar el siguiente paso al usuario y evitar pedirle que formule preguntas al asistente.
2. Enseñar al Verificador a distinguir metadatos del contrato de contenido metodológico y comprobar
   referencias a encabezados contra la ficha, sin inventar discrepancias.
3. Añadir regresiones basadas en estas salidas y repetir los mismos casos después de las correcciones,
   con una nueva versión y otro directorio de resultados.
4. Ampliar a otras herramientas, varios turnos, datos proporcionados por el usuario, instrucciones
   contradictorias, fuentes insuficientes, errores estructurales y reintentos.
5. Validar fichas y rúbrica con una persona experta antes del estudio con participantes.

Este piloto no mide carga cognitiva. Comparar 3.5-4B con 3.8-27B cambia tamaño y versión; no aísla
el efecto del número de parámetros. Dos repeticiones por caso no permiten generalizar tasas de éxito.

## Evidencia y reproducción

- [Resumen de las 16 observaciones](../data/evaluations/20260907T163510Z/summary.md)
- [Resultados completos](../data/evaluations/20260907T163510Z/summary.json)
- [Métricas agregadas](../data/evaluations/20260907T163510Z/metrics.json)
- [Revisión textual con evidencia](../data/evaluations/20260907T163510Z/review-assistant.json)
- [Manifiesto de versiones y hashes](../data/evaluations/20260907T163510Z/manifest.json)

Los resultados originales permanecen en `data/evaluations/20260907T163510Z/`, excluidos de Git.
Los dos modelos y llama.cpp permanecen en `%LOCALAPPDATA%/QwenLocalTest`, fuera de OneDrive.
Los servidores fueron cerrados y la clave temporal eliminada al terminar.

Para repetir desde `prototipo`:

```powershell
.\.venv\Scripts\python.exe scripts/compare_local.py
```

El comando crea un directorio nuevo; no sobrescribe esta ejecución.
