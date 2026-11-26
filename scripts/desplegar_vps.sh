#!/usr/bin/env bash
# Despliega en la VPS una versión de Hilo publicada por GitHub Actions en GHCR.
#
# Se instala UNA vez fuera del código (`~/hilo/desplegar.sh`, ver docs/despliegue-automatico.md)
# y la llave SSH de GitHub queda limitada a correr solo este script (`command=` en
# authorized_keys). Por eso no confía en nada de lo que llega:
#   - la orden llega en SSH_ORIGINAL_COMMAND: «desplegar sha-abc1234 usuario-de-github»;
#   - el token temporal de GHCR llega por la entrada estándar (vence al terminar el workflow);
#   - la imagen la fija este servidor (HILO_IMAGEN), no quien llama.
#
# Pasos: descarga la imagen nueva (Hilo sigue en línea), detiene, respalda los datos, arranca la
# nueva y espera a que el contenedor diga «healthy». Si no lo logra, vuelve a la versión anterior
# y termina con error para que el workflow quede en rojo.
set -euo pipefail
umask 077

HILO_DIR="${HILO_DIR:-$HOME/hilo}"
APP_DIR="${HILO_APP_DIR:-$HILO_DIR/app}"
IMAGEN="${HILO_IMAGEN:-ghcr.io/crparra4/sma-metodologias-innovacion}"
CONTENEDOR="${HILO_CONTENEDOR:-hilo}"
ESPERA_SALUD="${HILO_ESPERA_SALUD:-150}"
RESPALDOS_A_CONSERVAR="${HILO_RESPALDOS:-5}"
ESTADO="$HILO_DIR/despliegue"
REGISTRO="${IMAGEN%%/*}"

falla() { echo "ERROR: $*" >&2; exit 1; }
nota() { echo "[$(date '+%H:%M:%S')] $*"; }

mkdir -p "$ESTADO" "$HILO_DIR/respaldos"
# Un despliegue a la vez, aunque GitHub lance dos seguidos.
exec 9>"$ESTADO/candado"
flock -n 9 || falla "ya hay un despliegue en curso."

orden="${SSH_ORIGINAL_COMMAND:-$*}"
read -r accion version usuario resto <<<"$orden" || true
[[ "${accion:-}" == "desplegar" && -z "${resto:-}" ]] \
  || falla "orden no permitida. Uso: desplegar sha-<commit> <usuario-github>"
[[ "${version:-}" =~ ^sha-[0-9a-f]{7,40}$ ]] || falla "versión no válida: ${version:-vacía}"
[[ "${usuario:-}" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,38}$ ]] || falla "usuario no válido."

# Versión con la que se corre docker compose: «imagen:etiqueta».
con_version() {
  local referencia="$1"; shift
  (cd "$APP_DIR" && HILO_IMAGEN="${referencia%:*}" HILO_VERSION="${referencia##*:}" \
    docker compose "$@")
}

salud() {
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}sin-salud{{end}}' \
    "$CONTENEDOR" 2>/dev/null || echo "ausente"
}

esperar_salud() {
  local limite=$((SECONDS + ESPERA_SALUD)) estado
  while ((SECONDS < limite)); do
    estado="$(salud)"
    [[ "$estado" == "healthy" ]] && return 0
    [[ "$estado" == "unhealthy" || "$estado" == "ausente" ]] && break
    sleep 3
  done
  echo "estado final: $(salud)" >&2
  return 1
}

nueva="$IMAGEN:$version"
anterior="$(cat "$ESTADO/version-actual" 2>/dev/null || true)"
# La primera vez, la versión anterior es la imagen que se construyó en el propio servidor.
if [[ -z "$anterior" ]] && docker image inspect hilo:local >/dev/null 2>&1; then
  anterior="hilo:local"
fi
nota "Desplegando $nueva (anterior: ${anterior:-ninguna})"

# El token solo vive mientras dura este script.
IFS= read -r token || true
# Sin el \r final que deja un cliente de Windows.
token="${token%$'\r'}"
[[ -n "${token:-}" ]] || falla "falta el token de GHCR por la entrada estándar."
trap 'docker logout "$REGISTRO" >/dev/null 2>&1 || true' EXIT
printf '%s' "$token" | docker login "$REGISTRO" -u "$usuario" --password-stdin >/dev/null
unset token

# 1. Descargar mientras Hilo sigue atendiendo.
con_version "$nueva" pull --quiet aplicacion

# 2. Detener y respaldar. Con Hilo detenido, las bases SQLite quedan consistentes.
nota "Deteniendo Hilo y respaldando los datos"
con_version "${anterior:-$nueva}" stop aplicacion || true
respaldo="$HILO_DIR/respaldos/datos-$(date +%Y%m%d-%H%M%S)-antes-de-$version.tar.gz"
tar -czf "$respaldo" -C "$HILO_DIR" datos
# shellcheck disable=SC2012  # nombres propios, sin espacios
ls -1t "$HILO_DIR"/respaldos/datos-*-antes-de-*.tar.gz 2>/dev/null \
  | tail -n +"$((RESPALDOS_A_CONSERVAR + 1))" | xargs -r rm -f --

# 3. Arrancar la versión nueva y comprobar que responde.
nota "Arrancando $nueva"
if con_version "$nueva" up -d --no-build --force-recreate aplicacion && esperar_salud; then
  echo "$nueva" > "$ESTADO/version-actual"
  echo "$(date -Is) ok $nueva" >> "$ESTADO/historial.log"
  # Se guardan la versión nueva y la anterior; las demás se borran para no llenar el disco.
  docker images "$IMAGEN" --format '{{.Repository}}:{{.Tag}}' \
    | grep -vxF -e "$nueva" -e "${anterior:-$nueva}" | xargs -r docker rmi >/dev/null 2>&1 || true
  nota "Listo: $nueva está en línea. Respaldo: $respaldo"
  exit 0
fi

echo "$(date -Is) fallo $nueva" >> "$ESTADO/historial.log"
docker logs --tail 40 "$CONTENEDOR" >&2 || true
if [[ -n "$anterior" ]]; then
  nota "La versión nueva no quedó sana: volviendo a $anterior"
  con_version "$anterior" up -d --no-build --force-recreate aplicacion
  esperar_salud && nota "$anterior volvió a estar en línea." \
    || echo "ATENCIÓN: $anterior tampoco quedó sana; revisar a mano." >&2
fi
falla "el despliegue de $nueva no se completó."
