# Comando de ejecución:
# python scripts/extract_vocabulary.py --input_path "data/raw/vocabulario-jaqaru-neli-belleza.md" --output_path "data/processed/vocabulary-jaqaru.csv"

import argparse
import os
import re
import csv

def setup_directories(output_path):
  """Crea los directorios necesarios si no existen."""
  dir_name = os.path.dirname(output_path)
  if dir_name and not os.path.exists(dir_name):
    os.makedirs(dir_name, exist_ok=True)
    print(f"Directorio creado: {dir_name}")

def extract_jaqaru_vocabulary(input_md, output_csv):
  """
  Parsea el vocabulario Jaqaru desde Markdown y extrae las columnas
  jqr, gram_cat y esp hacia un archivo CSV limpio.
  """
  # Mapeo de abreviaturas gramaticales oficiales del libro
  cat_map = {
    's.': 'sustantivo',
    'v.': 'verbo',
    'adj.': 'adjetivo',
    'adv.': 'adverbio',
    'intj.': 'interjección',
    'pron.': 'pronombre'
  }
  
  if not os.path.exists(input_md):
    print(f"Error: No se encontró el archivo de origen en '{input_md}'")
    return

  print(f"Leyendo archivo origen: {input_md}...")
  with open(input_md, 'r', encoding='utf-8') as f:
    content = f.read()

  # Normalización del texto: unificar saltos de línea para procesar párrafos continuos
  # conservando el delimitador de derivadas '║'
  content_single_line = content.replace('\r\n', '\n').replace('\n', ' ')
  # Reducir espacios múltiples
  content_single_line = re.sub(r'\s+', ' ', content_single_line)
  
  # Separar por el carácter de sub-entrada/derivada '║'
  raw_tokens = content_single_line.split('║')
  
  extracted_data = []
  
  print("Procesando entradas y sub-entradas...")
  for token in raw_tokens:
    token = token.strip()
    if not token:
      continue
        
    # 1. Extraer término en Jaqaru (marcado en Markdown con **palabra**)
    match_jqr = re.search(r'\*\*([^*]+)\*\*', token)
    if not match_jqr:
      continue
        
    jqr_word = match_jqr.group(1).strip().rstrip('.')
    
    # Omitir si es un título de sección o indicador de página del convertidor
    if "INICIO PÁGINA" in jqr_word or jqr_word.isupper() and len(jqr_word) == 1:
      continue
        
    rest_of_text = token[match_jqr.end():].strip()
    
    # 2. Identificar categoría gramatical (simple o compuesta como 'adj. o s.')
    match_cat = re.search(
      r'\b(s\.|v\.|adj\.|adv\.|intj\.|pron\.)(?:\s+(?:o|y)\s+(s\.|v\.|adj\.|adv\.|intj\.|pron\.))?', 
      rest_of_text
    )
    
    gram_cat = "desconocido"
    esp_translation = rest_of_text
    
    if match_cat:
      cat_text = match_cat.group(0)
      # Reemplazar abreviaturas por nombres legibles en español
      for abbr, full in cat_map.items():
        cat_text = cat_text.replace(abbr, full)
      gram_cat = cat_text
        
      # El significado inicia inmediatamente después de la categoría gramatical
      esp_translation = rest_of_text[match_cat.end():].strip()
        
    # 3. Limpieza del significado en Español
    # Cortar el texto si empiezan ejemplos de uso con '=' o fragmentos en cursiva ('_')
    esp_translation = re.split(r'[_=]', esp_translation)[0].strip()
    # Eliminar puntuaciones sueltas al final de la traducción
    esp_translation = esp_translation.rstrip(';').rstrip('.').strip()
    
    # Evitar añadir registros vacíos de control
    if jqr_word and esp_translation:
      extracted_data.append({
        'jqr': jqr_word,
        'esp': esp_translation,
        'gram_cat': gram_cat
      })

  # Asegurar la existencia de las carpetas de destino
  setup_directories(output_csv)
  
  # 4. Exportar a archivo CSV
  print(f"Exportando {len(extracted_data)} registros a CSV...")
  with open(output_csv, 'w', encoding='utf-8', newline='') as csv_file:
    fieldnames = ['jqr', 'esp', 'gram_cat']
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    
    writer.writeheader()
    for row in extracted_data:
      writer.writerow(row)
        
  print(f"¡Extracción completada con éxito! Archivo guardado en: {output_csv}")


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extrae vocabulario Jaqaru a CSV.")
  parser.add_argument("--input_path", type=str, required=True, help="Ruta al archivo Markdown de origen")
  parser.add_argument("--output_path", type=str, required=True, help="Ruta al archivo CSV de destino")
  args = parser.parse_args()

  extract_jaqaru_vocabulary(args.input_path, args.output_path)