#!/bin/zsh
# Exporta uno o varios .md a PDF (queda al lado de cada .md) con el estilo de harness/md-to-pdf.json.
# Uso: harness/scripts/md2pdf.sh casos/inmueble-a/99-DECISION.md [casos/inmueble-a/analisis/*.md ...]
set -euo pipefail

RAIZ="${0:A:h:h:h}"
(( $# )) || { echo "uso: md2pdf.sh <archivo.md> [...]" >&2; exit 1; }

npx --yes md-to-pdf@5.2.5 --config-file "$RAIZ/harness/md-to-pdf.json" "$@"
