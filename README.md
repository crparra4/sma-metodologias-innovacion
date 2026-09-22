# Hilo · Ruta DIA

Prototipo de un asistente metodológico para desarrollar proyectos de innovación. El
backend usa FastAPI y LangGraph; el frontend usa TypeScript y Vite. La configuración
local ejecuta Qwen mediante llama.cpp y guarda las cuentas y proyectos en SQLite.

El código de la aplicación, las instrucciones de instalación y los comandos para
iniciar el modelo y la interfaz están en [prototipo/README.md](prototipo/README.md).
Las fichas de la ruta están en `prototipo/knowledge/`.

## Datos locales

Las claves de `.env`, las bases SQLite, los registros, el modelo GGUF y llama.cpp
se mantienen fuera de Git. Una copia del repositorio instala el código, pero no
incluye cuentas ni proyectos creados en otra computadora. Consulta la sección
«Preparación» del README del prototipo para configurar un entorno nuevo.
