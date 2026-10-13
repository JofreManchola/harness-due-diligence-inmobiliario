#!/bin/zsh
# Exporta uno o varios .md a PDF (queda al lado de cada .md) con el estilo de harness/md-to-pdf.json.
# Uso: harness/scripts/md2pdf.sh [--horizontal] casos/inmueble-a/99-DECISION.md [casos/inmueble-a/analisis/*.md ...]
#   --horizontal  página apaisada (útil para tablas anchas como prospectos/PROSPECTOS.md)
set -euo pipefail

RAIZ="${0:A:h:h:h}"
CONFIG="$RAIZ/harness/md-to-pdf.json"

extra=()
if [[ "${1:-}" == "--horizontal" ]]; then
  shift
  # --pdf-options reemplaza todo pdf_options del config: se reenvía completo, solo con landscape añadido.
  extra=(--pdf-options "$(python3 -c 'import json,sys; o=json.load(open(sys.argv[1]))["pdf_options"]; o["landscape"]=True; print(json.dumps(o))' "$CONFIG")")
fi

(( $# )) || { echo "uso: md2pdf.sh [--horizontal] <archivo.md> [...]" >&2; exit 1; }

npx --yes md-to-pdf@5.2.5 --config-file "$CONFIG" "${extra[@]}" "$@"
