#!/usr/bin/env bash
# Inicia Hilo en Linux. Uso:  bash scripts/start_interface.sh [--port 8787] [--no-browser]
#
# La primera vez crea el entorno de Python y descarga el modelo si falta. El entorno vive
# fuera del proyecto (por defecto ~/.venvs/hilo; cámbialo con HILO_VENV): en un disco
# compartido con Windows, `.venv` es el de Windows y no sirve aquí.
set -euo pipefail

proyecto="$(cd "$(dirname "$0")/.." && pwd)"
export UV_PROJECT_ENVIRONMENT="${HILO_VENV:-$HOME/.venvs/hilo}"
python="$UV_PROJECT_ENVIRONMENT/bin/python"

if [ ! -x "$python" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "Falta uv. Instálalo con:  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo "Luego abre una terminal nueva y repite este comando." >&2
    exit 1
  fi
  echo "Creando el entorno de Python en $UV_PROJECT_ENVIRONMENT ..."
  # --frozen: instala lo que dice uv.lock sin reescribirlo.
  (cd "$proyecto" && uv sync --extra dev --frozen)
fi

cd "$proyecto"
exec "$python" scripts/interface.py start "$@"
