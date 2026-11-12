# Recuperación de Qwen local — 29 de septiembre de 2026

El motor llama.cpp b10809 terminaba antes de cargar el modelo. Los eventos 3077
de Code Integrity identificaron bloqueos de Smart App Control sobre `llama.dll`
y `llama-common.dll`. Los archivos coincidían con el paquete original verificado;
no se pudo determinar por qué Windows había dejado de aceptar esa compilación.

Se actualizó el motor a **b11146**, correspondiente a la versión estable v0.5.0,
desde la publicación oficial de ggml-org. El paquete CUDA 12.4 se verificó con
SHA-256 `3c806a6ceccc3dae1c743ceb1a1fb2cce5b76f40bfbd4c6b7b8afb6ef45a5807`.
Se conserva Qwen3.5-4B Q4_K_M, su configuración, la clave y el puerto local 18083.

El instalador y los scripts de inicio usan ahora
`%LOCALAPPDATA%\QwenLocalTest\runtime-b11146`. La instalación anterior se conservó.
No se cambiaron las políticas de Windows ni se añadieron exclusiones antivirus.
El nuevo motor tampoco tiene firma Authenticode; Windows permitió esta ejecución.
Esto no garantiza que su evaluación de confianza permanezca igual en el futuro.

Comprobaciones realizadas:

- Arranque normal mediante `scripts/local_model.py start` y estado activo.
- Respuesta real con JSON Schema: `{"resultado": 4}` en 1,29 s.
- Turno LangGraph con los tres roles, exclusivamente en memoria: 19,06 s,
  herramienta `cinco-porques`, un intento, dictamen `observed`, sin degradación.
  Respuesta: «¿Por qué tus clientes deciden no reservar?».
- Hilo: `/api/status` devuelve `available: true`, `busy: false`.
- `start_interface.ps1 -NoBrowser` reconoce correctamente la interfaz activa.
- Ruff sobre los dos scripts Python modificados y `git diff --check` correctos.

La prueba no añadió conversaciones ni proyectos a las bases de datos del usuario.
Es una comprobación de funcionamiento, no una nueva evaluación metodológica.

Fuente del motor: https://github.com/ggml-org/llama.cpp/releases/tag/b11146
