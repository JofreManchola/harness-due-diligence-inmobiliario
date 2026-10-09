"""Extrae texto de un PDF: usa la capa de texto si existe y, si la página es escaneada, OCR con Apple Vision (español).

Uso: python pdf2txt.py <entrada.pdf> <salida.txt> [desde] [hasta]
"""
import re
import sys

import Quartz
import Vision
from Foundation import NSURL

ESCALA = 2.5
MARCA_AGUA = re.compile(r"^(SUPERINTENDENCIA DE NOTARIADO Y REGISTRO LA GUARDA.*|\* \* \*)$")


def texto_capa(pagina):
    texto = pagina.string() or ""
    return "\n".join(l for l in texto.splitlines() if not MARCA_AGUA.match(l.strip()))


def ocr(pagina):
    caja = pagina.boundsForBox_(Quartz.kPDFDisplayBoxMediaBox)
    ancho, alto = int(caja.size.width * ESCALA), int(caja.size.height * ESCALA)
    ctx = Quartz.CGBitmapContextCreate(None, ancho, alto, 8, 0, Quartz.CGColorSpaceCreateDeviceRGB(),
                                       Quartz.kCGImageAlphaNoneSkipLast)
    Quartz.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
    Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, ancho, alto))
    Quartz.CGContextScaleCTM(ctx, ESCALA, ESCALA)
    pagina.drawWithBox_toContext_(Quartz.kPDFDisplayBoxMediaBox, ctx)
    imagen = Quartz.CGBitmapContextCreateImage(ctx)

    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setRecognitionLanguages_(["es-ES", "en-US"])
    req.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(imagen, None)
    ok, _ = handler.performRequests_error_([req], None)
    if not ok:
        return ""
    obs = list(req.results() or [])
    # de arriba hacia abajo (y de Vision crece hacia arriba), luego izquierda a derecha
    obs.sort(key=lambda o: (-round(o.boundingBox().origin.y + o.boundingBox().size.height / 2, 2),
                            o.boundingBox().origin.x))
    return "\n".join(o.topCandidates_(1)[0].string() for o in obs if o.topCandidates_(1))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    doc = Quartz.PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(sys.argv[1]))
    if doc is None:
        sys.exit(f"no se pudo abrir {sys.argv[1]}")
    total = doc.pageCount()
    desde = max(1, int(sys.argv[3])) if len(sys.argv) > 3 else 1
    hasta = min(total, int(sys.argv[4])) if len(sys.argv) > 4 else total

    partes, n_ocr = [], 0
    for i in range(desde - 1, hasta):
        pagina = doc.pageAtIndex_(i)
        texto, metodo = texto_capa(pagina), "texto"
        if len(texto.strip()) < 40:
            texto, metodo = ocr(pagina), "ocr"
            n_ocr += 1
        partes.append(f"\n===== PÁGINA {i + 1} [{metodo}] =====\n{texto}\n")
        print(f"\r  página {i + 1}/{hasta}", end="", file=sys.stderr, flush=True)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write("".join(partes))
    print(f"\r{sys.argv[1]} -> {sys.argv[2]}: páginas {desde}-{hasta} de {total}, OCR en {n_ocr}", file=sys.stderr)


if __name__ == "__main__":
    main()
