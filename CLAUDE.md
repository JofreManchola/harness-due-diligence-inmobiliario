# Harness de due diligence inmobiliaria — Bogotá, Colombia

Este proyecto sirve para **buscar** inmuebles (principalmente vivienda usada en propiedad horizontal en Bogotá) que cumplan los criterios del comprador y para **analizarlos** antes de comprarlos, hasta llegar a una decisión fundamentada: **COMPRAR / COMPRAR CON CONDICIONES / NEGOCIAR / NO COMPRAR**, con un precio máximo recomendado.

El trabajo lo hace un equipo de agentes especialistas (`.claude/agents/`) en dos etapas:
1. **Búsqueda** (`/buscar-inmuebles`): barrido de portales, ubicación por dirección con Catastro, filtros, preselección y tablero de prospectos. El mejor prospecto pasa a caso con `/promover-prospecto`.
2. **Due diligence** (`/analizar-inmueble`): el equipo completo sobre los documentos del caso.

## Estructura

```
<harness>/                     ← repo público: solo el harness, sin datos de casos
├── CLAUDE.md                  ← este archivo (reglas del harness)
├── .claude/
│   ├── agents/                ← un archivo por rol del equipo experto
│   ├── skills/                ← /buscar-inmuebles, /promover-prospecto, /nuevo-inmueble, /analizar-inmueble, /comparar-inmuebles
│   ├── hooks/proteger-datos.py ← hook de Claude Code: documentos/ de solo lectura, sin datos de casos en el harness, tablero al día
│   └── settings.json          ← permisos y registro de los hooks
├── harness/
│   ├── conocimiento/          ← marco legal, costos de cierre, señales de alerta, fuentes de verificación, búsqueda de inmuebles
│   ├── plantillas/            ← formatos de ficha, informes, perfil, índice de casos, checklist de visita, criterios y ficha de prospecto…
│   ├── scripts/               ← inicializar_casos.sh, nuevo_inmueble.sh, extraer.sh (texto + OCR), md2pdf.sh,
│   │                            barrer_portales.py (búsqueda), zona.py (polígono + geocodificación de direcciones con Catastro)
│   └── git-hooks/             ← pre-commit que bloquea datos de casos en el repo público
└── casos → ../<harness>-casos ← symlink a un directorio aparte: repo Git PRIVADO, local y sin remoto
    ├── INDICE.md              ← índice de casos: estado, dictamen, precios y bitácora
    ├── perfil-comprador.md    ← presupuesto, financiación y objetivos del comprador (aplica a todos los inmuebles)
    ├── comparativo.md         ← (opcional) generado por /comparar-inmuebles
    ├── prospectos/            ← búsqueda: criterios.json, zona.geojson, registro.json, PROSPECTOS.md (tablero),
    │                            barridos/<fecha>/ (crudo por portal, candidatos, resumen), fichas/<id>.md
    └── inmueble-x/            ← una carpeta por inmueble
        ├── README.md              ← índice y estado del análisis
        ├── oferta.md              ← precio pedido, administración, contacto, notas de visita (lo llena el comprador)
        ├── documentos/            ← PDFs originales (no se modifican nunca)
        ├── texto/                 ← texto extraído/OCR de cada PDF (generado)
        ├── fotos/                 ← fotos de la visita (opcional)
        ├── 00-ficha.md            ← datos clave del inmueble consolidados
        ├── 01-inventario-documental.md ← qué hay, qué falta, vigencias
        ├── analisis/              ← un informe por especialista (10-…90-)
        ├── revision/              ← informe del abogado del diablo
        ├── pendientes.md          ← documentos faltantes, preguntas al vendedor, verificaciones manuales
        └── 99-DECISION.md         ← dictamen final del comité
```

## Equipo de búsqueda (`/buscar-inmuebles`)

| Fase | Quién | Salida |
|---|---|---|
| 0 | coordinador: criterios y zona (polígono validado con direcciones y sectores catastrales) | `prospectos/criterios.json`, `prospectos/zona.geojson` |
| 1 | `harness/scripts/barrer_portales.py` (Fincaraíz, Metrocuadrado, Ciencuadras) | `barridos/<fecha>/`, `registro.json`, `PROSPECTOS.md` |
| 2 | `explorador-mercado` (fuentes que el script no cubre) | `barridos/<fecha>/crudo-manual.jsonl`, `explorador.md` |
| 3 | `analista-prospectos` (abre cada anuncio, confirma y prioriza) | `fichas/<id>.md`, estados en `registro.json`, `barridos/<fecha>/analisis.md` |

Un prospecto es una pista, no un inmueble analizado: su puntaje ordena a quién llamar primero. Lo que decide la compra es el due diligence.

## Equipo de due diligence (orden de ejecución)

| Fase | Rol (archivo en `.claude/agents/`) | Salida |
|---|---|---|
| 1 | `documentalista` | `00-ficha.md`, `01-inventario-documental.md` |
| 2 (paralelo) | `abogado-titulos` | `analisis/10-titulos.md` |
| 2 | `analista-propiedad-horizontal` | `analisis/20-propiedad-horizontal.md` |
| 2 | `analista-fiscal-catastral` | `analisis/30-fiscal-catastral.md` |
| 2 | `perito-valuador` | `analisis/40-valoracion-mercado.md` |
| 2 | `analista-urbano-riesgos` | `analisis/50-urbanismo-riesgos.md` |
| 2 | `oficial-cumplimiento` | `analisis/60-cumplimiento-partes.md` |
| 2 | `inspector-tecnico` | `analisis/70-tecnico.md` |
| 3 | `analista-financiero` (usa 30 y 40) | `analisis/80-financiero.md` |
| 3 | `abogado-transaccional` (usa todo lo anterior) | `analisis/90-transaccion.md` |
| 4 | `abogado-del-diablo` | `revision/95-abogado-del-diablo.md` |
| 5 | `comite-decision` | `99-DECISION.md`, `pendientes.md` |

## Reglas para todos los agentes

1. **Evidencia o nada.** Toda afirmación sobre el inmueble cita su fuente: `(Cert apto, anotación 5)`, `(Escritura, pág. 12)`, `(fuente web: URL, fecha de consulta)`. Si no hay fuente, se marca como **SUPUESTO** o **PENDIENTE**.
2. **Clasifica cada hallazgo** con severidad:
   - `[BLOQUEANTE]` impide comprar hasta que se resuelva (p. ej. embargo vigente, falsa tradición, vendedor no es titular).
   - `[ALTO]` condiciona la compra o el precio; debe quedar como condición en la promesa.
   - `[MEDIO]` requiere gestión o verificación, no cambia la decisión por sí solo.
   - `[INFO]` / `[OK]` sin riesgo o verificado favorablemente.
3. **Distingue verificado vs. por verificar.** Los agentes no pueden consultar bases restringidas (VUR, Rama Judicial con captcha, listas restrictivas). Para esas, dejar el procedimiento exacto en `pendientes.md` y no darlas por buenas.
4. **No inventar cifras normativas.** Tarifas notariales, de registro, UVT, tasas de interés, etc. cambian cada año: consultarlas en la web (con fecha) o usar los valores de `harness/conocimiento/` marcados con su año y advertirlo.
5. **Los documentos originales son de solo lectura.** Trabajar sobre `texto/`. Si el OCR es dudoso en un dato crítico (número de matrícula, cédula, área, coeficiente), abrir el PDF con la herramienta Read (páginas concretas) y confirmar.
6. **Datos personales**: cédulas y datos de vendedores se quedan en este equipo. No publicarlos en artifacts ni servicios externos; en búsquedas web usar nombres solo para verificaciones de cumplimiento, nunca subir documentos. Todo dato de un caso (incluidos el perfil y las finanzas del comprador) vive solo en `casos/`; nunca se copia al harness (agentes, plantillas, conocimiento, ejemplos), que es público.
7. Escribir en español, conciso, con tablas cuando ayuden. Cada informe termina con **Conclusión del especialista** (1 párrafo) y **Acciones requeridas** (lista con responsable y momento: antes de oferta / antes de promesa / antes de escritura / post-registro).
8. Este harness no sustituye a un abogado, avaluador certificado (RAA) o ingeniero; su objetivo es llegar a esas instancias con las preguntas correctas y saber cuándo un hallazgo exige su intervención.

## Uso

- Buscar: `/buscar-inmuebles` (criterios en `casos/prospectos/criterios.json`; se pueden dar en texto libre) → tablero en `casos/prospectos/PROSPECTOS.md`. El estado de cada prospecto se cambia en `registro.json` y el hook re-genera el tablero.
- Pasar un prospecto a análisis: `/promover-prospecto <id>` (crea el caso con `oferta.md` prellenada).
- Primera vez: `harness/scripts/inicializar_casos.sh` crea `../<harness>-casos/`, lo enlaza como `casos/` y lo inicializa como repo Git privado.
- Nuevo inmueble: `/nuevo-inmueble inmueble-b` → copiar PDFs a `casos/inmueble-b/documentos/` → llenar `casos/inmueble-b/oferta.md`.
- Análisis completo: `/analizar-inmueble inmueble-b`.
- Comparar varios: `/comparar-inmuebles`.
- Solo extraer texto: `harness/scripts/extraer.sh inmueble-b`.
- Exportar informes a PDF (estilo en `harness/md-to-pdf.json`): `harness/scripts/md2pdf.sh casos/inmueble-b/99-DECISION.md` (con `--horizontal` para tablas anchas, p. ej. `PROSPECTOS.md`).

## Dos repositorios Git

- **Harness (esta carpeta)**: público. `.gitignore` excluye `/casos` y el hook `harness/git-hooks/pre-commit` bloquea rutas de casos, PDFs, imágenes, matrículas y CHIP.
- **Casos (`casos/`)**: privado, local, sin remoto. Versiona todo, incluidos los PDFs originales. Para revisar qué cambió en un análisis sin releerlo: `git -C casos diff`, `git -C casos log -p <inmueble>/99-DECISION.md`.
- **Hooks de Claude Code** (`.claude/hooks/proteger-datos.py`): bloquean escribir en `casos/*/documentos/` y escribir matrículas, CHIP o cédulas en archivos del harness; tras editar `prospectos/registro.json` re-generan `PROSPECTOS.md`.
- `casos/` es un symlink: busca con rutas explícitas (`casos/<inmueble>/texto/`), porque las búsquedas recursivas desde la raíz no lo recorren.
