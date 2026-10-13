#!/usr/bin/env python3
"""Hooks de Claude Code del harness (ver .claude/settings.json).

PreToolUse (Write|Edit|MultiEdit|NotebookEdit) — bloquea (exit 2):
  1. Escrituras en casos/<inmueble>/documentos/: los originales son de solo lectura (CLAUDE.md, regla 5).
  2. Datos de casos en archivos del harness público (todo lo que no resuelve dentro de casos/):
     matrículas de Bogotá (50C-/50N-/50S-), CHIP catastral y números de cédula (CLAUDE.md, regla 6).
PostToolUse (mismo matcher) — tras editar casos/prospectos/registro.json re-genera PROSPECTOS.md.

Lee el evento JSON por stdin. Ejecutar con `python3 -I`.
"""
import json
import os
import re
import subprocess
import sys

RAIZ = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASOS = os.path.realpath(os.path.join(RAIZ, "casos"))

PATRONES = {
    "matrícula inmobiliaria": re.compile(r"\b50[CNS]-\d{6,}"),
    "CHIP catastral": re.compile(r"\bAAA\d{4}[A-Z0-9]{4}\b"),
    "número de cédula": re.compile(r"\b(?:C\.?\s?C\.?|c[ée]dula(?:\s+de\s+ciudadan[íi]a)?)\s*(?:n[o°º.]*\s*)?:?\s*\d{1,3}(?:[.\s]?\d{3}){2,3}\b", re.I),
}


def texto_nuevo(ti):
    partes = [ti.get("content"), ti.get("new_string"), ti.get("new_source")]
    partes += [e.get("new_string") for e in ti.get("edits") or []]
    return "\n".join(p for p in partes if isinstance(p, str))


def dentro(ruta, base):
    return ruta == base or ruta.startswith(base + os.sep)


def main():
    ev = json.load(sys.stdin)
    ti = ev.get("tool_input") or {}
    ruta = ti.get("file_path") or ti.get("notebook_path")
    if not ruta:
        return 0
    real = os.path.realpath(ruta if os.path.isabs(ruta) else os.path.join(RAIZ, ruta))
    en_casos = dentro(real, CASOS)

    if ev.get("hook_event_name") == "PostToolUse":
        if en_casos and real.endswith(os.path.join("prospectos", "registro.json")):
            r = subprocess.run([sys.executable, "-I", os.path.join(RAIZ, "harness", "scripts", "barrer_portales.py"),
                                os.path.dirname(real), "--tablero"], capture_output=True, text=True)
            if r.returncode:
                print(f"No se pudo re-generar PROSPECTOS.md: {r.stderr.strip()[-400:]}", file=sys.stderr)
                return 2  # se muestra a Claude: el JSON del registro probablemente quedó inválido
        return 0

    rel = os.path.relpath(real, CASOS) if en_casos else ""
    if en_casos and os.sep + "documentos" + os.sep in os.sep + rel:
        print(f"Bloqueado: {ruta} está en documentos/, que guarda los originales de solo lectura "
              "(CLAUDE.md, regla 5). Trabaja sobre texto/ o escribe en la carpeta del caso.", file=sys.stderr)
        return 2

    if not en_casos and dentro(real, os.path.realpath(RAIZ)):
        nuevo = texto_nuevo(ti)
        hallados = [n for n, p in PATRONES.items() if p.search(nuevo)]
        if hallados:
            print(f"Bloqueado: el texto para {os.path.relpath(real, RAIZ)} contiene {', '.join(hallados)}. "
                  "El harness es público; los datos de un caso van solo en casos/ (CLAUDE.md, regla 6). "
                  "En plantillas y ejemplos usa marcadores como 50C-XXXXXXX.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
