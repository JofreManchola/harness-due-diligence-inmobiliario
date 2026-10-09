---
name: nuevo-inmueble
description: Crea la carpeta y estructura estándar para un nuevo inmueble a analizar en casos/ (documentos, texto, analisis, revision, fotos, oferta.md, README.md) y lo registra en casos/INDICE.md. Uso - /nuevo-inmueble <nombre-carpeta>
---

# /nuevo-inmueble

1. Si no existe `casos/`, ejecuta primero `harness/scripts/inicializar_casos.sh` y explícale al usuario que sus casos quedan en un directorio aparte, enlazado y versionado en un Git local sin remoto.
2. Ejecuta `harness/scripts/nuevo_inmueble.sh <nombre-carpeta>` (crea `casos/<nombre-carpeta>/`).
3. Agrega una fila al resumen de `casos/INDICE.md` (dictamen "en preparación") y una línea a la bitácora.
4. Dile al usuario qué poner en `casos/<nombre-carpeta>/documentos/` (ver `harness/plantillas/checklist-documentos.md`, gate 0 y 1 como mínimo: certificados de tradición de cada matrícula, escritura del vendedor, reglamento de PH, predial, cédulas) y que llene `oferta.md`.
5. Si `casos/perfil-comprador.md` está vacío, recuérdale llenarlo: sin él, el análisis financiero queda con supuestos.
6. Cuando estén los documentos: `/analizar-inmueble <nombre-carpeta>`.
