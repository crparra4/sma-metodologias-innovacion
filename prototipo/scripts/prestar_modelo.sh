#!/usr/bin/env bash
# Presta el modelo local de este computador a Hilo en el servidor. Uso:
#   bash scripts/prestar_modelo.sh
#
# Abre un túnel SSH cifrado: en el servidor, 127.0.0.1:18083 lleva al llama-server de este
# equipo. Mientras el túnel esté abierto, Hilo responde con el modelo local; si se cierra (o
# el computador se apaga), Hilo usa el respaldo con Claude (`respaldo_claude.py`).
#
# El servidor y la llave se leen de ~/.config/hilo/vps.env (no van en el repositorio):
#   HILO_VPS=usuario@servidor
#   HILO_TUNEL_LLAVE=~/.ssh/hilo_tunel   (opcional; ese es el valor por defecto)
# En el servidor, esa llave solo puede abrir este puerto: authorized_keys la limita con
# restrict,port-forwarding,permitlisten="127.0.0.1:18083",command="/usr/sbin/nologin".
set -euo pipefail

config="${XDG_CONFIG_HOME:-$HOME/.config}/hilo/vps.env"
if [ -f "$config" ]; then
  # shellcheck disable=SC1090
  . "$config"
fi
vps="${HILO_VPS:-}"
llave="${HILO_TUNEL_LLAVE:-$HOME/.ssh/hilo_tunel}"
llave="${llave/#\~/$HOME}"
puerto=18083
if [ -z "$vps" ]; then
  echo "Falta HILO_VPS (usuario@servidor) en $config" >&2
  exit 1
fi

proyecto="$(cd "$(dirname "$0")/.." && pwd)"
if ! curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$puerto/health"; then
  echo "El modelo local no está encendido; iniciándolo..."
  bash "$proyecto/scripts/start_interface.sh" --no-browser >/dev/null
fi

echo "Prestando el modelo a Hilo en $vps. Deja esta terminal abierta; Ctrl+C lo detiene."
trap 'echo; echo "Túnel cerrado: Hilo usará el respaldo con Claude."; exit 0' INT TERM
# Si la conexión se cae (wifi, suspensión), se vuelve a abrir sola.
while true; do
  ssh -N -i "$llave" \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=3 \
    -o IdentitiesOnly=yes -R "127.0.0.1:$puerto:127.0.0.1:$puerto" "$vps" || true
  echo "$(date +%H:%M:%S) El túnel se cerró; reintento en 10 s..."
  sleep 10
done
