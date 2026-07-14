"""Extrae el glosario bilingue del "Tesoro Jaqaru" a un CSV estructurado.

    python scripts/extract_glosary_tesoro.py --input data/raw/glosario-tesoro-jaqaru.pdf --output data/processed/glosary-tesoro.csv

El PDF maqueta el glosario como una tabla de tres columnas SIN bordes ni
separadores: las celdas solo se distinguen por su posicion horizontal.

    x < 75          75 <= x < 205            x >= 205
    numero        | frase en castellano    | frase en jaqaru

Ademas, una entrada larga se reparte en varias lineas y solo la primera lleva
el numero; las siguientes son continuacion de la celda correspondiente.

El CSV resultante descarta el numero y publica las columnas "jqr","esp" (en ese
orden), con todos los campos entrecomillados segun RFC 4180.

Dependencia: pdfplumber (`pip install pdfplumber`).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("Falta la dependencia 'pdfplumber'. Instalala con: pip install pdfplumber")


DEFAULT_INPUT = Path("data/raw/glosario-tesoro-jaqaru.pdf")
DEFAULT_OUTPUT = Path("data/processed/glosary-tesoro.csv")

# Fronteras horizontales de las tres columnas, en puntos PDF. Medidas sobre el
# documento: los numeros arrancan en x=61, el castellano en x=76 y el jaqaru en
# x=211. Los valores intermedios dejan margen para el jitter de la maqueta.
ESP_X = 75.0
JQR_X = 205.0

# Tolerancia vertical para considerar que dos palabras van en el mismo renglon.
LINE_TOL = 3.0

# Numero de fila del glosario: la primera celda es un ordinal ("12", "12.", "12)").
ROW_NUM_RE = re.compile(r"^\d{1,4}[.)]?$")

# Pie de pagina: un renglon con solo cifras (la numeracion del folleto original).
FOOTER_RE = re.compile(r"^[\d\s]+$")


def clean(text: str) -> str:
    """Colapsa espacios (incluidos los no separables del PDF) y recorta los bordes."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def group_lines(words: list[dict]) -> list[list[dict]]:
    """Agrupa las palabras de una pagina en renglones segun su coordenada vertical."""
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= LINE_TOL:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def split_columns(line: list[dict]) -> tuple[str, str, str]:
    """Reparte las palabras de un renglon en (numero, castellano, jaqaru)."""
    cells: tuple[list[str], list[str], list[str]] = ([], [], [])
    for word in sorted(line, key=lambda w: w["x0"]):
        index = 0 if word["x0"] < ESP_X else (1 if word["x0"] < JQR_X else 2)
        cells[index].append(word["text"])
    return tuple(clean(" ".join(cell)) for cell in cells)  # type: ignore[return-value]


def extract(pdf_path: Path) -> list[tuple[str, str]]:
    """Recorre el PDF y devuelve las filas del glosario como (jaqaru, castellano).

    Un renglon que empieza por un ordinal en la columna del numero abre una
    entrada nueva; los demas prolongan la entrada abierta. Los titulos y las
    cabeceras aparecen antes de la primera entrada y se descartan solos; el pie
    de pagina se filtra aparte para que no se pegue a la ultima entrada.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"No se encontro el PDF de entrada: {pdf_path}")

    rows: list[tuple[str, str]] = []
    current: list[str] | None = None  # [castellano, jaqaru] de la entrada abierta

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for line in group_lines(page.extract_words()):
                    number, esp, jqr = split_columns(line)

                    if FOOTER_RE.match(f"{number} {esp} {jqr}"):
                        continue

                    if ROW_NUM_RE.match(number):
                        current = [esp, jqr]
                        rows.append(("", ""))  # se rellena al cerrar la entrada
                    elif current is None or number:
                        continue  # cabecera, pie de pagina o ruido fuera de tabla
                    else:
                        if esp:
                            current[0] = f"{current[0]} {esp}".strip()
                        if jqr:
                            current[1] = f"{current[1]} {jqr}".strip()

                    rows[-1] = (current[1], current[0])
    except FileNotFoundError:
        raise
    except Exception as exc:  # PDF corrupto, cifrado o ilegible
        raise RuntimeError(f"No se pudo procesar el PDF '{pdf_path}': {exc}") from exc

    return [(jqr, esp) for jqr, esp in rows if jqr and esp]


def write_csv(rows: list[tuple[str, str]], output_path: Path) -> None:
    """Escribe el CSV en UTF-8 con todos los campos entre comillas dobles."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # newline="" es obligatorio: deja que el modulo csv controle el fin de linea.
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(["jqr", "esp"])
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        rows = extract(args.input)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not rows:
        print(f"Error: no se extrajo ninguna fila de '{args.input}'.", file=sys.stderr)
        return 1

    write_csv(rows, args.output)

    print(f"Entradas extraidas: {len(rows)}")
    print(f"CSV -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
