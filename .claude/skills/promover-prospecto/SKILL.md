---
name: promover-prospecto
description: Convierte un prospecto de casos/prospectos en un caso de due diligence (carpeta en casos/ con oferta.md prellenada desde el anuncio y la ficha), lo marca como promovido en el registro y lista los documentos que hay que pedir al vendedor. Uso - /promover-prospecto <id-prospecto> [nombre-caso]
---

# /promover-prospecto

1. Lee `casos/prospectos/registro.json[<id>]` y `casos/prospectos/fichas/<id>.md`. Si el prospecto no tiene ficha o está `descartado`, avisa y pide confirmación antes de seguir.
2. Nombre del caso: el que indique el usuario o `inmueble-<siguiente letra libre>` (mira `casos/INDICE.md`).
3. Ejecuta `/nuevo-inmueble <nombre-caso>` (crea la carpeta y la fila en el índice).
4. Prellena `casos/<nombre-caso>/oferta.md` con lo que se sabe del anuncio, cada dato con su fuente (URL y fecha): precio pedido e historial de precio, administración, área, piso, parqueadero, dirección/conjunto, enlaces a todos los portales donde aparece, y las preguntas pendientes de la ficha. Los datos del vendedor solo si el usuario los da.
5. Si hay fotos del anuncio útiles, no las descargues de forma masiva: anota las URLs en `oferta.md`. El comprador agrega sus propias fotos de la visita a `fotos/`.
6. En `registro.json`: `estado` = `promovido`, `nota` = `caso <nombre-caso>`. Re-genera el tablero (`python3 -I harness/scripts/barrer_portales.py casos/prospectos --tablero`).
7. Dile al usuario qué pedir al vendedor para poder correr `/analizar-inmueble <nombre-caso>` (gate 0 y 1 de `harness/plantillas/checklist-documentos.md`: certificados de tradición de cada matrícula —apto, parqueadero, depósito—, escritura de adquisición, reglamento de PH, predial, paz y salvo de administración, cédulas) y que con el certificado de tradición en mano ya se puede verificar el área privada y si el parqueadero tiene matrícula propia.
