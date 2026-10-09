#!/bin/zsh
# Crea la estructura de carpetas para un nuevo inmueble a analizar, dentro de casos/.
# Uso: harness/scripts/nuevo_inmueble.sh inmueble-b
set -euo pipefail

RAIZ="${0:A:h:h:h}"
NOMBRE="${1:?uso: nuevo_inmueble.sh <nombre-carpeta>}"
NOMBRE="${NOMBRE#casos/}"
[[ -d "$RAIZ/casos" ]] || { echo "No existe casos/. Ejecuta primero harness/scripts/inicializar_casos.sh" >&2; exit 1; }
DEST="$RAIZ/casos/$NOMBRE"

mkdir -p "$DEST"/{documentos,texto,analisis,revision,fotos}
[[ -f "$DEST/oferta.md" ]] || cp "$RAIZ/harness/plantillas/oferta.md" "$DEST/oferta.md"
[[ -f "$DEST/README.md" ]] || sed "s/{{INMUEBLE}}/$NOMBRE/g" "$RAIZ/harness/plantillas/README-inmueble.md" > "$DEST/README.md"
echo "Creado $DEST. Copia los PDFs en $DEST/documentos y llena $DEST/oferta.md"
