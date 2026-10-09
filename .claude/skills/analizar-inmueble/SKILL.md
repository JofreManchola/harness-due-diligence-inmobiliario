---
name: analizar-inmueble
description: Ejecuta el due diligence completo de un inmueble en Bogotá con el equipo de agentes expertos (títulos, PH, fiscal, valoración, urbanismo, cumplimiento, técnico, financiero, transacción, abogado del diablo y comité) y produce el dictamen de compra. Uso - /analizar-inmueble <carpeta-inmueble> [solo:<rol>]
---

# /analizar-inmueble

Argumento: nombre del caso (p. ej. `inmueble-a`); la carpeta es `casos/<inmueble>/`. Opcional `solo:<rol>` para re-ejecutar un especialista y luego el comité (p. ej. cuando llega un documento nuevo).

Eres el **coordinador**. No haces el análisis de fondo: preparas, delegas, controlas calidad y cierras. Lee `CLAUDE.md` antes de empezar.

## Fase 0 — Preparación (tú)
1. Verifica la estructura (`documentos/`, `texto/`, `analisis/`, `revision/`). Si los PDFs están sueltos en la raíz de la carpeta, muévelos a `documentos/`. Crea `README.md` y `oferta.md` desde `harness/plantillas/` si no existen.
2. Ejecuta `harness/scripts/extraer.sh <inmueble>` (texto + OCR; el reglamento puede tardar varios minutos → en segundo plano).
3. Lee `casos/perfil-comprador.md` y `casos/<inmueble>/oferta.md`. Si faltan datos clave (precio pedido, objetivo de compra, presupuesto), no te detengas: los especialistas trabajarán con supuestos explícitos y el comité los listará como pendientes.

## Fase 1 — Documentalista
Lanza el agente `documentalista` y espera su resultado (`00-ficha.md`, `01-inventario-documental.md`). Revisa la ficha: si hay inconsistencias críticas, compártelas en el prompt de los especialistas.

## Fase 2 — Especialistas en paralelo (un solo mensaje con varias llamadas Agent)
`abogado-titulos`, `analista-propiedad-horizontal`, `analista-fiscal-catastral`, `perito-valuador`, `analista-urbano-riesgos`, `oficial-cumplimiento`, `inspector-tecnico`.

## Fase 3 — Integradores (en paralelo, cuando terminen los de la fase 2)
`analista-financiero` (necesita 20, 30, 40, 70) y `abogado-transaccional` (necesita 10–70; el financiero puede faltar: que lo lea si ya existe).

## Fase 4 — `abogado-del-diablo`

## Fase 5 — `comite-decision` → `99-DECISION.md`, `pendientes.md`, `README.md`.

## Cómo invocar a cada rol
- Si el tipo de agente con ese nombre está disponible, usa `subagent_type: <rol>`.
- Si no (p. ej. el harness se creó en esta misma sesión y aún no se recargó), usa `subagent_type: general-purpose` y en el prompt indica: *"Asume el rol definido en `.claude/agents/<rol>.md` (léelo completo primero y síguelo al pie de la letra), junto con las reglas de `CLAUDE.md`."*
- En el prompt incluye siempre: ruta absoluta de la carpeta del inmueble, el archivo de salida esperado, datos clave de la ficha y cualquier advertencia del coordinador.

## Control de calidad (tú, entre fases)
- Cada informe existe, tiene semáforo/severidades, cita fuentes y termina con conclusión y acciones requeridas.
- Si un informe contradice la ficha en un dato crítico, pide corrección al agente (SendMessage) antes de avanzar.
- No reescribas los informes de los especialistas; si discrepas, anótalo para el comité.

## Cierre
1. Actualiza la fila del caso en `casos/INDICE.md` (dictamen, precios, confianza, riesgos abiertos, fecha, próximo paso) y agrega una línea a la bitácora.
2. Sugiere al usuario versionar el resultado en el repo privado: `git -C casos add -A && git -C casos commit -m "<inmueble>: <qué cambió>"`. No hagas el commit sin que lo pida.
3. Responde al usuario con: dictamen en una línea, precio máximo recomendado, los 3–5 riesgos/condiciones principales y los pendientes más urgentes, con enlaces a `99-DECISION.md` y `pendientes.md`.
