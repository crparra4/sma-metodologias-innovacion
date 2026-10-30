#!/usr/bin/env bash
# Construye la interfaz en Linux. Uso:  bash scripts/build_frontend.sh
#
# Solo hace falta si cambiaste algo en frontend/ desde Linux: la carpeta dist/ ya construida
# sirve igual en los dos sistemas.
#
# Trabaja sobre una copia fuera del proyecto. En un disco compartido con Windows,
# frontend/node_modules es el de Windows (binarios y enlaces propios de ese sistema), y
# reinstalarlo desde Linux lo dañaría para Windows.
set -euo pipefail

frontend="$(cd "$(dirname "$0")/../frontend" && pwd)"
trabajo="${XDG_CACHE_HOME:-$HOME/.cache}/hilo-frontend"

for programa in pnpm rsync; do
  if ! command -v "$programa" >/dev/null 2>&1; then
    echo "Falta $programa. En Ubuntu o Mint: sudo apt install rsync nodejs && npm install -g pnpm" >&2
    exit 1
  fi
done

mkdir -p "$trabajo"
# --chmod: en NTFS las carpetas pueden venir marcadas de solo lectura y la copia las heredaría.
rsync -a --chmod=u+rwX --delete --exclude node_modules --exclude dist "$frontend/" "$trabajo/"
(cd "$trabajo" && pnpm install --frozen-lockfile && pnpm build)

# Se reemplaza solo el resultado; el código fuente del proyecto no se toca.
rsync -a --delete "$trabajo/dist/" "$frontend/dist/"
echo "Interfaz construida en $frontend/dist"
