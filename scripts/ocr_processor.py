"""
scripts/ocr_processor.py

Extrae texto mediante OCR desde capturas de video (data/raw/tiktok/)
y genera un .txt por imagen en data/processed/tiktok/.

Uso:
    python scripts/ocr_processor.py TT-001.png TT-002.jpg TT-003.png

Requisitos:
    pip install easyocr opencv-python-headless numpy
    (EasyOCR descarga sus propios modelos de detección/reconocimiento
    la primera vez que se ejecuta; no requiere Tesseract instalado.)
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import easyocr

RAW_DIR = Path("data/raw/tiktok")
PROCESSED_DIR = Path("data/processed/tiktok")
VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
IDIOMAS = ["es"]  # No existe modelo para jaqaru; 'es' cubre el alfabeto
                  # latino base, con errores esperables en diacríticos
                  # propios del jaqaru (glotalizadas, retroflejas).
UMBRAL_CONFIANZA = 0.20  # EasyOCR reporta confianza en [0, 1]; 0.35 es
                         # permisivo a propósito, para no perder texto
                         # real con fuentes decorativas de baja nitidez.

_lector = None  # se inicializa una sola vez (carga de modelos es costosa)


def obtener_lector() -> easyocr.Reader:
  global _lector
  if _lector is None:
    print("[info] Cargando modelos de EasyOCR (solo la primera vez)...")
    _lector = easyocr.Reader(IDIOMAS, gpu=False)
  return _lector


def preprocesar(ruta: Path) -> np.ndarray:
  """Aumenta resolución para mejorar la detección de fuentes finas o
  con contorno delgado; EasyOCR ya maneja color y fondo complejo, por
  lo que NO se convierte a escala de grises ni se binariza."""
  imagen = cv2.imread(str(ruta))
  if imagen is None:
    raise ValueError("OpenCV no pudo leer la imagen")

  alto, ancho = imagen.shape[:2]
  if max(alto, ancho) < 1500:
    imagen = cv2.resize(imagen, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

  return imagen


def reconstruir_texto(resultados: list) -> str:
  """Ordena las detecciones de arriba hacia abajo, agrupando por línea
  aproximada según la coordenada vertical del cuadro delimitador."""
  detecciones = []
  for cuadro, texto, confianza in resultados:
    if not texto.strip() or confianza < UMBRAL_CONFIANZA:
      continue
    ys = [punto[1] for punto in cuadro]
    xs = [punto[0] for punto in cuadro]
    detecciones.append({
      "texto": texto.strip(),
      "top": min(ys),
      "left": min(xs),
    })

  if not detecciones:
    return ""

  detecciones.sort(key=lambda d: d["top"])

  # Agrupa en líneas: detecciones cuyo 'top' cae dentro de un margen de
  # tolerancia se consideran parte de la misma línea visual.
  lineas = []
  linea_actual = [detecciones[0]]
  margen = 20  # píxeles de tolerancia vertical

  for det in detecciones[1:]:
    if abs(det["top"] - linea_actual[-1]["top"]) <= margen:
      linea_actual.append(det)
    else:
      lineas.append(linea_actual)
      linea_actual = [det]
  lineas.append(linea_actual)

  texto_final = []
  for linea in lineas:
    linea_ordenada = sorted(linea, key=lambda d: d["left"])
    texto_final.append(" ".join(d["texto"] for d in linea_ordenada))

  return "\n".join(texto_final)


def resolver_ruta_entrada(nombre_archivo: str) -> Path:
  ruta_exacta = RAW_DIR / nombre_archivo
  if ruta_exacta.exists():
    return ruta_exacta

  stem = Path(nombre_archivo).stem
  for ext in VALID_EXTENSIONS:
    candidato = RAW_DIR / f"{stem}{ext}"
    if candidato.exists():
      print(f"[aviso] '{nombre_archivo}' no existe; usando '{candidato.name}'")
      return candidato

  return ruta_exacta


def procesar_archivo(nombre_archivo: str) -> None:
  ruta_entrada = resolver_ruta_entrada(nombre_archivo)

  if ruta_entrada.suffix.lower() not in VALID_EXTENSIONS:
    print(f"[omitido] Extensión no soportada: {nombre_archivo}")
    return

  if not ruta_entrada.exists():
    print(f"[error] No se encontró: {ruta_entrada}")
    return

  try:
    imagen = preprocesar(ruta_entrada)
    lector = obtener_lector()
    resultados = lector.readtext(imagen)
    texto = reconstruir_texto(resultados)
  except Exception as exc:
    print(f"[error] Fallo al procesar {nombre_archivo}: {exc}")
    return

  PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
  ruta_salida = PROCESSED_DIR / f"{ruta_entrada.stem}.txt"
  ruta_salida.write_text(texto, encoding="utf-8")

  if not texto.strip():
    print(f"[aviso] {nombre_archivo}: OCR no detectó texto confiable (txt vacío)")
  else:
    print(f"[ok] {nombre_archivo} -> {ruta_salida}")


def main() -> None:
  parser = argparse.ArgumentParser(
    description="OCR de capturas de video en data/raw/tiktok/ con EasyOCR"
  )
  parser.add_argument(
    "archivos",
    nargs="+",
    help="Nombres de archivo (con extensión) dentro de data/raw/tiktok/",
  )
  args = parser.parse_args()

  if not RAW_DIR.exists():
    sys.exit(f"[error] No existe el directorio de entrada: {RAW_DIR}")

  for nombre_archivo in args.archivos:
    procesar_archivo(nombre_archivo)


if __name__ == "__main__":
  main()