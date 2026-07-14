// Extrae el vocabulario jaqaru (Neli Belleza) a un CSV estructurado.
//
//   node scripts/extract_vocabulary.mjs \
//     --input data/raw/vocabulario-jaqaru-neli-belleza.md \
//     --output data/processed/vocabulary-jaqaru.csv
//
// Columnas: jqr, esp, gram_cat

import fs from 'node:fs';
import path from 'node:path';

// Abreviaturas segun la seccion "Abreviaturas" del propio libro.
// Las de varios tokens van primero: "v. t." debe ganarle a "v.".
const CATS = [
  'pron. rel.', 'p. e.', 'v. i.', 'v. t.', 'u. a.',
  'adj.', 'adv.', 'col.', 'conj.', 'intj.', 'onom.',
  'pref.', 'pron.', 'suf.', 's.', 'v.',
];
const CAT_ALT = CATS.map((c) => c.replace(/[.]/g, '\\.').replace(/ /g, '\\s*')).join('|');
// Categoria simple o compuesta ("s. y adj.", "adj. o s.")
const CAT_RE = new RegExp(`^(?:${CAT_ALT})(?:\\s*(?:y|o)\\s*(?:${CAT_ALT}))*`);

const HEADWORD_RE = /^((?:\*\*[^*]+\*\*(?:\s*(?:o|y|,)\s*)?)+)/;
const HOMOGRAPH_RE = /^\(\s*(\d+)\s*\)\s*\.?\s*/;

// La conversion PDF->Markdown perdio la negrita en ~100 entradas (sobre todo en
// las secciones I, K, N e Y). Se reconocen igual por su forma: "lema. cat. ...".
// El lema se toma entero y con avidez, y la categoria se valida aparte: asi una
// linea de continuacion como "adv. hacia afuera" no se parte en lema "ad" + "v.".
const UNBOLD_RE = /^(-?[\p{L}’']{2,})\s*\.?\s*/u;

/**
 * Cabecera de una entrada sin negrita. Devuelve {lemmas, rest} o null.
 * Exige categoria gramatical explicita: sin negrita no aceptamos referencias
 * cruzadas sueltas, porque "manos. V. ishara" es continuacion, no entrada.
 */
function unboldHead(chunk) {
  const m = chunk.match(UNBOLD_RE);
  if (!m) return null;
  let rest = chunk.slice(m[0].length);
  const hom = rest.match(HOMOGRAPH_RE);
  if (hom) rest = rest.slice(hom[0].length);
  if (!CAT_RE.test(rest)) return null;
  return { lemmas: [m[1]], rest: chunk.slice(m[0].length) };
}

/** Cabecera en negrita: "**lema**", "**a** o **b**", "**a** , **b**". */
function boldHead(chunk) {
  const m = chunk.match(HEADWORD_RE);
  if (!m) return null;
  // Las variantes van entre negritas ("**a** o **b**") pero tambien dentro de una
  // sola ("**at’trhatrha, at’uru.**"), asi que se separa en los dos niveles.
  const lemmas = m[1]
    .split(/\*\*\s*(?:o|y|,)\s*\*\*|\*\*\s*\*\*/)
    .flatMap((part) => cleanLemma(part).split(/\s*,\s*|\s+o\s+/))
    .map((s) => s.trim())
    .filter(Boolean);
  if (!lemmas.length) return null;
  return { lemmas, rest: chunk.slice(m[0].length) };
}

/** Inicio de entrada: en negrita, o sin ella si la conversion la perdio. */
function entryHead(chunk) {
  return boldHead(chunk) ?? unboldHead(chunk);
}

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 2) out[argv[i].replace(/^--/, '')] = argv[i + 1];
  return out;
}

/**
 * Quita las notas del editor delimitadas por ***...*** (rule 2).
 *
 * El delimitador es un grupo de exactamente tres asteriscos, no de cuatro: el
 * markdown trae restos como "**_ants’arpaya_****.**", y confundir esa racha con
 * una nota se comeria el texto hasta la siguiente. De ahi los lookarounds.
 * Algunas notas nunca cierran ("hojas. ***atrmi"): esas mueren con su linea.
 */
const NOTE_OPEN = String.raw`(?<!\*)\*\*\*(?!\*)`;
function stripEditorNotes(text) {
  return text
    .replace(new RegExp(`${NOTE_OPEN}(?=[^\\s*])[\\s\\S]{0,300}?${NOTE_OPEN}`, 'g'), ' ')
    .replace(new RegExp(`${NOTE_OPEN}[^\\n]*`, 'g'), ' ');
}

/**
 * Reune las palabras que el PDF partio con guion al final de renglon
 * ("ani- males" -> "animales") y normaliza la cita de sufijos ("- taki" -> "-taki").
 * El guion de un lema sufijo va pegado y precedido de espacio, asi que no se toca.
 */
function dehyphenate(text) {
  return text
    .replace(/([\p{L}’'])-\s+(?=[\p{L}])/gu, '$1')
    .replace(/(^|[\s(])-\s+(?=[\p{L}])/gu, '$1-');
}

/** Deja el texto en espanol limpio de marcas markdown. */
function cleanEsp(text) {
  return dehyphenate(
    text
      .replace(/\*+/g, '')
      .replace(/_/g, '')
      .replace(/\s+/g, ' '),
  )
    .replace(/\s+([,;.)])/g, '$1')
    .replace(/(\()\s+/g, '$1')
    .trim()
    .replace(/^[;,.\s]+/, '')
    .trim();
}

/** Normaliza un lema jaqaru: sin markdown, sin punto final. */
function cleanLemma(word) {
  return dehyphenate(
    word
      .replace(/\*+/g, '')
      .replace(/_/g, '')
      .replace(/\s+/g, ' '),
  )
    .trim()
    .replace(/[.,;]+$/, '')
    .trim();
}

function extract(inputPath) {
  const raw = fs.readFileSync(inputPath, 'utf8');
  const lines = raw.split(/\r?\n/);

  // El cuerpo del diccionario empieza en el encabezado "# A";
  // antes de eso van portada, ortografia y abreviaturas.
  const start = lines.findIndex((l) => /^#\s*A\s*$/.test(l));
  if (start === -1) throw new Error('No se encontro el inicio del diccionario (encabezado "# A").');

  const body = lines
    .slice(start + 1)
    .filter((l) => !/^#{1,6}\s/.test(l)); // encabezados de letra y notas al pie sueltas

  // Las notas se quitan sobre el texto completo, porque muchas cruzan el salto
  // de linea ("***aatsts’a,\naatsts’ishi***").
  // El separador real de subentradas es U+2551 (se ve como "||"): convertirlo en
  // salto de linea hace que cada subentrada arranque su propio bloque.
  // Los lemas sufijo empiezan con guion ("-cha"), y el conversor confundio ese
  // guion con una vinieta de lista: "- **cha.** suf. ...". Se devuelve adentro.
  const text = stripEditorNotes(body.join('\n'))
    .replace(/║/g, '\n')
    .replace(/^[ \t]*[-–—][ \t]+\*\*\s*/gm, '**-');

  // Un bloque nuevo empieza donde arranca una entrada; lo demas son lineas de
  // continuacion del bloque anterior (el PDF usa sangria francesa, que se perdio).
  const blocks = [];
  for (const line of text.split('\n')) {
    const l = line.replace(/\*{2,}/g, '**').trim();
    if (!l) continue;
    if (blocks.length === 0 || entryHead(l)) blocks.push(l);
    else blocks[blocks.length - 1] += ' ' + l;
  }

  const records = [];
  const skipped = [];

  for (const chunk of blocks) {
    const head = entryHead(chunk);
    if (!head) {
      appendToPrevious(records, skipped, chunk);
      continue;
    }

    // Restos de negrita mal cerrada entre el lema y la categoria ("**.** v. ...").
    let rest = head.rest.replace(/^[\s.*]+/, '');
    let sense = '';

    // El homografo puede quedar fuera del lema ("**aka** (1) pron.") o dentro
    // ("**-ru (2)**"); en ambos casos se guarda al inicio de la definicion.
    const lemmas = head.lemmas.map((l) => {
      const m = l.match(/^(.*?)\s*\((\d+)\)$/);
      if (!m) return l;
      sense = `(${m[2]}) `;
      return m[1];
    });

    const hom = rest.match(HOMOGRAPH_RE);
    if (hom) {
      sense = `(${hom[1]}) `;
      rest = rest.slice(hom[0].length).trim();
    }

    const catMatch = rest.match(CAT_RE);
    let gramCat;
    let esp;

    if (catMatch) {
      gramCat = normalizeCat(catMatch[0]);
      esp = sense + rest.slice(catMatch[0].length).trim();
    } else if (/^V\.\s/.test(rest)) {
      // Referencia cruzada pura (rule 4): la definicion solo apunta a otro lema.
      gramCat = 'ref';
      esp = sense + rest;
    } else {
      // Sin categoria ni referencia: no es una entrada, es continuacion mal cortada.
      appendToPrevious(records, skipped, chunk);
      continue;
    }

    esp = cleanEsp(esp);
    if (!esp) {
      appendToPrevious(records, skipped, chunk);
      continue;
    }

    // Un mismo encabezado puede traer variantes: "atyama o atyima", "aktraqa, aktraqt'a".
    // Cada variante es un lema propio y comparte definicion.
    for (const jqr of lemmas.filter(Boolean)) {
      records.push({ jqr, esp, gram_cat: gramCat });
    }
  }

  return { records: unweld(records), skipped };
}

/** "v.t." -> "v. t.", "adj. y  s." -> "adj. y s." */
function normalizeCat(text) {
  return text.replace(/\.(?=\p{L})/gu, '. ').replace(/\s+/g, ' ').trim();
}

/**
 * En una veintena de casos el markdown trae la negrita mal cerrada y una entrada
 * queda soldada al final de la definicion anterior ("... V. atr’trhatrha.
 * at’unku. v. tender ..."). Se reconocen porque dentro de la definicion aparece
 * "lema. cat." tras un punto, y se despegan como registros propios.
 */
function unweld(records) {
  const WELD = new RegExp(`\\.\\s+(-?[\\p{L}’']{2,})\\.\\s+(?=(?:${CAT_ALT})\\s)`, 'u');
  const out = [];
  for (const rec of records) {
    let cur = rec;
    for (;;) {
      const m = cur.esp.match(WELD);
      if (!m) break;
      const tail = cur.esp.slice(m.index + m[0].length);
      const catMatch = tail.match(CAT_RE);
      if (!catMatch) break;
      out.push({ ...cur, esp: cur.esp.slice(0, m.index + 1) });
      cur = {
        jqr: m[1],
        esp: cleanEsp(tail.slice(catMatch[0].length)),
        gram_cat: normalizeCat(catMatch[0]),
      };
    }
    out.push(cur);
  }
  return out;
}

function appendToPrevious(records, skipped, chunk) {
  const tail = cleanEsp(chunk);
  if (!tail) return;
  if (records.length === 0) {
    skipped.push(tail);
    return;
  }
  const prev = records[records.length - 1];
  prev.esp = cleanEsp(prev.esp + ' ' + tail);
}

function toCsv(records) {
  const esc = (v) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const out = ['jqr,esp,gram_cat'];
  for (const r of records) out.push([r.jqr, r.esp, r.gram_cat].map(esc).join(','));
  return out.join('\n') + '\n';
}

const args = parseArgs(process.argv);
const inputPath = args.input ?? 'data/raw/vocabulario-jaqaru-neli-belleza.md';
const outputPath = args.output ?? 'data/processed/vocabulary-jaqaru.csv';

const { records, skipped } = extract(inputPath);

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, toCsv(records), 'utf8'); // UTF-8 sin BOM (rule 5)

console.log(`Entradas extraidas: ${records.length}`);
console.log(`Con categoria gramatical: ${records.filter((r) => r.gram_cat && r.gram_cat !== 'ref').length}`);
console.log(`Referencias cruzadas (ref): ${records.filter((r) => r.gram_cat === 'ref').length}`);
if (skipped.length) console.log(`Fragmentos sin entrada previa: ${skipped.length}`);
console.log(`CSV -> ${outputPath}`);
