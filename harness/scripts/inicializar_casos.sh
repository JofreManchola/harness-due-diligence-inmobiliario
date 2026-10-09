#!/bin/zsh
# Prepara el directorio privado de casos FUERA del repo del harness, lo enlaza como ./casos
# (symlink ignorado por Git) y lo inicializa como repositorio Git local, sin remoto.
# También activa el pre-commit del harness, que bloquea commits con datos de casos.
# Uso: harness/scripts/inicializar_casos.sh [ruta-casos]   (por defecto: ../<carpeta-del-harness>-casos)
set -euo pipefail

RAIZ="${0:A:h:h:h}"
CASOS="${${1:-${RAIZ:h}/${RAIZ:t}-casos}:a}"
ENLACE="$RAIZ/casos"

[[ "$CASOS" == "$RAIZ" || "$CASOS" == "$RAIZ"/* ]] && { echo "El directorio de casos debe quedar fuera de $RAIZ" >&2; exit 1; }
[[ -e "$ENLACE" && ! -L "$ENLACE" ]] && { echo "$ENLACE ya existe y no es un symlink; muévelo antes" >&2; exit 1; }

mkdir -p "$CASOS"
# Enlace relativo si es hermano del harness (sobrevive si se mueven juntos), absoluto si no.
if [[ "${CASOS:h}" == "${RAIZ:h}" ]]; then ln -sfn "../${CASOS:t}" "$ENLACE"; else ln -sfn "$CASOS" "$ENLACE"; fi

[[ -f "$CASOS/perfil-comprador.md" ]] || cp "$RAIZ/harness/plantillas/perfil-comprador.md" "$CASOS/"
[[ -f "$CASOS/INDICE.md" ]] || cp "$RAIZ/harness/plantillas/INDICE-casos.md" "$CASOS/INDICE.md"
[[ -f "$CASOS/.gitignore" ]] || cp "$RAIZ/harness/plantillas/gitignore-casos" "$CASOS/.gitignore"
[[ -d "$CASOS/.git" ]] || git -C "$CASOS" init -q -b main

if git -C "$RAIZ" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$RAIZ" config core.hooksPath harness/git-hooks
fi

echo "Casos en $CASOS (enlazado como casos/). Repo privado: git -C casos status"
[[ -z "$(git -C "$CASOS" remote)" ]] || echo "ADVERTENCIA: el repo de casos tiene remoto configurado" >&2
