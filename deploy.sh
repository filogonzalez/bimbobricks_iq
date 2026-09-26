#!/usr/bin/env bash
# Despliegue completo de BimboBricks IQ.
#   ./deploy.sh [dev|prod] [opciones extra del CLI, p.ej. -p MI_PERFIL]
# Requiere estar conectado a la VPN (FortiClient) y autenticado:  databricks auth login --host <workspace>
set -euo pipefail
cd "$(dirname "$0")"

TARGET="${1:-dev}"; shift || true
DBX=(databricks)

echo "▶ 1/4 Validando bundle ($TARGET)"
"${DBX[@]}" bundle validate -t "$TARGET" "$@"

echo "▶ 2/4 Desplegando recursos (el hook predeploy prepara el HTML)"
"${DBX[@]}" bundle deploy -t "$TARGET" "$@"

echo "▶ 3/4 Subiendo vídeo al Volume"
MEDIA=$("${DBX[@]}" bundle validate -t "$TARGET" -o json "$@" | python3 -c '
import json, sys
v = json.load(sys.stdin)["variables"]
print("/Volumes/%s/%s/media" % (v["catalog"]["value"], v["schema"]["value"]))')
if [ -f build/video.mp4 ]; then
  "${DBX[@]}" fs mkdir "dbfs:${MEDIA}/media" "$@"
  "${DBX[@]}" fs cp --overwrite build/video.mp4 "dbfs:${MEDIA}/media/video.mp4" "$@"
  echo "  ✔ ${MEDIA}/media/video.mp4"
else
  echo "  (el HTML no trae vídeo embebido; se omite)"
fi

echo "▶ 4/4 Publicando código y arrancando la App"
"${DBX[@]}" bundle run -t "$TARGET" bimbobricks_iq "$@"

echo "✔ Listo. URL de la App:"
"${DBX[@]}" bundle summary -t "$TARGET" "$@" | grep -iE 'url|bimbobricks-iq' || true
