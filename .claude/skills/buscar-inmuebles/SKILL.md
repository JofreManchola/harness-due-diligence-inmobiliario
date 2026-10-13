---
name: buscar-inmuebles
description: Busca apartamentos en venta que cumplan los criterios del comprador (presupuesto con gastos, área privada, parqueadero, piso, zona como polígono) en los portales de Bogotá, los ubica por dirección con Catastro, los filtra y prioriza, y mantiene el tablero casos/prospectos/PROSPECTOS.md. Uso - /buscar-inmuebles [criterios en texto libre] [revisar:<n>] [solo-tablero]
---

# /buscar-inmuebles

Eres el **coordinador de la búsqueda**. Preparas los criterios, corres el barrido, delegas la exploración y la preselección, y cierras con un tablero priorizado. Lee `CLAUDE.md` y `harness/conocimiento/busqueda-inmuebles.md` antes de empezar.

Argumentos opcionales: criterios en texto libre (actualizan `criterios.json`), `revisar:<n>` (cuántos prospectos abre el analista; 15 por defecto), `solo-tablero` (re-genera el tablero y termina).

## Fase 0 — Criterios y zona (tú)
1. Si no existe `casos/prospectos/`, créala con `fichas/` y `barridos/`, y copia `harness/plantillas/criterios-busqueda.json` como `casos/prospectos/criterios.json`.
2. Si el usuario dio criterios nuevos, actualiza `criterios.json` (y la sección Finanzas/Objetivo de `casos/perfil-comprador.md` si son datos del comprador, con fecha):
   - `precio_compra_max` = (presupuesto total − costos fijos) / (1 + tasa de gastos de cierre). La tasa sale de `harness/conocimiento/costos-transaccion-bogota.md` según la financiación; si no se conoce, usa el escenario de crédito del 70 % y márcalo como SUPUESTO.
   - `precio_pedido_max` = `precio_compra_max` / (1 − descuento de negociación esperado, 5–8 %).
3. **Zona**: si el usuario describe límites (vías, humedales, barrios), construye `casos/prospectos/zona.geojson` con geometría real, no a ojo:
   - Vías y humedales de OpenStreetMap: Overpass (`overpass-api.de`, `maps.mail.ru/osm/tools/overpass`, `overpass.kumi.systems`; si uno da 504, prueba otro) y Nominatim con `polygon_geojson=1` para áreas con nombre. Calcula los vértices como intersecciones de las vías.
   - Valida el polígono con las direcciones: `python3 -I harness/scripts/zona.py casos/prospectos/zona.geojson --direccion "<dirección conocida>"` y lista los sectores catastrales que cubre (capa `catastro/sectorcatastral`, ver `busqueda-inmuebles.md`).
   - Guarda en `properties` los límites en palabras, las fuentes y la fecha, y muéstrale al usuario los barrios que quedaron dentro y en el borde para que corrija.
4. Ajusta las fuentes de `criterios.json` a la zona (slugs de Fincaraíz y Ciencuadras por localidad/barrio; radio de Metrocuadrado que cubra el polígono desde su centroide).

## Fase 1 — Barrido automático (tú)
`python3 -I harness/scripts/barrer_portales.py casos/prospectos` (≈ 5–10 min; en segundo plano). Lee `barridos/<hoy>/resumen.md`: portales vacíos, conteos, motivos de descarte, mediana de $/m².

## Fase 2 — Exploración complementaria (en paralelo con el inicio de la Fase 3)
Lanza `explorador-mercado` con: la carpeta de prospectos, la fecha del barrido, los portales que fallaron y los barrios de la zona. Él agrega `crudo-manual.jsonl` y re-ejecuta el script con `--sin-descarga`.

## Fase 3 — Preselección
Lanza `analista-prospectos` con la lista de IDs a revisar: los `revisar:<n>` primeros por puntaje de `candidatos.jsonl` **más** todos los que tengan piso ≥ `piso_deseable_min`, los que bajaron de precio y los nuevos del explorador. Si son más de ~20, divide en dos agentes en paralelo (por rango de puntaje): cada uno escribe `barridos/<hoy>/revision-<lote>.json` y `analisis-<lote>.md` en vez de editar `registro.json`, y tú los incorporas con `barrer_portales.py casos/prospectos --fusionar barridos/<hoy>/revision-A.json barridos/<hoy>/revision-B.json` y unes los informes en `analisis.md`.

## Cómo invocar a cada rol
Igual que en `/analizar-inmueble`: `subagent_type: <rol>` si existe; si no, `general-purpose` con *"Asume el rol definido en `.claude/agents/<rol>.md` (léelo completo primero y síguelo al pie de la letra), junto con las reglas de `CLAUDE.md`."* Incluye rutas absolutas, la fecha del barrido y los criterios clave.

## Control de calidad (tú)
- Cada prospecto `preseleccionado`/`contactar`/`visitar` tiene ficha, y su área, parqueadero y piso tienen fuente o están marcados por confirmar.
- Ningún prospecto descartado sin motivo. Ningún nombre, teléfono ni cédula de vendedores en el registro ni en las fichas.
- `PROSPECTOS.md` re-generado (`barrer_portales.py casos/prospectos --tablero`).

## Cierre
1. Agrega una línea a la bitácora de `casos/INDICE.md` ("búsqueda <fecha>: N leídos, M candidatos, K preseleccionados").
2. Sugiere versionar: `git -C casos add -A && git -C casos commit -m "prospectos: barrido <fecha>"`. No hagas el commit sin que lo pida.
3. Responde con: los 3–5 mejores prospectos (precio, área, piso, parqueadero, $/m² vs. zona, por qué), cuántos quedaron por confirmar, los huecos de cobertura, y el siguiente paso: contactar con las preguntas de la ficha y, para el que pase la visita, `/promover-prospecto <id>`.
