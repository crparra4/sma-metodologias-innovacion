# Hilo en contenedores Docker

Estado (27 oct 2026): los archivos están listos y la imagen se construyó y probó en el servidor
sin tocar el servicio en uso. El cambio del servidor a contenedores está planeado para noviembre
de 2026; hasta entonces Hilo sigue corriendo como servicio systemd.

## Qué va en contenedor y qué no

Hilo es un monolito modular, así que la aplicación es **un solo contenedor**: la API (FastAPI con
Uvicorn), los agentes (LangGraph) y la interfaz web ya compilada.

| Pieza | ¿Contenedor? | Por qué |
|---|---|---|
| Aplicación Hilo | Sí (`hilo`) | Es lo que se despliega y se actualiza. |
| Interfaz web | Dentro de la misma imagen | Se compila con Vite en una etapa de la construcción y la sirve FastAPI. |
| Datos (SQLite y registros JSONL) | No: carpetas montadas | Deben sobrevivir a cada versión de la imagen. |
| Proxy reverso (nginx) | No | Es del servidor y atiende también otros sitios de la empresa. |
| Servidor del modelo (llama.cpp) | No | Necesita la GPU del computador del equipo; llega por el túnel SSH. |

## Archivos

- `Dockerfile`: construcción en tres etapas. (1) Node 24 compila la interfaz con pnpm y Vite;
  (2) uv 0.12.21 instala las dependencias de Python desde `uv.lock` (versiones exactas); (3) la
  imagen final, sobre `python:3.13-slim`, solo lleva el entorno, el código, las fichas y la
  interfaz compilada. Corre con un usuario sin privilegios y tiene comprobación de salud
  (`/api/status`).
- `compose.yaml`: el servicio `aplicacion`. Usa la red del host para seguir escuchando en
  `127.0.0.1:8787` detrás de nginx y alcanzar el túnel del modelo en `127.0.0.1:18083`. Monta
  los datos, lee la configuración y la clave de Claude de los mismos `.env` de hoy (fuera de la
  imagen) y aplica endurecimiento: sistema de archivos de solo lectura, sin capacidades extra y
  sin escalamiento de privilegios. Se reinicia solo y limita el tamaño de sus registros.
- `.dockerignore`: deja fuera secretos, datos, pruebas y entornos locales.

## Prueba del 27 de octubre de 2026

En el servidor (Ubuntu 24.04 ARM64, Docker 29.5, Compose 5.1), en una carpeta aparte, en el
puerto 8790 y con datos temporales, mientras el servicio seguía en el 8787:

- La imagen se construyó en 2 min 8 s y pesa 1,45 GB.
- El contenedor quedó `healthy`, corrió con el UID 1001 (el del usuario `ubuntu`) y el
  sistema de archivos de solo lectura impidió escribir fuera de los volúmenes.
- Cuenta, proyecto y práctica: 201; lista de prácticas: 200; práctica inexistente: 404; cuenta
  repetida: 409; interfaz web: 200. Memoria: 157 MB.
- Ajuste que salió de la prueba: el usuario del servidor tiene UID 1001, no 1000; por eso
  `compose.yaml` fija el usuario al ejecutar (`HILO_UID`, `HILO_GID`).

Al terminar se borraron el contenedor, la imagen y los datos de prueba.

## Pasos para el cambio (noviembre de 2026)

En el servidor, sin sesiones en curso:

```bash
cd ~/hilo && cp -a datos respaldos/datos-antes-de-docker-$(date +%Y%m%d)
cd ~/hilo/app && printf "HILO_UID=$(id -u)\nHILO_GID=$(id -g)\n" > .env
docker compose build
sudo systemctl stop hilo && sudo systemctl disable hilo
docker compose up -d
docker compose ps        # debe decir healthy
curl -s http://127.0.0.1:8787/api/status
```

Si algo falla, se vuelve al servicio anterior en un minuto:

```bash
docker compose down && sudo systemctl enable --now hilo
```

Para cada versión nueva: actualizar el código en `~/hilo/app` y repetir
`docker compose up -d --build`. Conviene etiquetar la imagen (`HILO_VERSION=2026-11-xx`) para
poder volver a la anterior.

## Lo que queda para después

- Publicar la imagen en un registro (por ejemplo, GitHub Container Registry) y construirla con
  integración continua en lugar de en el servidor.
- Si algún día se separan servicios (Anexo G de la tesis), cada contexto delimitado tendría su
  propio contenedor y el `compose.yaml` crecería con ellos.
