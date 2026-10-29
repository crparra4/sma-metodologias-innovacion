#!/usr/bin/env bash
# Abre Hilo a internet con un túnel rápido de Cloudflare, para entrar desde otro computador.
# Uso:  bash scripts/abrir_tunel.sh [--port 8787]
#
# - Hilo y el modelo siguen corriendo aquí; afuera solo se ve la página, por https.
# - La dirección (https://…trycloudflare.com) cambia cada vez que se abre el túnel.
# - Para crear una cuenta desde afuera hace falta el código de invitación que se muestra al
#   abrir. Quien ya tiene cuenta entra con su usuario y contraseña.
# - Ctrl+C cierra el túnel. Hilo sigue funcionando en este computador.
# - Este computador tiene que seguir encendido (y sin suspenderse) mientras lo usen.
set -euo pipefail

proyecto="$(cd "$(dirname "$0")/.." && pwd)"
puerto=8787
if [ "${1:-}" = "--port" ] && [ -n "${2:-}" ]; then puerto="$2"; fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Falta cloudflared. En Ubuntu o Mint:" >&2
  echo "  curl -L -o /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb" >&2
  echo "  sudo apt install /tmp/cloudflared.deb" >&2
  exit 1
fi

# Ocho caracteres sin los que se confunden (0/O, 1/I/L): 31^8 combinaciones, y el servidor
# solo deja 20 intentos por minuto. Se puede fijar uno propio con HILO_CODIGO_INVITACION.
codigo="${HILO_CODIGO_INVITACION:-$(python3 -c 'import secrets; a = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; c = "".join(secrets.choice(a) for _ in range(8)); print(c[:4] + "-" + c[4:])')}"

# Hilo lee estas dos variables al arrancar, así que se reinicia con ellas. Los proyectos y
# las cuentas no se pierden; una respuesta que se esté generando en ese momento, sí.
export HILO_HOSTS_PUBLICOS="*.trycloudflare.com"
export HILO_CODIGO_INVITACION="$codigo"
echo "Reiniciando Hilo para que acepte la dirección del túnel..."
bash "$proyecto/scripts/stop_interface.sh" --port "$puerto" >/dev/null 2>&1 || true
bash "$proyecto/scripts/start_interface.sh" --port "$puerto" --no-browser

registro="$(mktemp)"
cloudflared tunnel --url "http://127.0.0.1:$puerto" --no-autoupdate >"$registro" 2>&1 &
tunel=$!
cerrar() {
  kill "$tunel" 2>/dev/null || true
  rm -f "$registro"
  echo
  echo "Túnel cerrado: Hilo ya no se ve desde internet. En este computador sigue en http://127.0.0.1:$puerto"
}
trap cerrar EXIT
trap 'exit 0' INT TERM HUP

direccion=""
for _ in $(seq 60); do
  direccion="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$registro" | head -1 || true)"
  [ -n "$direccion" ] && break
  if ! kill -0 "$tunel" 2>/dev/null; then
    echo "cloudflared terminó sin abrir el túnel:" >&2
    cat "$registro" >&2
    exit 1
  fi
  sleep 1
done
if [ -z "$direccion" ]; then
  echo "Cloudflare no entregó una dirección en un minuto. Revisa la conexión a internet." >&2
  exit 1
fi

cat <<EOF

  Hilo está abierto en internet
  ─────────────────────────────
  Dirección:             $direccion
  Código de invitación:  $codigo   (solo para crear cuentas nuevas)

  Comparte la dirección y el código solo con quien deba entrar.
  Deja esta terminal abierta; Ctrl+C cierra el túnel.

EOF
wait "$tunel"
