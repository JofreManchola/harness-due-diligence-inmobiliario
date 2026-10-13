#!/usr/bin/env python3
"""Ubica un inmueble respecto a la zona de interés (polígono GeoJSON) por coordenadas o por dirección.

La dirección se geocodifica con la capa oficial de placas domiciliarias de Catastro Bogotá
(un punto por placa) y el punto se cruza con el sector catastral (barrio oficial).
Las coordenadas de los portales suelen ser aproximadas (centro del barrio), así que la
dirección, cuando existe, manda.

Uso:
  zona.py <zona.geojson> --punto 4.6619 -74.1353
  zona.py <zona.geojson> --direccion "Carrera 87 # 17-59"
Solo librería estándar. Ejecutar con `python3 -I`.
"""
import argparse
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request

CATASTRO = "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/catastro"
UA = "harness-due-diligence/1.0 (consulta personal)"

# ---------------------------------------------------------------- geometría

def cargar_zona(ruta):
    with open(ruta, encoding="utf-8") as f:
        g = json.load(f)
    feats = g["features"] if g.get("type") == "FeatureCollection" else [g]
    anillos = []
    for ft in feats:
        geom = ft.get("geometry", ft)
        if geom["type"] == "Polygon":
            anillos.append(geom["coordinates"][0])
        elif geom["type"] == "MultiPolygon":
            anillos += [p[0] for p in geom["coordinates"]]
    return anillos


def _dentro(lon, lat, anillo):
    c = False
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _dist_segmento_m(lon, lat, a, b):
    k = math.cos(math.radians(lat))
    px, py = lon * 111320 * k, lat * 110574
    ax, ay, bx, by = a[0] * 111320 * k, a[1] * 110574, b[0] * 111320 * k, b[1] * 110574
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def clasificar(lon, lat, anillos, borde_m=150):
    """('dentro'|'borde'|'fuera', distancia en m al límite; 0 si está dentro)."""
    if any(_dentro(lon, lat, a) for a in anillos):
        return "dentro", 0
    d = min(_dist_segmento_m(lon, lat, p, q) for a in anillos for p, q in zip(a, a[1:]))
    return ("borde" if d <= borde_m else "fuera"), round(d)


def distancia_m(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lon1 - lon2) * 111320 * k, (lat1 - lat2) * 110574)

# ---------------------------------------------------------------- direcciones

VIAS = [
    (r"av(enida)?\.?\s*(carrera|cra|kr|kra|cr)\b", "AK"),
    (r"av(enida)?\.?\s*(calle|cl|cll)\b", "AC"),
    (r"\b(ak)\b", "AK"), (r"\b(ac)\b", "AC"),
    (r"\b(carrera|cra|kra|kr|cr|crr)\b\.?", "KR"),
    (r"\b(calle|cll|cl)\b\.?", "CL"),
    (r"\b(transversal|tv|tr|trans)\b\.?", "TV"),
    (r"\b(diagonal|dg|diag)\b\.?", "DG"),
]
_DIR = re.compile(
    r"(?P<via>AK|AC|KR|CL|TV|DG)\s*(?P<n1>\d{1,3})(?:\s*(?P<l1>[A-H])(?![A-Z]))?(?:\s*(?P<b1>BIS))?"
    r"(?:\s*(?P<l1b>[A-H])(?![A-Z]))?"
    r"(?:\s*(?:#|N[O°º]\.?|NUMERO|NRO\.?)\s*|\s+)(?P<n2>\d{1,3})(?:\s*(?P<l2>[A-H])(?![A-Z]))?(?:\s*(?P<b2>BIS))?"
    r"(?:\s*[-–—\s]\s*(?P<n3>\d{1,3})\b)?"
)


def normalizar_direccion(texto):
    """'Carrera 87 # 17-59' -> ('KR 87', '17 59'); 'Carrera 86 # 22F' -> ('KR 86', '22F') (solo cruce).

    Usa el formato de Catastro: BIS pegado a la letra ('CL 23ABIS', 'KR 72BIS'). None si no se reconoce."""
    t = " " + texto.lower() + " "
    t = t.replace("º", "°").replace("n°", " # ")
    for patron, sigla in VIAS:
        t = re.sub(patron, f" {sigla} ", t)
    t = re.sub(r"\s+", " ", t.upper())
    m = _DIR.search(t)
    if not m:
        return None
    via = f"{m['via']} {m['n1']}{m['l1'] or ''}{'BIS' if m['b1'] else ''}{m['l1b'] or ''}"
    cruce = f"{m['n2']}{m['l2'] or ''}{'BIS' if m['b2'] else ''}"
    return (via, f"{cruce} {int(m['n3']):02d}") if m["n3"] else (via, cruce)


def _consulta(servicio, params):
    url = f"{CATASTRO}/{servicio}/MapServer/0/query?" + urllib.parse.urlencode({**params, "f": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def geocodificar(texto):
    """Geocodifica una dirección de Bogotá con la capa de placas domiciliarias de Catastro.

    Devuelve dict con lat, lon, via, placa y metodo:
      'placa exacta' | 'placa vecina (±N en el número)' | 'cruce de vías (sin número de placa)'
    o None. Sin placa exacta toma la más cercana en número sobre la misma vía y el mismo cruce
    (p. ej. 17-59 -> 17-61); sin número de placa, el centro de las placas de esa vía en ese cruce."""
    n = normalizar_direccion(texto)
    if not n:
        return None
    via, placa = n
    alternas = [via]
    for a, b in (("KR", "AK"), ("AK", "KR"), ("CL", "AC"), ("AC", "CL")):
        if via.startswith(a):
            alternas.append(b + via[2:])
    cruce, _, num = placa.partition(" ")
    sur = " SUR" in f" {texto.upper()} "
    for v in alternas:
        try:
            d = _consulta("placadomiciliaria", {
                "where": f"PDONVIAL='{v}' AND PDOTEXTO LIKE '{cruce} %'",
                "outFields": "PDOTEXTO,PDONVIAL", "outSR": 4326, "resultRecordCount": 200})
        except Exception as e:  # servicio caído: el llamador usa las coordenadas del portal
            return {"error": str(e)}
        # Las placas del sur terminan en " S"; solo valen si la dirección dice "sur".
        feats = [f for f in d.get("features") or [] if f["attributes"]["PDOTEXTO"].endswith(" S") == sur]
        if not feats:
            continue
        if not num:
            xs = sorted(f["geometry"]["x"] for f in feats)
            ys = sorted(f["geometry"]["y"] for f in feats)
            return {"lat": round(ys[len(ys) // 2], 6), "lon": round(xs[len(xs) // 2], 6), "via": v,
                    "placa": cruce, "metodo": f"cruce de vías (sin número de placa; {len(feats)} placas)"}

        def dif(f):
            try:
                return abs(int(f["attributes"]["PDOTEXTO"].split(" ")[1]) - int(num))
            except (ValueError, IndexError):
                return 999
        f = min(feats, key=dif)
        g = f["geometry"]
        delta = dif(f)
        return {"lat": round(g["y"], 6), "lon": round(g["x"], 6), "via": v,
                "placa": f["attributes"]["PDOTEXTO"],
                "metodo": "placa exacta" if delta == 0 else f"placa vecina (±{delta} en el número)"}
    return None


def sector_catastral(lat, lon):
    try:
        d = _consulta("sectorcatastral", {
            "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": "SCACODIGO,SCANOMBRE",
            "returnGeometry": "false"})
        a = d["features"][0]["attributes"]
        return a["SCANOMBRE"]
    except Exception:
        return None


def ubicar(anillos, direccion=None, lat=None, lon=None, aproximada=False, borde_m=150, pausa=0.3):
    """Ubica un inmueble: geocodifica la dirección si hay, si no usa las coordenadas del portal."""
    res = {"fuente_ubicacion": None}
    geo = geocodificar(direccion) if direccion else None
    time.sleep(pausa)
    if geo and "lat" in geo:
        res.update(lat=geo["lat"], lon=geo["lon"], fuente_ubicacion=f"Catastro, {geo['via']} # {geo['placa']} ({geo['metodo']})")
        if lat is not None and lon is not None:
            res["desfase_portal_m"] = round(distancia_m(lat, lon, geo["lat"], geo["lon"]))
    elif geo is None and direccion and len((normalizar_direccion(direccion) or ("", ""))[1].split()) == 2:
        # Dirección completa que no existe en el catastro de Bogotá: anuncio de otra ciudad o dirección errada.
        # No se confía en las coordenadas del portal.
        res.update(zona="sin ubicación", distancia_limite_m=None, direccion_no_encontrada=True,
                   fuente_ubicacion="dirección no encontrada en Catastro Bogotá")
        return res
    elif lat is not None and lon is not None:
        res.update(lat=lat, lon=lon, fuente_ubicacion="coordenadas del portal" + (" (aproximadas)" if aproximada else ""))
    else:
        res.update(zona="sin ubicación", distancia_limite_m=None)
        return res
    res["zona"], res["distancia_limite_m"] = clasificar(res["lon"], res["lat"], anillos, borde_m)
    res["sector_catastral"] = sector_catastral(res["lat"], res["lon"])
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zona")
    ap.add_argument("--punto", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--direccion")
    ap.add_argument("--borde", type=int, default=150, help="metros de tolerancia para el borde (150)")
    a = ap.parse_args()
    if not (a.punto or a.direccion):
        ap.error("indica --punto o --direccion")
    anillos = cargar_zona(a.zona)
    lat, lon = a.punto if a.punto else (None, None)
    print(json.dumps(ubicar(anillos, a.direccion, lat, lon, borde_m=a.borde), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
