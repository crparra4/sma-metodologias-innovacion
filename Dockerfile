# syntax=docker/dockerfile:1.7
# Imagen de la aplicación Hilo (monolito modular): API, agentes e interfaz web en un contenedor.
#
# El servidor del modelo (llama.cpp) no va aquí: necesita la GPU del computador del equipo y
# llega por el túnel SSH. El proxy reverso (nginx) tampoco: es del servidor y atiende otros sitios.
# Detalle y pasos de despliegue en docs/contenedores.md.

ARG PYTHON_VERSION=3.13
ARG NODE_VERSION=24
ARG UV_VERSION=0.12.21

# ---------------------------------------------------------------- 1. interfaz web (Vite)
FROM node:${NODE_VERSION}-slim AS interfaz
WORKDIR /interfaz
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ---------------------------------------------------------------- 2. dependencias de Python
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:${PYTHON_VERSION}-slim AS dependencias
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Primero solo el lockfile: la capa de dependencias se reutiliza mientras no cambien.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
# Instalación editable a propósito: config.py ubica las fichas y la interfaz relativas a src/.
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------- 3. imagen final
FROM python:${PYTHON_VERSION}-slim
ARG UID=1000
ARG GID=1000
# Mismo UID que el usuario del servidor, para escribir en las carpetas de datos montadas.
RUN groupadd --gid "${GID}" hilo \
    && useradd --uid "${UID}" --gid hilo --no-create-home --home-dir /tmp hilo \
    && mkdir -p /datos /app/data \
    && chown hilo:hilo /datos /app/data
WORKDIR /app
COPY --from=dependencias /app/.venv ./.venv
COPY --from=dependencias /app/src ./src
COPY knowledge ./knowledge
COPY --from=interfaz /interfaz/dist ./frontend/dist
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    RUTA_DIA_DATA_DIR=/datos \
    HILO_PUERTO=8787
USER hilo
VOLUME ["/datos", "/app/data"]
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"HILO_PUERTO\"]}/api/status', timeout=4)"]
# Escucha solo en 127.0.0.1: con la red del host queda detrás del nginx del servidor.
CMD ["python", "-c", "import os; from hilo.web import run_server; run_server(int(os.environ['HILO_PUERTO']))"]
