# Harness de due diligence inmobiliaria con agentes de IA — Bogotá

Un equipo de 12 agentes especialistas en [Claude Code](https://claude.com/claude-code) que revisa un inmueble usado en propiedad horizontal en Bogotá antes de comprarlo. Lee los documentos del caso (certificados de tradición, escrituras, reglamento de PH, predial, cédulas), cruza la información con fuentes públicas y termina en un dictamen del comité:

**COMPRAR · COMPRAR CON CONDICIONES · NEGOCIAR · NO COMPRAR**, con precio de apertura, objetivo y retiro, condiciones para la promesa y pendientes ordenados por etapa.

> No sustituye a un abogado, un avaluador certificado (RAA) ni un ingeniero. Sirve para llegar a ellos con las preguntas correctas y saber cuándo un hallazgo exige su intervención.

## Cómo trabaja

```mermaid
flowchart LR
  D[Documentalista<br/>ficha + inventario] --> E
  subgraph E[Especialistas en paralelo]
    T[Títulos] & PH[Propiedad horizontal] & F[Fiscal y catastral] & V[Valuador] & U[Urbanismo y riesgos] & C[Cumplimiento] & I[Inspector técnico]
  end
  E --> FI[Financiero] & TR[Transaccional]
  FI & TR --> AD[Abogado del diablo]
  AD --> CO[Comité de decisión<br/>99-DECISION.md]
```

| Fase | Agente (`.claude/agents/`) | Produce |
|---|---|---|
| 1 | `documentalista` | Ficha del inmueble e inventario documental (qué hay, qué falta, vigencias) |
| 2 | `abogado-titulos`, `analista-propiedad-horizontal`, `analista-fiscal-catastral`, `perito-valuador`, `analista-urbano-riesgos`, `oficial-cumplimiento`, `inspector-tecnico` | Un informe por especialidad, en paralelo |
| 3 | `analista-financiero`, `abogado-transaccional` | Costo total y escenarios de crédito; condiciones de la oferta y cláusulas de la promesa |
| 4 | `abogado-del-diablo` | Revisión adversarial: supuestos sin verificar, contradicciones, sesgos |
| 5 | `comite-decision` | Dictamen, scorecard, precios, condiciones y `pendientes.md` |

Reglas que siguen todos los agentes (detalle en [CLAUDE.md](CLAUDE.md)):

- **Evidencia o nada.** Cada afirmación cita su fuente (documento y página, anotación del certificado o URL con fecha). Lo que no tiene fuente queda como SUPUESTO o PENDIENTE.
- **Severidad explícita.** Cada hallazgo es `[BLOQUEANTE]`, `[ALTO]`, `[MEDIO]` o `[OK]`.
- **Verificado no es lo mismo que por verificar.** Lo que requiere bases restringidas (VUR, Rama Judicial, listas restrictivas) se deja como procedimiento en `pendientes.md`. No se da por bueno.
- **Las cifras normativas tienen año.** Tarifas, UVT y tasas se consultan con fecha o se toman de `harness/conocimiento/` con advertencia.

## Requisitos

- [Claude Code](https://claude.com/claude-code). Los agentes y skills se cargan solos desde `.claude/`.
- macOS con `zsh` y `python3`. El OCR de PDFs escaneados usa Apple Vision; el entorno virtual se crea solo la primera vez.
- Node.js (`npx`), solo si quieres exportar informes a PDF.

## Primeros pasos

### 1. Prepara el directorio privado de casos (una sola vez)

```bash
harness/scripts/inicializar_casos.sh            # por defecto crea ../<esta-carpeta>-casos
```

Los casos tienen documentos de identidad, escrituras y tus finanzas, así que **nunca** viven dentro de este repo. El script:

- crea el directorio de casos **fuera** del repo y lo enlaza como `casos/` (el symlink está en `.gitignore`);
- lo inicializa como un **repositorio Git local y sin remoto**, para que tengas la traza de cada cambio del análisis;
- copia las plantillas de `perfil-comprador.md` e `INDICE.md`;
- activa el hook [`harness/git-hooks/pre-commit`](harness/git-hooks/pre-commit), que bloquea commits del repo público con rutas de casos, PDFs, imágenes, matrículas o CHIP catastrales.

Después llena `casos/perfil-comprador.md` (objetivo, horizonte, ahorro, ingresos, crédito). Sin él, el análisis financiero trabaja con supuestos.

### 2. Crea un caso

En Claude Code, dentro de esta carpeta:

```
/nuevo-inmueble apto-chapinero
```

Se crea `casos/apto-chapinero/` y el caso se registra en `casos/INDICE.md`. Después:

1. Copia los PDFs en `casos/apto-chapinero/documentos/`. Como mínimo: certificado de tradición de **cada** matrícula (apartamento, garaje, depósito), escritura con la que compró el vendedor, reglamento de PH, predial del año y cédulas de los vendedores. La lista completa está en [checklist-documentos.md](harness/plantillas/checklist-documentos.md).
2. Llena `casos/apto-chapinero/oferta.md`: precio pedido, administración, quién vende y notas de la visita.

### 3. Analiza

```
/analizar-inmueble apto-chapinero
```

El coordinador extrae el texto de los PDFs (con OCR si hace falta) y lanza las 5 fases. Un análisis completo tarda del orden de decenas de minutos, según el tamaño del reglamento. Al final tendrás:

| Archivo | Para qué |
|---|---|
| `99-DECISION.md` | Dictamen, precios, condiciones y respuesta al abogado del diablo |
| `pendientes.md` | Lo que falta, ordenado por etapa (antes de oferta, de promesa, de escritura) y por responsable |
| `analisis/10…90-*.md`, `revision/95-*.md` | Informe de cada especialista |
| `README.md` | Estado del caso y enlaces |

### 4. Itera

Cuando llegue un documento nuevo, hagas la visita o cambie el precio:

```
/analizar-inmueble apto-chapinero solo:analista-propiedad-horizontal   # re-ejecuta un rol y luego el comité
git -C casos diff                                                       # qué cambió, sin releer todo
git -C casos add -A && git -C casos commit -m "apto-chapinero: llega paz y salvo, actualiza PH"
```

Con varios casos analizados, `/comparar-inmuebles` arma un ranking ponderado según tu perfil.

## Estructura

```
.
├── CLAUDE.md               reglas del harness para todos los agentes
├── .claude/agents/         un archivo por rol (12)
├── .claude/skills/         /nuevo-inmueble, /analizar-inmueble, /comparar-inmuebles
├── harness/conocimiento/   marco legal, costos de transacción en Bogotá, señales de alerta, fuentes de verificación
├── harness/plantillas/     ficha, informe de decisión, oferta, perfil, checklists de documentos y visita, preguntas al vendedor
├── harness/scripts/        inicializar_casos, nuevo_inmueble, extraer (texto + OCR), md2pdf
├── harness/git-hooks/      pre-commit que protege el repo público
├── notes.md                el prompt con el que empezó este proyecto
└── casos → ../…-casos      (no versionado aquí) repo privado con tus casos
```

## Cómo nació

[notes.md](notes.md) tiene el pedido original: cinco líneas pidiendo un harness con roles expertos para decidir si comprar un apartamento en Bogotá. Todo lo demás (los roles, las reglas de evidencia, la revisión adversarial y el comité) se diseñó con Claude Code a partir de ese pedido y se probó con un caso real, que queda fuera de este repositorio.

## Licencia

© 2026 Jofre Manchola. Todos los derechos reservados. Ver [LICENSE](LICENSE).
