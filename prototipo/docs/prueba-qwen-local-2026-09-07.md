# Prueba local de Qwen3.8-27B — 7 de septiembre de 2026

## Resultado

Qwen3.8-27B Q4_K_M pudo cargarse y responder en este computador. La generación medida fue de 2,07 a 2,44 tokens por segundo. Es viable para experimentar, pero esta configuración resulta lenta para acompañamiento conversacional con varios agentes y exige casi toda la RAM disponible.

## Equipo y configuración

- Intel Core i5-12400F, 6 núcleos, 12 hilos.
- 16 GB de RAM instalados; 4,63 GiB disponibles al iniciar la prueba.
- NVIDIA GeForce RTX 4060 Ti, 8 GB de VRAM.
- Windows 11 Pro.
- llama.cpp b10809, commit 5266f24da, compilación Windows CUDA 12.4.
- Modelo: mradermacher/Qwen3.8-27B-GGUF, archivo Qwen3.8-27B.Q4_K_M.gguf, 16.810.714.848 bytes.
- SHA-256 verificado: 1dc0ce077ffb27a39f40081b66269f40719f922feea7e27c582caebd07f019ec.
- Contexto: 2.048 tokens; un usuario; 6 hilos CPU; lotes de 128 tokens; ajuste automático de GPU con margen de 1.024 MiB.
- Razonamiento desactivado; temperatura 0,7; top_p 0,8; semilla 42; respuesta sin streaming.
- JSON restringido al formato de objeto en Orquestador y Verificador; no se validaron los contratos Pydantic del prototipo.
- Fuente: https://huggingface.co/mradermacher/Qwen3.8-27B-GGUF

## Mediciones

Tiempo de carga hasta disponibilidad: **28.76 segundos**, incluyendo inicialización y calentamiento; sin descarga ni comprobación SHA-256.

| Prueba | Tiempo completo (s) | Tokens generados | Generación (tokens/s) |
|---|---:|---:|---:|
| breve | 15.21 | 16 | 2.44 |
| orquestador | 18.27 | 30 | 2.07 |
| metodologo | 41.19 | 76 | 2.20 |
| verificador | 27.55 | 53 | 2.22 |

La suma de las tres consultas que simulan roles fue **87.01 segundos**. Son casos independientes con prompts abreviados: esta suma NO es una medición del flujo CrewAI integrado, no incluye reintentos y el Verificador no recibió la salida del Metodólogo.

Consumo observado del sistema completo, incluyendo otras aplicaciones:

- Pico de uso de RAM en muestreo cada aproximadamente 5 segundos: **99 %**.
- Mínimo de RAM disponible muestreada: **0.04 GiB**.
- Pico de VRAM utilizada muestreada: **7011 MiB**, incluyendo escritorio y otras aplicaciones.
- Tras cerrar el servidor quedaron 10.52 GiB de RAM disponibles.

## Inspección de las respuestas

1. **Respuesta breve:** respondió en español y en una frase sobre la utilidad de preguntar por qué.
2. **Orquestador:** eligió `Definir un reto` y `cinco_porques`; salida JSON válida.
3. **Metodólogo: fallo de fidelidad.** Afirmó que el envío era inesperado o excesivo frente al valor del producto sin que el caso aportara esa causa, pese a la instrucción de no inventar causas. Además avanzó a otra pregunta usando esa suposición. Debió pedir al usuario evidencia o su respuesta antes de continuar.
4. **Verificador:** rechazó correctamente requisitos fabricados de entrevistar a 100 clientes y elaborar PESTEL; salida JSON válida. Esto no demuestra que detecte todos los errores ni que hubiera detectado el fallo anterior.

## Alcance y recomendación

Prueba exploratoria de cuatro consultas, una ejecución por caso, con contexto corto y prompts simplificados. No se midieron concurrencia, conversaciones largas, razonamiento extendido, contratos completos ni la integración con CrewAI. No permite estimar una tasa general de exactitud.

Puede utilizarse para experimentación local, pero no conviene adoptar todavía esta configuración para sesiones con participantes: deben evaluarse instrucciones y validaciones de fidelidad, y reducirse las esperas. El siguiente contraste útil sería repetir los mismos casos con un modelo menor o con más memoria disponible.

## Archivos y repetición

El modelo, el motor y el script permanecen en `%LOCALAPPDATA%/QwenLocalTest/`, fuera de OneDrive. El servidor fue cerrado al terminar.

Para repetir la misma prueba desde PowerShell:

```powershell
python "$env:LOCALAPPDATA/QwenLocalTest/benchmark.py"
```

El script arranca el servidor en 127.0.0.1:18083, ejecuta los cuatro casos y lo cierra. Sobrescribe los registros de esa carpeta. La copia de esta ejecución permanece en `prototipo/data/qwen-local-2026-09-07/` (excluida de Git).
