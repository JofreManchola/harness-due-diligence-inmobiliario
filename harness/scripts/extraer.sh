#!/bin/zsh
# Extrae el texto de todos los PDFs de <inmueble>/documentos hacia <inmueble>/texto.
# Usa la capa de texto cuando existe y OCR (Apple Vision) cuando el PDF es escaneado.
# Uso: harness/scripts/extraer.sh inmueble-a [--forzar]   (o casos/inmueble-a, o una ruta)
set -euo pipefail

HARNESS="${0:A:h:h}"
INMUEBLE="${1:?uso: extraer.sh <carpeta-inmueble> [--forzar]}"
[[ -d "$INMUEBLE" ]] || INMUEBLE="${HARNESS:h}/casos/$INMUEBLE"
[[ -d "$INMUEBLE" ]] || { echo "No encuentro la carpeta del inmueble: $1" >&2; exit 1; }
FORZAR="${2:-}"
PY="$HARNESS/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "Creando entorno Python del harness (una sola vez)..."
  python3 -m venv "$HARNESS/.venv"
  "$HARNESS/.venv/bin/pip" -q install pyobjc-framework-Vision pyobjc-framework-Quartz
fi

mkdir -p "$INMUEBLE/texto"
for pdf in "$INMUEBLE"/documentos/*.pdf(N); do
  salida="$INMUEBLE/texto/${pdf:t:r}.txt"
  if [[ -f "$salida" && "$salida" -nt "$pdf" && "$FORZAR" != "--forzar" ]]; then
    echo "ya extraído: ${pdf:t}"
    continue
  fi
  "$PY" -I "$HARNESS/scripts/pdf2txt.py" "$pdf" "$salida"
done
echo "Listo. Textos en $INMUEBLE/texto/"
