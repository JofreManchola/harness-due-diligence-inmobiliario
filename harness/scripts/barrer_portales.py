#!/usr/bin/env python3
"""Barrido de portales inmobiliarios -> candidatos normalizados, filtrados y priorizados.

Lee los criterios (`casos/prospectos/criterios.json`) y la zona (`zona.geojson`), consulta
los portales con datos estructurados (Fincaraíz, Metrocuadrado, Ciencuadras), normaliza cada
anuncio, ubica la dirección con Catastro (zona.py), filtra, agrupa duplicados entre portales,
calcula un puntaje preliminar y actualiza el registro histórico y el tablero.

Uso:
  barrer_portales.py casos/prospectos              # barrido completo
  barrer_portales.py casos/prospectos --tablero    # solo re-genera PROSPECTOS.md desde registro.json
  barrer_portales.py casos/prospectos --fuentes fincaraiz,metrocuadrado --max-paginas 3
  barrer_portales.py casos/prospectos --sin-descarga   # re-filtra el crudo de hoy (tras cambiar criterios)
  barrer_portales.py casos/prospectos --fusionar barridos/<fecha>/revision-A.json [...]
      # incorpora al registro las revisiones de analistas que trabajaron en paralelo

Salidas (dentro de la carpeta de prospectos):
  barridos/<fecha>/crudo-<portal>.jsonl   todos los anuncios normalizados del portal
                                          (crudo-manual.jsonl lo escribe el agente explorador-mercado)
  barridos/<fecha>/candidatos.jsonl       los que pasan los filtros duros, con zona y puntaje
  barridos/<fecha>/resumen.md             conteos, motivos de descarte y $/m² de referencia
  registro.json                           historial por prospecto (precio, fechas, estado manual)
  PROSPECTOS.md                           tablero (se re-genera; las notas manuales van en registro.json)

Solo librería estándar. Ejecutar con `python3 -I`. Los portales cambian su HTML: si un portal
devuelve 0 anuncios, el resumen lo advierte y el agente explorador debe cubrirlo a mano.
"""
import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zona  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
HOY = dt.date.today().isoformat()
# Llave pública que la web de Metrocuadrado publica en su propio HTML para su buscador.
M2_KEY = "P1MfFHfQMOtL16Zpg36NcntJYCLFm8FqFfudnavl"


def get(url, headers=None, pausa=0.8):
    time.sleep(pausa)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-CO", **(headers or {})})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def num(x):
    try:
        if x in (None, ""):
            return None
        return float(str(x).replace(",", ".").split()[0])
    except ValueError:
        return None


RE_PISO = [re.compile(p, re.I) for p in (
    r"\bpiso\s*(?:n[°ºo.]\s*)?(\d{1,2})\b(?!\s*(?:pisos|de\s+\d))",
    r"\b(\d{1,2})\s*(?:°|º|o\.?|er|do|to|vo|no|mo)?\s*piso\b",
)]
RE_SIN_PARQ = re.compile(r"\bsin\s+(parqueadero|garaje)|no\s+(tiene|incluye)\s+(parqueadero|garaje)|parqueadero\s+comunal", re.I)
RE_PARQ = re.compile(r"\b(\d)?\s*(parqueaderos?|garajes?)\b", re.I)
RE_BALCON = re.compile(r"\bbalc[oó]n|terraza", re.I)
RE_ALERTAS = {
    "remate/subasta": r"\bremate|subasta|adjudicad",
    "sucesión/proindiviso": r"\bsucesi[oó]n|proindiviso|derechos\s+(de\s+)?cuota|herederos",
    "leasing (cesión)": r"\bleasing",
    "solo contado/urgente": r"\bsolo\s+(de\s+)?contado|urge\b|urgente|ganga|precio\s+de\s+oportunidad",
    "parqueadero de uso exclusivo/comunal": r"uso\s+exclusivo|parqueadero\s+comunal|parqueaderos?\s+comunales",
    "arrendado/ocupado": r"\barrendad[oa]\b|con\s+inquilino|ocupad[oa]",
    "remodelación necesaria": r"para\s+remodelar|necesita\s+arreglos|para\s+actualizar",
}


def piso_de(texto):
    for r in RE_PISO:
        m = r.search(texto or "")
        if m and 0 < int(m.group(1)) <= 40:
            return int(m.group(1))
    return None


def registro_base(**kw):
    base = dict(id=None, portal=None, url=None, titulo=None, precio=None, administracion=None,
                area_privada=None, area_construida=None, area_fuente=None, habitaciones=None,
                banos=None, garajes=None, piso=None, piso_fuente=None, estrato=None,
                antiguedad=None, estado=None, barrio_portal=None, direccion=None,
                lat=None, lon=None, coord_aproximada=None, oferente=None, publicado=None,
                descripcion=None)
    base.update(kw)
    return base

# ---------------------------------------------------------------- portales

def fincaraiz(cfg, max_paginas):
    out = []
    pmin, pmax = cfg.get("precio_desde"), cfg.get("precio_hasta")
    for slug in cfg.get("slugs", []):
        for pag in range(1, max_paginas + 1):
            ruta = f"https://www.fincaraiz.com.co/venta/apartamentos/{slug}"
            if pmin and pmax:
                ruta += f"/desde-{int(pmin)}/hasta-{int(pmax)}"
            if pag > 1:
                ruta += f"/pagina{pag}"
            # Fincaraíz limita la frecuencia: tras unas páginas responde vacío. Pausa de 4 s y reintento a los 20 s.
            m = None
            for espera in (4, 20):
                try:
                    h = get(ruta, pausa=espera)
                except Exception as e:
                    print(f"  fincaraiz {slug} p{pag}: {e}", file=sys.stderr)
                    continue
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
                if m:
                    break
            if not m:
                print(f"  fincaraiz {slug} p{pag}: sin datos (¿límite de frecuencia?)", file=sys.stderr)
                break
            sf = json.loads(m.group(1))["props"]["pageProps"].get("fetchResult", {}).get("searchFast", {})
            for x in sf.get("data", []):
                ts = {t["field"]: t.get("value") for t in x.get("technicalSheet", [])}
                desc = x.get("description") or ""
                out.append(registro_base(
                    id=f"fr-{x['id']}", portal="fincaraiz",
                    url="https://www.fincaraiz.com.co" + x.get("link", ""),
                    titulo=x.get("title"), precio=(x.get("price") or {}).get("amount"),
                    administracion=(x.get("commonExpenses") or {}).get("amount"),
                    area_privada=num(x.get("m2apto")) or None, area_construida=num(x.get("m2Built")) or None,
                    area_fuente="ficha técnica Fincaraíz (Área Privada / Construida)",
                    habitaciones=x.get("bedrooms"), banos=x.get("bathrooms"), garajes=x.get("garage"),
                    piso=x.get("floor") or None, piso_fuente="ficha técnica" if x.get("floor") else None,
                    estrato=x.get("stratum"), antiguedad=ts.get("constructionYear") or None,
                    estado=ts.get("construction_state_name"),
                    barrio_portal=((x.get("locations") or {}).get("location_main") or {}).get("name"),
                    direccion=x.get("address"), lat=x.get("latitude"), lon=x.get("longitude"),
                    oferente="inmobiliaria" if (x.get("owner") or {}).get("inmoPropsLink") else "particular o sin dato",
                    publicado=x.get("created_at"),
                    descripcion=desc))
            pi = sf.get("paginatorInfo") or {}
            if not pi.get("hasMorePages"):
                break
    return out


def metrocuadrado(cfg, centro, max_paginas):
    out, tam = [], 50
    lat, lon = centro
    for pag in range(max_paginas * 3):  # 50 por página; ~3 páginas de M2 por página de otros portales
        q = urllib.parse.urlencode({
            "realEstateTypeList": "apartamento", "realEstateBusinessList": "venta", "city": "bogotá",
            "byPoint": "true", "latitude": lat, "longitude": lon, "distance": cfg.get("radio_km", 2.5),
            "from": pag * tam, "size": tam})
        try:
            d = json.loads(get("https://www.metrocuadrado.com/rest-search/search?" + q,
                               {"x-api-key": M2_KEY, "Referer": "https://www.metrocuadrado.com/"}))
        except Exception as e:
            print(f"  metrocuadrado p{pag}: {e}", file=sys.stderr)
            break
        res = d.get("results") or []
        for x in res:
            loc = x.get("localizacion") or {}
            desc = x.get("comment") or ""
            p = piso_de(desc)
            out.append(registro_base(
                id=f"m2-{x['midinmueble']}", portal="metrocuadrado",
                url="https://www.metrocuadrado.com" + (x.get("link") or ""),
                titulo=x.get("title"), precio=x.get("mvalorventa"),
                area_privada=num(x.get("areaprivada")), area_construida=num(x.get("marea")),
                area_fuente="API Metrocuadrado (areaprivada / marea)",
                habitaciones=num(x.get("mnrocuartos")), banos=num(x.get("mnrobanos")),
                garajes=num(x.get("mnrogarajes")), piso=p, piso_fuente="descripción" if p else None,
                estrato=x.get("estrato"), estado=x.get("mestadoinmueble"),
                barrio_portal=x.get("mnombrecomunbarrio") or x.get("mbarrio"),
                lat=loc.get("lat"), lon=loc.get("lon"), coord_aproximada=x.get("ubicacionaproximada") == "S",
                oferente=x.get("OwnerType") or x.get("moferente"), descripcion=desc,
                proyecto=x.get("mnombreproyecto")))
        if len(res) < tam or (pag + 1) * tam >= (d.get("totalHits") or 0):
            break
    return out


def ciencuadras(cfg, max_paginas):
    out = []
    for slug in cfg.get("slugs", []):
        try:
            h = get(f"https://www.ciencuadras.com/venta/bogota/apartamento/{slug}")
        except Exception as e:
            print(f"  ciencuadras {slug}: {e}", file=sys.stderr)
            continue
        for s in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S):
            try:
                d = json.loads(s)
            except ValueError:
                continue
            if d.get("@type") != "ItemList":
                continue
            for it in d.get("itemListElement", []):
                prod = it.get("item", {})
                of = prod.get("offers", {})
                ap = of.get("itemOffered", {})
                geo = ap.get("geo", {})
                nombre = prod.get("name", "")
                dirm = re.search(r" en (.+?), ([^,]+), Bogot", nombre)
                out.append(registro_base(
                    id="cc-" + it["url"].rsplit("-", 1)[-1], portal="ciencuadras", url=it["url"],
                    titulo=nombre, precio=num(of.get("price")),
                    area_construida=num((ap.get("floorSize") or {}).get("value")),
                    area_fuente="Ciencuadras floorSize (no distingue privada/construida)",
                    banos=num(ap.get("numberOfBathroomsTotal")),
                    direccion=dirm.group(1) if dirm else None, barrio_portal=dirm.group(2) if dirm else slug,
                    lat=geo.get("latitude"), lon=geo.get("longitude")))
    return out

# ---------------------------------------------------------------- filtros y puntaje

def direccion_de(r):
    """La dirección más precisa disponible: campo dirección, título o descripción."""
    for t in (r.get("direccion"), r.get("titulo"), r.get("descripcion")):
        if t and zona.normalizar_direccion(t):
            return t
    return None


def evaluar(r, c):
    """Aplica filtros duros. Devuelve (pasa, motivo_descarte, banderas)."""
    banderas = []
    desc = (r.get("descripcion") or "") + " " + (r.get("titulo") or "")
    precio = r.get("precio") or 0
    if not precio or precio < c.get("precio_pedido_min", 0):
        return False, "precio ausente o fuera de rango", banderas
    if precio > c["precio_pedido_max"]:
        return False, "precio pedido > máximo negociable", banderas
    if (r.get("estado") or "").lower().startswith("nuevo") and not c.get("incluir_nuevos", True):
        return False, "proyecto nuevo excluido", banderas
    ap, ac = r.get("area_privada"), r.get("area_construida")
    amin = c["area_privada_min"]
    if ap:
        if ap < amin:
            return False, f"área privada < mínimo: {ap:g}", banderas
        if ac and ap == ac and RE_BALCON.search(desc):
            banderas.append("área privada = construida y menciona balcón/terraza: confirmar área sin balcón")
    elif ac:
        if ac < amin:
            return False, f"área construida < mínimo: {ac:g}", banderas
        banderas.append("solo área construida: confirmar área privada sin balcón")
    else:
        return False, "sin área", banderas
    if c.get("parqueadero_requerido"):
        g = r.get("garajes")
        if RE_SIN_PARQ.search(desc):
            return False, "sin parqueadero / parqueadero comunal", banderas
        if not g:
            m = RE_PARQ.search(desc)
            if m:
                banderas.append("parqueadero mencionado en la descripción, no en la ficha: confirmar")
            else:
                banderas.append("parqueadero no informado: confirmar")
    for nombre, patron in RE_ALERTAS.items():
        if re.search(patron, desc, re.I):
            banderas.append(f"alerta: {nombre}")
    return True, None, banderas


def puntaje(r, c, mediana_m2):
    """0–100 preliminar. Lo ajusta el analista de prospectos tras abrir el anuncio."""
    p = 0
    precio = r["precio"]
    if precio <= c["precio_compra_max"]:
        p += 30
    else:  # entre compra máxima y pedido máximo: requiere negociar
        p += 30 * (c["precio_pedido_max"] - precio) / max(1, c["precio_pedido_max"] - c["precio_compra_max"])
    area = r.get("area_privada") or (r.get("area_construida") or 0) * 0.92
    if mediana_m2 and area:
        rel = (precio / area) / mediana_m2  # <1 = más barato que la mediana
        p += max(0, min(25, 25 * (1.15 - rel) / 0.3))
    piso = r.get("piso")
    pmin = c.get("piso_deseable_min", 10)
    p += 15 if piso and piso >= pmin else (6 if piso is None else (3 if piso >= 5 else 0))
    p += {"dentro": 15, "borde": 7}.get(r.get("zona"), 0)
    p += min(10, max(0, (area - c["area_privada_min"]) / 2)) if area else 0
    p += 5 if r.get("garajes") else 0
    p -= 4 * len([b for b in r.get("banderas", []) if b.startswith("alerta")])
    return round(max(0, min(100, p)))


def agrupar_duplicados(cands):
    """Mismo inmueble en varios portales: misma placa con área ±3 m² y precio ±6 %, o a <80 m con área ±2 m²
    y precio ±3 %; en ambos casos, mismo piso si los dos lo dicen."""
    grupos = []
    for r in sorted(cands, key=lambda x: x["id"]):
        area = r.get("area_privada") or r.get("area_construida") or 0
        dr = zona.normalizar_direccion(direccion_de(r) or "")
        for g in grupos:
            a = g[0]
            aa = a.get("area_privada") or a.get("area_construida") or 0
            da = zona.normalizar_direccion(direccion_de(a) or "")
            # Un conjunto entero comparte placa: la misma dirección solo agrupa si área y precio también coinciden.
            misma_dir = dr and da and dr == da and len(dr[1].split()) == 2  # placa completa, no solo el cruce
            if (misma_dir and abs(aa - area) <= 3 and abs(a["precio"] - r["precio"]) / a["precio"] <= 0.06
                    and (a.get("piso") is None or r.get("piso") is None or a.get("piso") == r.get("piso"))) or (a.get("lat") and r.get("lat") and zona.distancia_m(a["lat"], a["lon"], r["lat"], r["lon"]) < 80
                    and abs(aa - area) <= 2 and abs(a["precio"] - r["precio"]) / a["precio"] <= 0.03
                    and (a.get("piso") in (None, r.get("piso")) or r.get("piso") is None)):
                g.append(r)
                break
        else:
            grupos.append([r])
    res = []
    for g in grupos:
        # se queda el más completo (con dirección geocodificada y piso)
        g.sort(key=lambda x: ((x.get("fuente_ubicacion") or "").startswith("Catastro"), x.get("piso") is not None,
                              x.get("area_privada") is not None), reverse=True)
        p = dict(g[0])
        p["duplicados"] = [{"id": o["id"], "url": o["url"], "precio": o["precio"]} for o in g[1:]]
        res.append(p)
    return res

# ---------------------------------------------------------------- registro y tablero

def actualizar_registro(ruta, cands):
    reg = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else {}
    vistos, dups = set(), {}
    for r in cands:
        for d in r.get("duplicados", []):
            dups[d["id"]] = r["id"]
        e = reg.get(r["id"])
        if e is None:
            e = reg[r["id"]] = {"estado": "nuevo", "primera_vez": HOY, "historial_precio": []}
        hp = e.setdefault("historial_precio", [])
        if not hp or hp[-1]["precio"] != r["precio"]:
            hp.append({"fecha": HOY, "precio": r["precio"]})
        e["ultima_vez"] = HOY
        e["activo"] = True
        e["datos"] = {k: v for k, v in r.items() if k != "descripcion"}
        vistos.add(r["id"])
    for k, e in reg.items():
        if k in dups:  # el mismo inmueble en otro anuncio: se muestra en la fila del principal
            e["duplicado_de"] = dups[k]
            e["activo"] = True
            e["ultima_vez"] = HOY
        else:
            e.pop("duplicado_de", None)
            if k not in vistos:
                e["activo"] = False  # no apareció en este barrido (vendido, pausado o fuera de filtros)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    return reg


def M(x):
    return f"${x / 1e6:,.0f} M".replace(",", ".") if x else "—"


ORDEN_ESTADO = ["promovido", "visitar", "preseleccionado", "contactar", "nuevo", "en espera", "descartado"]


def generar_tablero(carpeta, reg, c):
    filas = []
    # Si el anuncio principal no está revisado pero un duplicado suyo sí, la fila hereda esa revisión.
    revisado_en = {}
    for k, e in reg.items():
        if e.get("duplicado_de") and e.get("estado", "nuevo") != "nuevo":
            revisado_en.setdefault(e["duplicado_de"], (k, e))
    for pid, e in reg.items():
        if e.get("estado", "nuevo") == "nuevo" and pid in revisado_en:
            k, r = revisado_en[pid]
            e = {**e, **{x: r[x] for x in ("estado", "nota", "puntaje_analista") if x in r}}
            e["nota"] = f"{e.get('nota') or ''} (revisado como {k})".strip()
        d = e.get("datos", {})
        if not d or e.get("duplicado_de"):
            continue
        area = d.get("area_privada") or d.get("area_construida")
        hp = e.get("historial_precio", [])
        cambio = ""
        if len(hp) > 1 and hp[-1]["precio"] != hp[0]["precio"]:
            cambio = f" ({'↓' if hp[-1]['precio'] < hp[0]['precio'] else '↑'} desde {M(hp[0]['precio'])})"
        fichas = [x for x in [pid] + [d2["id"] for d2 in d.get("duplicados", [])]
                  if os.path.exists(os.path.join(carpeta, "fichas", f"{x}.md"))]
        ficha = f"[ficha](fichas/{fichas[0]}.md)" if fichas else ""
        filas.append((ORDEN_ESTADO.index(e.get("estado", "nuevo")) if e.get("estado") in ORDEN_ESTADO else 4,
                      -(e.get("puntaje_analista") or d.get("puntaje") or 0), pid, e, d, area, cambio, ficha))
    filas.sort(key=lambda f: (not f[3].get("activo", True), f[0], f[1]))
    L = [
        "# Prospectos", "",
        "> Generado por `harness/scripts/barrer_portales.py` desde `registro.json`. **No editar la tabla a mano**:",
        "> el estado, la nota y el puntaje del analista se cambian en `registro.json` (campos `estado`, `nota`,",
        "> `puntaje_analista`) y se re-genera con `--tablero`. Criterios: [criterios.json](criterios.json) · zona: [zona.geojson](zona.geojson).",
        "",
        f"Presupuesto total {M(c.get('presupuesto_total'))} → precio de compra máximo **{M(c['precio_compra_max'])}** "
        f"(precio pedido hasta {M(c['precio_pedido_max'])} si la negociación lo permite) · área privada ≥ {c['area_privada_min']} m² "
        f"sin balcón · parqueadero {'requerido' if c.get('parqueadero_requerido') else 'opcional'} · piso deseable ≥ {c.get('piso_deseable_min')}.",
        "",
        "Estados: `nuevo` → `contactar` (falta un dato excluyente) → `preseleccionado` (cumple lo confirmado) → `visitar` → `promovido` (caso en `casos/`) · `en espera` · `descartado` (con motivo).",
        "",
        "| # | Prospecto | Estado | Puntaje | Precio pedido | Área priv. | $/m² | Piso | Garaje | Adm. | Zona | Barrio (Catastro) | Banderas | Visto | Ficha |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    n = 0
    for _, _, pid, e, d, area, cambio, ficha in filas:
        n += 1
        activo = "" if e.get("activo", True) else " _(no visto en el último barrido)_"
        pts = e.get("puntaje_analista")
        pts = f"**{pts}**" if pts is not None else f"{d.get('puntaje', '—')} (pre)"
        ban = "; ".join(d.get("banderas", [])[:3]) or "—"
        if d.get("duplicados"):
            ban = f"también en {', '.join(x['id'] for x in d['duplicados'])}; " + ban
        L.append(
            f"| {n} | [{pid}]({d.get('url')}) {d.get('titulo', '')[:45]}{activo} | {e.get('estado')}"
            f"{(' — ' + e['nota']) if e.get('nota') else ''} | {pts} | {M(d.get('precio'))}{cambio} | "
            f"{(f'{area:g}' if area else '—')}{'' if d.get('area_privada') else ' (constr.)'} | "
            f"{(format(d['precio'] / area / 1e6, '.2f') + ' M') if area else '—'} | {d.get('piso') or '¿?'} | {d.get('garajes') or '¿?'} | "
            f"{M(d.get('administracion')) if d.get('administracion') else '—'} | {d.get('zona', '—')} | "
            f"{d.get('sector_catastral') or d.get('barrio_portal') or '—'} | {ban} | {e.get('primera_vez')}→{e.get('ultima_vez')} | {ficha} |")
    with open(os.path.join(carpeta, "PROSPECTOS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return n

# ---------------------------------------------------------------- main

def centroide(anillos):
    pts = [p for a in anillos for p in a[:-1]]
    return (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta", help="carpeta de prospectos (casos/prospectos)")
    ap.add_argument("--tablero", action="store_true", help="solo re-generar PROSPECTOS.md")
    ap.add_argument("--fuentes", default="fincaraiz,metrocuadrado,ciencuadras,manual",
                    help="'manual' = barridos/<hoy>/crudo-manual.jsonl, escrito por el agente explorador-mercado")
    ap.add_argument("--max-paginas", type=int, default=15)
    ap.add_argument("--fusionar", nargs="+", metavar="REVISION.json",
                    help="fusiona {id: {estado, nota, puntaje_analista, revisado, verificado}} en registro.json")
    ap.add_argument("--sin-descarga", action="store_true", help="usar barridos/<hoy>/crudo-*.jsonl en vez de consultar los portales")
    a = ap.parse_args()
    carpeta = a.carpeta.rstrip("/")
    c = json.load(open(os.path.join(carpeta, "criterios.json"), encoding="utf-8"))
    reg_ruta = os.path.join(carpeta, "registro.json")
    if a.fusionar:
        reg = json.load(open(reg_ruta, encoding="utf-8"))
        campos = ("estado", "nota", "puntaje_analista", "revisado", "verificado")
        for ruta in a.fusionar:
            ruta = ruta if os.path.isabs(ruta) or os.path.exists(ruta) else os.path.join(carpeta, ruta)
            rev = json.load(open(ruta, encoding="utf-8"))
            desconocidos = [k for k in rev if k not in reg]
            for pid, cambios in rev.items():
                if pid in reg:
                    reg[pid].update({k: v for k, v in cambios.items() if k in campos})
            print(f"{ruta}: {len(rev) - len(desconocidos)} fusionados" +
                  (f"; IDs fuera del registro: {', '.join(desconocidos)}" if desconocidos else ""))
        with open(reg_ruta, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=1)
        a.tablero = True
    if a.tablero:
        reg = json.load(open(reg_ruta, encoding="utf-8"))
        print(f"PROSPECTOS.md: {generar_tablero(carpeta, reg, c)} filas")
        return
    anillos = zona.cargar_zona(os.path.join(carpeta, c.get("zona", "zona.geojson")))
    borde = c.get("borde_m", 150)
    salida = os.path.join(carpeta, "barridos", HOY)
    os.makedirs(salida, exist_ok=True)
    fu = c.get("fuentes", {})
    todos = []
    for portal in a.fuentes.split(","):
        print(f"→ {portal}", file=sys.stderr)
        crudo = os.path.join(salida, f"crudo-{portal}.jsonl")
        if a.sin_descarga or portal == "manual":
            if os.path.exists(crudo):
                todos += [json.loads(x) for x in open(crudo, encoding="utf-8")]
            continue
        if portal == "fincaraiz":
            rs = fincaraiz(fu.get("fincaraiz", {}), a.max_paginas)
        elif portal == "metrocuadrado":
            rs = metrocuadrado(fu.get("metrocuadrado", {}), centroide(anillos), a.max_paginas)
        elif portal == "ciencuadras":
            rs = ciencuadras(fu.get("ciencuadras", {}), a.max_paginas)
        else:
            continue
        uniq = {r["id"]: r for r in rs}
        with open(crudo, "w", encoding="utf-8") as f:
            for r in uniq.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  {len(uniq)} anuncios", file=sys.stderr)
        todos += uniq.values()

    # Filtro grueso por coordenadas del portal antes de geocodificar (ahorra consultas a Catastro):
    # se descarta lo que esté a más de 1,5 km del límite incluso con coordenadas aproximadas.
    descartes, pasan = {}, []
    for r in todos:
        if r.get("lat") and r.get("lon"):
            z, dist = zona.clasificar(float(r["lon"]), float(r["lat"]), anillos, borde)
            if z == "fuera" and dist > 1500:
                descartes["fuera de zona (>1,5 km)"] = descartes.get("fuera de zona (>1,5 km)", 0) + 1
                continue
        ok, motivo, ban = evaluar(r, c)
        if not ok:
            clave = motivo.split(":")[0]
            descartes[clave] = descartes.get(clave, 0) + 1
            continue
        r["banderas"] = ban
        pasan.append(r)

    # Coordenadas compartidas por 3+ anuncios = centro del barrio puesto por el portal, no el edificio.
    repetidas = {}
    for r in todos:
        if r.get("lat") and r.get("lon"):
            k = (round(float(r["lat"]), 5), round(float(r["lon"]), 5))
            repetidas[k] = repetidas.get(k, 0) + 1
    for r in pasan:
        if r.get("lat") and repetidas.get((round(float(r["lat"]), 5), round(float(r["lon"]), 5)), 0) >= 3:
            r["coord_aproximada"] = True

    print(f"→ ubicando {len(pasan)} candidatos con Catastro", file=sys.stderr)
    cands = []
    for r in pasan:
        u = zona.ubicar(anillos, direccion_de(r), num(r.get("lat")), num(r.get("lon")),
                        aproximada=bool(r.get("coord_aproximada")), borde_m=borde)
        r.update(u)
        if r.get("desfase_portal_m", 0) > 300:
            r["banderas"].append(f"coordenadas del portal a {r['desfase_portal_m']} m de la dirección")
        if r["zona"] == "fuera":
            descartes["fuera de zona"] = descartes.get("fuera de zona", 0) + 1
            continue
        if r.get("direccion_no_encontrada"):
            r["banderas"].append("alerta: la dirección no existe en Catastro Bogotá (¿otra ciudad o dirección errada?)")
        elif r["zona"] == "sin ubicación":
            r["banderas"].append("sin ubicación: confirmar dirección")
        elif r.get("coord_aproximada") and not r["fuente_ubicacion"].startswith("Catastro"):
            r["banderas"].append("ubicación aproximada (centro del barrio): confirmar dirección")
        piso = r.get("piso")
        if piso is None:
            r["piso"] = piso_de(r.get("descripcion"))
            r["piso_fuente"] = "descripción" if r["piso"] else None
        cands.append(r)

    cands = agrupar_duplicados(cands)
    # $/m² de referencia: mediana de los candidatos usados dentro de la zona (área privada o construida×0,92)
    m2 = [r["precio"] / (r.get("area_privada") or r["area_construida"] * 0.92)
          for r in cands if r["zona"] == "dentro" and not (r.get("estado") or "").lower().startswith("nuevo")]
    mediana = statistics.median(m2) if m2 else None
    for r in cands:
        r["puntaje"] = puntaje(r, c, mediana)
        r["m2_mediana_zona"] = round(mediana) if mediana else None
    cands.sort(key=lambda r: -r["puntaje"])
    with open(os.path.join(salida, "candidatos.jsonl"), "w", encoding="utf-8") as f:
        for r in cands:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    reg = actualizar_registro(reg_ruta, cands)
    n = generar_tablero(carpeta, reg, c)

    print(f"  mediana zona: {mediana and round(mediana)} $/m²", file=sys.stderr)
    por_portal = {}
    for r in todos:
        por_portal[r["portal"]] = por_portal.get(r["portal"], 0) + 1
    R = [f"# Barrido {HOY}", "",
         "| Portal | Anuncios leídos |", "|---|---|"] + [f"| {p} | {k} |" for p, k in por_portal.items()]
    vacios = [p for p in a.fuentes.split(",") if p not in por_portal and p != "manual"]
    if vacios:
        R += ["", f"**Advertencia:** sin anuncios de {', '.join(vacios)} (¿cambió el portal o bloqueó?). Cubrirlo con el agente explorador."]
    R += ["", f"Candidatos que pasan filtros duros (tras agrupar duplicados): **{len(cands)}** "
          f"({sum(r['zona'] == 'dentro' for r in cands)} dentro, {sum(r['zona'] == 'borde' for r in cands)} borde).",
          "", f"Mediana $/m² de candidatos usados dentro de la zona: **${mediana / 1e6:.2f} M/m²** (n={len(m2)}; precios pedidos, sin descuento de negociación)." if mediana else "",
          "", "| Motivo de descarte | Anuncios |", "|---|---|"] + \
        [f"| {k} | {v} |" for k, v in sorted(descartes.items(), key=lambda x: -x[1])]
    with open(os.path.join(salida, "resumen.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(R) + "\n")
    print(f"✓ {len(todos)} leídos → {len(cands)} candidatos. Tablero: {n} filas. Resumen: {salida}/resumen.md")


if __name__ == "__main__":
    sys.exit(main())
