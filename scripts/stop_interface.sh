#!/usr/bin/env bash
# Detiene Hilo en Linux. Uso:  bash scripts/stop_interface.sh [--port 8787] [--model]
#
# Con --model detiene también el servidor de Qwen, que ocupa la memoria de la GPU.
set -euo pipefail

proyecto="$(cd "$(dirname "$0")/.." && pwd)"
python="${HILO_VENV:-$HOME/.venvs/hilo}/bin/python"
if [ ! -x "$python" ]; then
  echo "No existe el entorno de Python ($python): Hilo no se ha iniciado en este equipo." >&2
  exit 1
fi

modelo=0
argumentos=()
for argumento in "$@"; do
  if [ "$argumento" = "--model" ]; then modelo=1; else argumentos+=("$argumento"); fi
done

cd "$proyecto"
"$python" scripts/interface.py stop "${argumentos[@]}"
if [ "$modelo" = 1 ]; then
  "$python" scripts/local_model.py stop
fi
