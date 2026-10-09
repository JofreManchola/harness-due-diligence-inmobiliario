---
name: comparar-inmuebles
description: Compara los inmuebles ya analizados (carpetas de casos/ con 99-DECISION.md) en una tabla única de scorecard, precio, riesgos y costo mensual, y recomienda cuál priorizar. Uso - /comparar-inmuebles [inmueble-a inmueble-b ...]
---

# /comparar-inmuebles

1. Encuentra las carpetas `casos/*/` con `99-DECISION.md` (o usa las indicadas).
2. De cada una toma: dictamen, confianza, scorecard por dimensión, precio pedido, rango de mercado, precio máximo, $/m², costo total de adquisición y costo mensual de tenencia (de `80-financiero.md`), riesgos ALTO/BLOQUEANTE abiertos y número de pendientes.
3. Escribe `casos/comparativo.md`: tabla comparativa, ranking ponderado según `casos/perfil-comprador.md`, y una recomendación de cuál avanzar primero y qué verificar antes. Agrega una línea a la bitácora de `casos/INDICE.md`.
4. No reinterpretes los dictámenes: si los análisis tienen fechas muy distintas o supuestos diferentes (tasas, precio), adviértelo.
