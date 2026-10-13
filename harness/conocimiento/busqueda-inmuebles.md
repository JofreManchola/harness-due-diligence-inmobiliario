# Búsqueda de inmuebles — portales, lectura de anuncios y preselección

> Lo usan `/buscar-inmuebles`, `explorador-mercado` y `analista-prospectos`. Los portales cambian su HTML y sus APIs sin aviso: lo descrito aquí se comprobó el **2026-10-13**. Si un portal deja de responder, el resumen del barrido lo advierte y el explorador lo cubre a mano.

## Flujo

```
criterios.json + zona.geojson
        │
        ▼
barrer_portales.py ──► crudo-<portal>.jsonl ──► filtros duros ──► ubicación (Catastro) ──► duplicados ──► puntaje
        ▲                                                                                              │
explorador-mercado ──► crudo-manual.jsonl                                                              ▼
                                                    analista-prospectos ◄── candidatos.jsonl ──► registro.json ──► PROSPECTOS.md
                                                          │
                                                          ▼
                                              fichas/<id>.md ──► contacto / visita ──► /promover-prospecto ──► /analizar-inmueble
```

## Portales

| Portal | Cómo lo lee el script | Qué trae | Limitaciones |
|---|---|---|---|
| Fincaraíz | HTML de búsqueda `fincaraiz.com.co/venta/apartamentos/<slug>[/desde-<p>/hasta-<p>][/pagina<n>]`, JSON `__NEXT_DATA__` (`props.pageProps.fetchResult.searchFast`) | precio, administración, **área privada (`m2apto`) y construida (`m2Built`)**, garajes, **piso**, estrato, antigüedad, coordenadas, dirección (a veces completa), descripción | 21 anuncios por página. Muchas inmobiliarias ponen la misma cifra en ambas áreas. **El listado por localidad no trae todo**: muchos anuncios solo salen por barrio (`<barrio>/zona-occidental/bogota`), así que hay que poner slugs de localidad y de cada barrio. Limita la frecuencia (tras 2–5 páginas responde vacío): el script espera 4 s entre páginas y reintenta a los 20 s. |
| Metrocuadrado | API del buscador `metrocuadrado.com/rest-search/search` con la llave pública que la propia web incluye en su HTML (`x-api-key`), búsqueda por punto y radio (`byPoint`, `latitude`, `longitude`, `distance` en km), 50 por página | precio, **área privada (`areaprivada`) y construida (`marea`)**, garajes, estrato, coordenadas (`ubicacionaproximada` = S/N), descripción | **No trae piso ni dirección** en el listado: el analista abre el anuncio. Los filtros de precio de la API no se documentan; el script filtra del lado propio. |
| Ciencuadras | HTML de búsqueda por barrio, JSON-LD `ItemList` | precio, un área (`floorSize`, no dice cuál), baños, coordenadas, dirección en el título | Solo la primera página por barrio (la paginación la arma el navegador; `?page=2` repite la primera). Compensar con muchos slugs: variantes del barrio (`ciudad-hayuelos`, `modelia-occidental`…) y `fontibon/<barrio>/apartamento`. |
| Properati, Habi, Mercado Libre, Mitula | — | — | Bloquean consultas automáticas (401/403/anti-bots al 2026-10-13) y WebSearch casi no los indexa: revisarlos a mano en el navegador. Habi tiene inventario propio que no está en otros portales. |
| Puntopropiedad (grupo Lifull: Mitula, Nuroa, Trovit) | — | — | Responde a WebFetch; comparte casi todo su inventario con los demás portales. |
| La Haus, Inmuebles24, inmobiliarias locales (Wasi…) | — | — | La Haus solo tiene proyectos nuevos; Inmuebles24 no respondió. Explorador (WebFetch / WebSearch). |

Fuera de alcance: grupos de Facebook/WhatsApp, avisos "se vende" en ventanas y porterías. El comprador los cubre en persona; vale la pena recorrer los conjuntos que el tablero muestre como más baratos por $/m².

## Ubicación: polígono y dirección

1. **Dirección primero.** Las coordenadas de los portales a menudo son el centro del barrio o las pone el anunciante a mano. `harness/scripts/zona.py` normaliza la dirección (`Carrera 87 # 17-59` → vía `KR 87`, placa `17 59`) y la busca en la capa oficial de **placas domiciliarias** de Catastro Bogotá:
   `serviciosgis.catastrobogota.gov.co/arcgis/rest/services/catastro/placadomiciliaria/MapServer/0/query` (campos `PDONVIAL` = vía, `PDOTEXTO` = placa). Formato de Catastro: `KR`, `CL`, `AK` (Av. Carrera), `AC` (Av. Calle), `DG`, `TV`; letras pegadas al número (`19A`) y BIS pegado a la letra (`CL 23ABIS`); las placas del sur terminan en ` S`.
   - Sin placa exacta: toma la placa más cercana en número sobre la misma vía y el mismo cruce.
   - Sin número de placa ("Carrera 86 # 22F"): toma el centro de las placas de esa vía en ese cruce.
   - Sin dirección: usa las coordenadas del portal y lo deja dicho en `fuente_ubicacion`.
   - Dirección completa que **no existe** en Catastro: no usa las coordenadas del portal; queda "sin ubicación" con alerta (pasó con un anuncio de Cali publicado como Bogotá).
   - Si 3 o más anuncios comparten exactamente la misma coordenada, es el centro del barrio que pone el portal (pasa en Fincaraíz con direcciones tipo "Hayuelos, Bogotá, Colombia"): el script la marca como **ubicación aproximada** y el analista debe conseguir la dirección.
2. **Barrio oficial**: el punto se cruza con la capa `catastro/sectorcatastral` (campo `SCANOMBRE`). El barrio que dice el anuncio a veces es el nombre comercial de un sector vecino; manda el catastral.
3. **Zona**: punto en polígono (`dentro`), a menos de `borde_m` del límite (`borde`, cuenta como alrededores) o `fuera`. Si las coordenadas del portal quedan a más de 300 m de la dirección geocodificada, se marca como bandera.
4. Otras capas útiles del mismo servidor (`catastro/…`): `valorreferencia` (mediana del valor comercial del m² de terreno por manzana), `medavalcatphmz` (avalúo catastral medio de PH por manzana), `alturamedia`.

## Cómo leer un anuncio

### Áreas
- **Área privada construida**: la de la escritura y el certificado de tradición; es la que cuenta para el criterio. Excluye muros comunes y ductos. Según el reglamento, el **balcón o terraza** puede estar dentro o fuera; el criterio del comprador lo excluye siempre.
- **Área construida**: incluye muros, columnas y ductos; suele ser 5–12 % mayor que la privada.
- Si el anuncio da una sola cifra, trátala como construida. Si menciona balcón, réstalo (típico 3–6 m²) y deja el área **por confirmar** con el certificado de tradición.
- Áreas redondas e idénticas (80 / 80) en "privada" y "construida" suelen ser copiadas: por confirmar.

### Parqueadero
| Tipo | Qué significa | Para el criterio "parqueadero requerido" |
|---|---|---|
| Privado con matrícula propia | Unidad privada con su folio; se compra con el apto | Cumple (lo ideal) |
| Privado incluido en la matrícula del apto | El garaje está dentro del área privada del apto | Cumple; confirmar en escritura |
| Uso exclusivo (bien común) | Asignado por reglamento/asamblea, no es propiedad | Cumple con reservas: revisar reglamento; afecta valor |
| Comunal / por sorteo / rotación | No hay derecho permanente | **No cumple** |
| Servidumbre o arrendado aparte | Contrato con terceros | No cumple salvo que se pueda comprar |
Los portales solo dicen "1 parqueadero": el tipo casi nunca aparece. Es pregunta obligatoria del primer contacto.

### Piso
- El dato del portal es lo que escribe el anunciante (a veces el número de pisos del edificio). Confirmar con fotos (vista) y en la visita.
- En la zona hay muchos conjuntos de 5–6 pisos sin ascensor y torres de 12–20 pisos. Piso alto sin ascensor = bandera.

### Señales del anuncio (ver también `senales-alerta.md`)
Remate, subasta, adjudicado · sucesión, derechos de cuota, proindiviso · leasing (cesión del contrato, no compraventa) · "solo contado", "urge", "ganga" · arrendado / ocupado · precio muy por debajo de la mediana del barrido · mismo inmueble con precios distintos en dos portales · fotos de otro inmueble o de catálogo · administración desproporcionada.

## Presupuesto → precio máximo

```
precio_compra_max = (presupuesto_total − costos_fijos) / (1 + tasa_gastos_cierre)
precio_pedido_max = precio_compra_max / (1 − descuento_esperado)
```

- `tasa_gastos_cierre` sale de `costos-transaccion-bogota.md` y depende de la financiación (de contado ≈ 2,5–2,7 %; con crédito del 70 % ≈ 4,2–4,5 % con las tarifas de 2026). Si no se conoce la financiación, usar la más costosa razonable y marcarla como SUPUESTO.
- `descuento_esperado`: 3–8 % es lo usual en vivienda usada de Bogotá. El historial de precio del registro (bajas) y el tiempo publicado indican cuánto margen hay.
- El precio de compra máximo es un **tope de presupuesto**, no el valor del inmueble: el valor lo da el perito valuador en `/analizar-inmueble`. Un apartamento puede estar en presupuesto y aun así sobrevalorado.

## Esquema de un registro (crudo y candidatos)

```json
{"id": "fr-123", "portal": "fincaraiz", "url": "…", "titulo": "…", "precio": 520000000,
 "administracion": 420000, "area_privada": 74.0, "area_construida": 80.0, "area_fuente": "…",
 "habitaciones": 3, "banos": 2, "garajes": 1, "piso": 11, "piso_fuente": "ficha técnica|descripción",
 "estrato": 4, "antiguedad": "…", "estado": "Usado", "barrio_portal": "…", "direccion": "…",
 "lat": 4.66, "lon": -74.13, "coord_aproximada": false, "oferente": "inmobiliaria|particular",
 "publicado": "2026-10-01", "descripcion": "…"}
```

El script añade: `banderas`, `fuente_ubicacion`, `zona`, `distancia_limite_m`, `sector_catastral`, `desfase_portal_m`, `puntaje`, `m2_mediana_zona`, `duplicados`.

En `registro.json`, por ID: `estado`, `nota`, `puntaje_analista`, `revisado`, `verificado` (los edita el analista o el comprador) y `datos`, `historial_precio`, `primera_vez`, `ultima_vez`, `activo` (los escribe el script).

## Puntaje preliminar (0–100)
| Componente | Peso | Regla |
|---|---|---|
| Precio | 30 | 30 si el precio pedido ≤ precio de compra máximo; lineal hasta 0 en el precio pedido máximo |
| $/m² vs. mediana de la zona | 25 | 25 si está ≥ 15 % por debajo; 0 si está ≥ 15 % por encima |
| Piso | 15 | 15 si ≥ piso deseable; 6 si se desconoce; 3 si ≥ 5; 0 si menor |
| Zona | 15 | 15 dentro, 7 borde |
| Área | 10 | +1 por cada 2 m² sobre el mínimo, máx. 10 |
| Parqueadero | 5 | 5 si la ficha lo confirma |
| Banderas de alerta | −4 c/u | |
Es una heurística para ordenar la revisión, no una valoración.
