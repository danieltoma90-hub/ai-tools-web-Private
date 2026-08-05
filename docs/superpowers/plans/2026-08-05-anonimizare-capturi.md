# Tool „Anonimizare capturi" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Al 4-lea tool în ai-tools-web — anonimizează seturi de capturi de ecran (nume de firme/parteneri) integral în browser, cu detecție automată, confirmare editabilă și descărcare `.zip`.

**Architecture:** 100% client-side. `tesseract.js` (WASM) face OCR în browser; euristici TypeScript clasifică entitățile (firmă/persoană) și le grupează global pe tot setul; Canvas 2D acoperă textul cu fundalul eșantionat și rescrie înlocuitorul; `jszip` împachetează rezultatele. **Fără endpoint de backend, fără upload, fără storage.**

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind, `tesseract.js`, `jszip`, `vitest` (teste unitare — infrastructură nouă).

## Global Constraints

- **Zero backend**: nu se creează endpoint-uri, nu se modifică `backend/`, imaginile nu părăsesc browserul.
- **Zero cost**: fără AI, fără API plătit, fără tokeni de abonament.
- Assets tesseract (WASM + date de limbă) se descarcă de la CDN la prima utilizare și rămân în cache-ul browserului. **Abatere deliberată de la spec** (care cerea auto-găzduire): CDN e mai simplu, iar dacă rețeaua îl blochează spike-ul din Task 1 o arată imediat — atunci se comută pe auto-găzduire în `frontend/public/tesseract/`.
- Texte UI în **română cu diacritice**, în stilul paginilor existente (`ToolCard`, `ProcessingSpinner` refolosite).
- Nu se modifică `components/UploadZone.tsx` (îl folosesc celelalte 3 tool-uri, acceptă un singur fișier) — se creează componentă dedicată pentru multi-upload.
- Nume implicite: firmă → `TotalSoft`, persoană → `PartenerTest`. Dacă există **mai multe** entități de același tip, se numerotează de la 1 (`TotalSoft1`, `TotalSoft2`); dacă e una singură, **fără număr**.
- Sufixe firmă (doar cu MAJUSCULE în textul original): `S.R.L.`, `S.A.`, `SRL`, `SA`, `PFA`, `LTD`, `GMBH`, `SNC`, `SCS`.
- Termeni de interfață excluși de la „persoană": `ADMINISTRATOR, TOTALSOFT, TOTAL, MAIN, ORC, TVA, RON, TEST, PARTENER, NUME, CLIENT, DATA, PUNCT, LUCRU, NUMAR, SERIAL, VALOARE, REST, PLATA, SCADENTA, FACTURA, INTERN`.
- Text prea lung: micșorare **maxim 10%**, apoi trunchiere cu elipsă `…`.
- Comenzi: teste `npm test` din `frontend/`; build `npm run build` din `frontend/`.
- Commit după fiecare task, mesaje în stilul repo-ului (`feat:`, `fix:`, `test:`, `chore:`).
- NU se staghează `.env*`, `node_modules/`, `frontend/public/tesseract/*.traineddata*` (binare mari — vezi Task 5).

---

### Task 1: Spike de validare tesseract.js (poartă de decizie)

**Scop:** înainte de a construi interfața, măsurăm dacă tesseract.js găsește în browser aceleași nume pe care RapidOCR le-a găsit în testul Python. Rezultatul decide dacă detecția automată rămâne modul principal.

**Files:**
- Create: `frontend/scripts/spike-ocr.mjs`

**Interfaces:**
- Produces: raport în consolă + structura exactă a răspunsului tesseract.js (numele câmpurilor pentru cuvinte/linii), consemnată în raportul task-ului. Task 5 depinde de ea.

- [ ] **Step 1: Instalează tesseract.js**

```bash
cd frontend
npm install tesseract.js
```

- [ ] **Step 2: Scrie scriptul de spike**

Create `frontend/scripts/spike-ocr.mjs`:

```javascript
// Spike: verifica daca tesseract.js gaseste aceleasi nume ca RapidOCR (test Python).
// Baseline RapidOCR: poza 1 -> 5 aparitii tinta, poza 2 -> 3 aparitii tinta (total 8).
import { createWorker } from "tesseract.js";

const IMAGES = [
  "D:/AI_Claude/anonimizare/input/poza 1.png",
  "D:/AI_Claude/anonimizare/input/poza 2.png",
];
const TINTE = ["orchid", "agache", "eugen"];

const worker = await createWorker("ron");
let gasiteTotal = 0;

for (const img of IMAGES) {
  const t0 = Date.now();
  const ret = await worker.recognize(img, {}, { blocks: true });
  const dt = ((Date.now() - t0) / 1000).toFixed(1);

  // Structura raspunsului difera intre versiuni: incercam ambele forme.
  const data = ret.data;
  let words = data.words;
  if (!words || words.length === 0) {
    words = [];
    for (const b of data.blocks ?? []) {
      for (const p of b.paragraphs ?? []) {
        for (const l of p.lines ?? []) {
          for (const w of l.words ?? []) words.push(w);
        }
      }
    }
  }

  const hits = words.filter((w) =>
    TINTE.some((t) => (w.text || "").toLowerCase().includes(t))
  );
  gasiteTotal += hits.length;

  console.log(`\n=== ${img} (${dt}s, ${words.length} cuvinte) ===`);
  for (const w of hits) {
    const b = w.bbox || {};
    console.log(
      `  "${w.text}" conf=${Math.round(w.confidence)} box=(${b.x0},${b.y0},${b.x1},${b.y1})`
    );
  }
  if (words[0]) console.log("  [structura cuvant]:", JSON.stringify(words[0]).slice(0, 200));
}

await worker.terminate();
console.log(`\n>>> TOTAL aparitii tinta gasite: ${gasiteTotal} (baseline RapidOCR: 8)`);
console.log(gasiteTotal >= 6 ? ">>> PRAG TRECUT: continuam cu detectie automata" : ">>> SUB PRAG: modul principal devine selectia manuala");
```

- [ ] **Step 3: Rulează spike-ul**

Run: `node scripts/spike-ocr.mjs` (din `frontend/`)
Expected: listează aparițiile găsite pentru fiecare imagine și afișează totalul.
Notă: prima rulare descarcă datele de limbă (~15 MB) — poate dura 1-2 minute.

- [ ] **Step 4: Consemnează rezultatul în raport**

În raportul task-ului notează explicit:
1. **Câte apariții-țintă din 8** au fost găsite.
2. **Structura exactă** a obiectului cuvânt (unde stau `text`, `bbox`, `confidence`) — Task 5 o va folosi.
3. Timpul per imagine.
4. Verdictul: `≥6` → continuăm cu detecție automată; `<6` → se raportează utilizatorului ca **BLOCKED**, pentru decizie (marcare manuală ca mod principal).

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/spike-ocr.mjs frontend/package.json frontend/package-lock.json
git commit -m "chore: spike validare tesseract.js pe capturi reale"
```

---

### Task 2: Infrastructură de teste + tipuri + clasificator

**Files:**
- Create: `frontend/vitest.config.ts`, `frontend/lib/anonimizare/types.ts`, `frontend/lib/anonimizare/classify.ts`
- Test: `frontend/lib/anonimizare/classify.test.ts`
- Modify: `frontend/package.json` (script `test`)

**Interfaces:**
- Produces (Task 5/6/7 depind):
  - `type OcrWord = { text: string; box: [number, number, number, number]; conf: number; imageIndex: number }`
  - `type OcrLine = { text: string; words: OcrWord[]; imageIndex: number }`
  - `type EntityKind = "firma" | "persoana"`
  - `type Entity = { id: string; originalText: string; kind: EntityKind; replacement: string; enabled: boolean; manual: boolean; occurrences: OcrWord[] }`
  - `normalizeKey(text: string): string`
  - `detectInLine(line: OcrLine): { kind: EntityKind; words: OcrWord[] }[]`
  - `buildEntities(lines: OcrLine[]): Entity[]`
  - `unionBox(words: OcrWord[]): [number, number, number, number]`

- [ ] **Step 1: Instalează vitest și adaugă scriptul**

```bash
cd frontend
npm install -D vitest
```

În `frontend/package.json`, în `"scripts"`, adaugă după `"lint": "eslint"`:
```json
    "test": "vitest run"
```

Create `frontend/vitest.config.ts`:
```typescript
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: { environment: "node", include: ["lib/**/*.test.ts"] },
  resolve: { alias: { "@": path.resolve(__dirname, ".") } },
});
```

- [ ] **Step 2: Scrie testele (eșuează)**

Create `frontend/lib/anonimizare/classify.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { normalizeKey, detectInLine, buildEntities, unionBox } from "./classify";
import type { OcrLine, OcrWord } from "./types";

function w(text: string, x0 = 0, imageIndex = 0): OcrWord {
  return { text, box: [x0, 10, x0 + text.length * 8, 24], conf: 90, imageIndex };
}
function line(words: OcrWord[], imageIndex = 0): OcrLine {
  return { text: words.map((x) => x.text).join(" "), words, imageIndex };
}

describe("normalizeKey", () => {
  it("ignora spatiile, punctuatia si diacriticele de caz", () => {
    expect(normalizeKey("ORCHID S.R.L.")).toBe(normalizeKey("orchid srl"));
    expect(normalizeKey("AGACHE EUGEN")).toBe(normalizeKey("AGACHEEUGEN"));
  });
});

describe("detectInLine — firma", () => {
  it("gaseste firma dupa sufix cu majuscule", () => {
    const l = line([w("ORCHID", 0), w("S.R.L.", 60)]);
    const found = detectInLine(l);
    expect(found).toHaveLength(1);
    expect(found[0].kind).toBe("firma");
    expect(found[0].words.map((x) => x.text)).toEqual(["ORCHID", "S.R.L."]);
  });

  it("NU confunda cuvantul romanesc 'sa' cu sufixul S.A.", () => {
    const l = line([w("total", 0), w("sau", 40), w("partial,", 80), w("sa", 130), w("anexati", 160)]);
    expect(detectInLine(l)).toHaveLength(0);
  });

  it("gaseste firma si cand eticheta e in aceeasi linie", () => {
    const l = line([w("Localitate:", 0), w("ORCHID", 90), w("S.R.L.", 150)]);
    const found = detectInLine(l);
    expect(found).toHaveLength(1);
    expect(found[0].words.map((x) => x.text)).toEqual(["ORCHID", "S.R.L."]);
  });
});

describe("detectInLine — persoana", () => {
  it("gaseste nume lipit, fara spatiu (asa cum da OCR-ul)", () => {
    const found = detectInLine(line([w("AGACHEEUGEN", 0)]));
    expect(found).toHaveLength(1);
    expect(found[0].kind).toBe("persoana");
  });

  it("gaseste doua cuvinte consecutive cu majuscule", () => {
    const found = detectInLine(line([w("ION", 0), w("POPESCU", 40)]));
    expect(found).toHaveLength(1);
    expect(found[0].words.map((x) => x.text)).toEqual(["ION", "POPESCU"]);
  });

  it("exclude termenii de interfata", () => {
    expect(detectInLine(line([w("ADMINISTRATOR", 0)]))).toHaveLength(0);
    expect(detectInLine(line([w("DATA", 0), w("FACTURA", 40)]))).toHaveLength(0);
  });

  it("ignora cuvintele scurte", () => {
    expect(detectInLine(line([w("LS", 0)]))).toHaveLength(0);
  });
});

describe("buildEntities", () => {
  it("grupeaza aceeasi entitate din imagini diferite", () => {
    const lines = [
      line([w("ORCHID", 0), w("S.R.L.", 60)], 0),
      line([w("ORCHID", 0), w("S.R.L.", 60)], 1),
    ];
    const ents = buildEntities(lines);
    expect(ents).toHaveLength(1);
    expect(ents[0].occurrences).toHaveLength(2);
    expect(ents[0].replacement).toBe("TotalSoft");
  });

  it("numeroteaza doar cand exista mai multe entitati de acelasi tip", () => {
    const ents = buildEntities([
      line([w("AGACHEEUGEN", 0)], 0),
      line([w("ION", 0), w("POPESCU", 40)], 0),
    ]);
    expect(ents).toHaveLength(2);
    expect(ents.map((e) => e.replacement).sort()).toEqual(["PartenerTest1", "PartenerTest2"]);
  });

  it("entitatile pornesc bifate si ne-manuale", () => {
    const ents = buildEntities([line([w("ORCHID", 0), w("S.R.L.", 60)], 0)]);
    expect(ents[0].enabled).toBe(true);
    expect(ents[0].manual).toBe(false);
  });
});

describe("unionBox", () => {
  it("reuneste casetele mai multor cuvinte", () => {
    expect(unionBox([w("AB", 10), w("CD", 50)])).toEqual([10, 10, 66, 24]);
  });
});
```

- [ ] **Step 3: Rulează testele — trebuie să eșueze**

Run: `npm test` (din `frontend/`)
Expected: FAIL — `Cannot find module './classify'`

- [ ] **Step 4: Creează tipurile**

Create `frontend/lib/anonimizare/types.ts`:

```typescript
export type Box = [number, number, number, number]; // x0, y0, x1, y1

export type OcrWord = {
  text: string;
  box: Box;
  conf: number;
  imageIndex: number;
};

export type OcrLine = {
  text: string;
  words: OcrWord[];
  imageIndex: number;
};

export type EntityKind = "firma" | "persoana";

export type Entity = {
  id: string;
  originalText: string;
  kind: EntityKind;
  replacement: string;
  enabled: boolean;
  manual: boolean;
  occurrences: OcrWord[];
};
```

- [ ] **Step 5: Implementează clasificatorul**

Create `frontend/lib/anonimizare/classify.ts`:

```typescript
import type { Box, Entity, EntityKind, OcrLine, OcrWord } from "./types";

/** Sufixe juridice — se acceptă DOAR cu majuscule în textul original,
 *  altfel cuvântul românesc „sa" ar fi luat drept „S.A." (fals pozitiv real, prins la test). */
const SUFIX_FIRMA = /^(S\.?R\.?L|S\.?A|SRL|SA|PFA|LTD|GMBH|SNC|SCS)\.?[,.]?$/;

const TERMENI_UI = new Set([
  "ADMINISTRATOR", "TOTALSOFT", "TOTAL", "MAIN", "ORC", "TVA", "RON", "TEST",
  "PARTENER", "NUME", "CLIENT", "DATA", "PUNCT", "LUCRU", "NUMAR", "SERIAL",
  "VALOARE", "REST", "PLATA", "SCADENTA", "FACTURA", "INTERN",
]);

const NUME_IMPLICIT: Record<EntityKind, string> = {
  firma: "TotalSoft",
  persoana: "PartenerTest",
};

export function normalizeKey(text: string): string {
  return text.toUpperCase().replace(/[^A-Z0-9ĂÂÎȘȚ]/g, "");
}

function esteMajuscule(t: string): boolean {
  const litere = t.replace(/[^A-Za-zĂÂÎȘȚăâîșț]/g, "");
  return litere.length >= 4 && litere === litere.toUpperCase();
}

function esteCapitalizat(t: string): boolean {
  return /^[A-ZĂÂÎȘȚ]/.test(t);
}

export function unionBox(words: OcrWord[]): Box {
  return [
    Math.min(...words.map((w) => w.box[0])),
    Math.min(...words.map((w) => w.box[1])),
    Math.max(...words.map((w) => w.box[2])),
    Math.max(...words.map((w) => w.box[3])),
  ];
}

/** Găsește entitățile dintr-o linie OCR, la nivel de cuvinte consecutive. */
export function detectInLine(line: OcrLine): { kind: EntityKind; words: OcrWord[] }[] {
  const out: { kind: EntityKind; words: OcrWord[] }[] = [];
  const ws = line.words;
  const consumat = new Set<number>();

  // 1) Firmă: cuvânt capitalizat urmat de sufix juridic cu majuscule.
  for (let i = 1; i < ws.length; i++) {
    if (!SUFIX_FIRMA.test(ws[i].text)) continue;
    if (ws[i].text !== ws[i].text.toUpperCase()) continue; // „sa" minuscul → nu e sufix
    if (!esteCapitalizat(ws[i - 1].text)) continue;
    out.push({ kind: "firma", words: [ws[i - 1], ws[i]] });
    consumat.add(i - 1);
    consumat.add(i);
  }

  // 2) Persoană: rulaje de cuvinte cu MAJUSCULE, ≥8 litere în total.
  let run: number[] = [];
  const inchideRun = () => {
    if (run.length) {
      const cuvinte = run.map((k) => ws[k]);
      const litere = cuvinte.map((c) => c.text.replace(/[^A-Za-zĂÂÎȘȚăâîșț]/g, "")).join("");
      if (litere.length >= 8) out.push({ kind: "persoana", words: cuvinte });
    }
    run = [];
  };
  for (let i = 0; i < ws.length; i++) {
    const t = ws[i].text.replace(/[^A-Za-zĂÂÎȘȚăâîșț]/g, "").toUpperCase();
    const ok = !consumat.has(i) && esteMajuscule(ws[i].text) && !TERMENI_UI.has(t);
    if (ok) run.push(i);
    else inchideRun();
  }
  inchideRun();

  return out;
}

/** Construiește entitățile globale: grupare pe text normalizat + numerotare. */
export function buildEntities(lines: OcrLine[]): Entity[] {
  const grupe = new Map<string, { kind: EntityKind; text: string; occ: OcrWord[] }>();

  for (const line of lines) {
    for (const { kind, words } of detectInLine(line)) {
      const text = words.map((w) => w.text).join(" ");
      const key = normalizeKey(text);
      const g = grupe.get(key);
      if (g) g.occ.push(...words);
      else grupe.set(key, { kind, text, occ: [...words] });
    }
  }

  const entities: Entity[] = [];
  for (const [key, g] of grupe) {
    entities.push({
      id: key,
      originalText: g.text,
      kind: g.kind,
      replacement: "",
      enabled: true,
      manual: false,
      occurrences: g.occ,
    });
  }
  return numeroteaza(entities);
}

/** Numerotează doar când există mai multe entități de același tip. */
export function numeroteaza(entities: Entity[]): Entity[] {
  for (const kind of ["firma", "persoana"] as EntityKind[]) {
    const dinTip = entities.filter((e) => e.kind === kind);
    dinTip.forEach((e, i) => {
      if (e.replacement && e.manual) return; // păstrează ce a scris utilizatorul
      e.replacement = dinTip.length === 1 ? NUME_IMPLICIT[kind] : `${NUME_IMPLICIT[kind]}${i + 1}`;
    });
  }
  return entities;
}
```

- [ ] **Step 6: Rulează testele — trebuie să treacă**

Run: `npm test`
Expected: toate testele din `classify.test.ts` PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/vitest.config.ts frontend/package.json frontend/package-lock.json frontend/lib/anonimizare/
git commit -m "feat: clasificator entitati (firma/persoana) + infrastructura vitest"
```

---

### Task 3: Potrivirea textului în casetă (mărime + elipsă)

**Files:**
- Create: `frontend/lib/anonimizare/fit.ts`
- Test: `frontend/lib/anonimizare/fit.test.ts`

**Interfaces:**
- Produces (Task 4 depinde): `fitText(text: string, boxWidth: number, boxHeight: number, measure: (t: string, size: number) => number): { text: string; size: number }`
  - `measure` e injectat (în browser va fi `ctx.measureText`) — face funcția testabilă fără Canvas.

- [ ] **Step 1: Scrie testele (eșuează)**

Create `frontend/lib/anonimizare/fit.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { fitText } from "./fit";

// măsurare simulată: fiecare caracter are lățimea = 0,5 × mărimea fontului
const measure = (t: string, size: number) => t.length * size * 0.5;

describe("fitText", () => {
  it("pastreaza textul si marimea cand incape", () => {
    const r = fitText("ABC", 200, 14, measure);
    expect(r.text).toBe("ABC");
    expect(r.size).toBeCloseTo(14 * 1.35, 1);
  });

  it("micsoreaza usor fontul cand depaseste putin", () => {
    // 13 caractere la marime 18,9 => 122,8px; caseta 118px => trebuie micsorat
    const r = fitText("PartenerTest1", 118, 14, measure);
    expect(r.text).toBe("PartenerTest1");
    expect(r.size).toBeLessThan(14 * 1.35);
    expect(r.size).toBeGreaterThanOrEqual(14 * 1.35 * 0.9); // nu sub 90%
  });

  it("trunchiaza cu elipsa cand nu incape nici la 90%", () => {
    const r = fitText("PartenerTest1", 40, 14, measure);
    expect(r.text.endsWith("…")).toBe(true);
    expect(r.text.length).toBeLessThan("PartenerTest1".length);
    expect(r.size).toBeCloseTo(14 * 1.35 * 0.9, 1); // s-a oprit la limita de lizibilitate
  });

  it("nu coboara niciodata sub 90% din marimea initiala", () => {
    const r = fitText("text foarte foarte lung care nu incape nicicum", 30, 14, measure);
    expect(r.size).toBeGreaterThanOrEqual(14 * 1.35 * 0.9 - 0.01);
  });

  it("returneaza cel putin un caracter plus elipsa", () => {
    const r = fitText("ABCDEF", 1, 14, measure);
    expect(r.text.length).toBeGreaterThanOrEqual(2);
  });
});
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `npm test`
Expected: FAIL — `Cannot find module './fit'`

- [ ] **Step 3: Implementează**

Create `frontend/lib/anonimizare/fit.ts`:

```typescript
/** Raport între înălțimea casetei și mărimea fontului (empiric, potrivit vizual). */
const RAPORT_MARIME = 1.35;
/** Nu micșorăm sub 90% — sub asta textul devine greu lizibil; preferăm trunchierea. */
const MICSORARE_MINIMA = 0.9;
const PAS = 0.5;
const MARJA_PX = 4;

export type Masura = (text: string, size: number) => number;

/**
 * Potrivește textul în casetă: întâi micșorare ușoară, apoi trunchiere cu elipsă.
 * Prioritatea este lizibilitatea — nu micșorăm textul până devine ilizibil.
 */
export function fitText(
  text: string,
  boxWidth: number,
  boxHeight: number,
  measure: Masura
): { text: string; size: number } {
  const marimeInitiala = boxHeight * RAPORT_MARIME;
  const limita = boxWidth + MARJA_PX;
  const marimeMinima = marimeInitiala * MICSORARE_MINIMA;

  let size = marimeInitiala;
  while (measure(text, size) > limita && size - PAS >= marimeMinima) {
    size -= PAS;
  }
  if (measure(text, size) <= limita) return { text, size };

  // Tot nu încape la mărimea minimă acceptată → trunchiem.
  size = marimeMinima;
  let taiat = text;
  while (taiat.length > 1 && measure(taiat + "…", size) > limita) {
    taiat = taiat.slice(0, -1);
  }
  return { text: taiat + "…", size };
}
```

- [ ] **Step 4: Rulează — trebuie să treacă**

Run: `npm test`
Expected: toate testele PASS (classify + fit)

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/anonimizare/fit.ts frontend/lib/anonimizare/fit.test.ts
git commit -m "feat: potrivire text in caseta cu elipsa (prioritate lizibilitate)"
```

---

### Task 4: Redactarea pe Canvas

**Files:**
- Create: `frontend/lib/anonimizare/redact.ts`
- Test: `frontend/lib/anonimizare/redact.test.ts` (doar funcțiile pure de culoare)

**Interfaces:**
- Consumes: `fitText` (Task 3), tipurile din `types.ts` (Task 2).
- Produces (Task 8 depinde):
  - `medianColor(data: Uint8ClampedArray): [number, number, number]`
  - `type Edit = { box: Box; text: string }`
  - `redactImage(img: HTMLImageElement, edits: Edit[]): Promise<Blob>`

- [ ] **Step 1: Scrie testele pentru funcțiile pure (eșuează)**

Create `frontend/lib/anonimizare/redact.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { medianColor, densitateCerneala } from "./redact";

/** construiește un buffer RGBA din culori repetate */
function buf(colors: [number, number, number][]): Uint8ClampedArray {
  const a = new Uint8ClampedArray(colors.length * 4);
  colors.forEach((c, i) => {
    a[i * 4] = c[0]; a[i * 4 + 1] = c[1]; a[i * 4 + 2] = c[2]; a[i * 4 + 3] = 255;
  });
  return a;
}

describe("medianColor", () => {
  it("intoarce culoarea dominanta ignorand valorile extreme", () => {
    const c = medianColor(buf([[255, 255, 255], [255, 255, 255], [255, 255, 255], [0, 0, 0]]));
    expect(c).toEqual([255, 255, 255]);
  });

  it("functioneaza pe gradient (bara de status)", () => {
    const c = medianColor(buf([[200, 220, 240], [204, 224, 244], [208, 228, 248]]));
    expect(c[0]).toBeGreaterThanOrEqual(200);
    expect(c[0]).toBeLessThanOrEqual(208);
  });
});

describe("densitateCerneala", () => {
  it("zero pe fundal curat", () => {
    expect(densitateCerneala(buf([[255, 255, 255], [255, 255, 255]]))).toBe(0);
  });

  it("detecteaza text ingrosat (peste 22%)", () => {
    const pixeli: [number, number, number][] = [];
    for (let i = 0; i < 10; i++) pixeli.push(i < 3 ? [20, 20, 20] : [255, 255, 255]);
    expect(densitateCerneala(buf(pixeli))).toBeGreaterThan(0.22);
  });
});
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `npm test`
Expected: FAIL — `Cannot find module './redact'`

- [ ] **Step 3: Implementează**

Create `frontend/lib/anonimizare/redact.ts`:

```typescript
import type { Box } from "./types";
import { fitText } from "./fit";

export type Edit = { box: Box; text: string };

const PRAG_INTUNECAT = 384; // suma R+G+B sub care pixelul e considerat „cerneală"
const PRAG_BOLD = 0.22;
const BANDA_FUNDAL = 4; // px deasupra casetei, pentru eșantionarea fundalului
const PADDING = 2;

/** Mediana pe canal — robustă la pixeli izolați (antialiasing, gradient). */
export function medianColor(data: Uint8ClampedArray): [number, number, number] {
  const canale: number[][] = [[], [], []];
  for (let i = 0; i < data.length; i += 4) {
    canale[0].push(data[i]);
    canale[1].push(data[i + 1]);
    canale[2].push(data[i + 2]);
  }
  const med = (a: number[]) => {
    if (!a.length) return 255;
    const s = [...a].sort((x, y) => x - y);
    return s[Math.floor(s.length / 2)];
  };
  return [med(canale[0]), med(canale[1]), med(canale[2])];
}

/** Proporția pixelilor întunecați — folosită ca indiciu de text îngroșat. */
export function densitateCerneala(data: Uint8ClampedArray): number {
  let total = 0;
  let intunecati = 0;
  for (let i = 0; i < data.length; i += 4) {
    total++;
    if (data[i] + data[i + 1] + data[i + 2] < PRAG_INTUNECAT) intunecati++;
  }
  return total ? intunecati / total : 0;
}

/** Culoarea cernelii = mediana pixelilor întunecați din casetă. */
function culoareCerneala(data: Uint8ClampedArray): [number, number, number] {
  const dark: number[] = [];
  for (let i = 0; i < data.length; i += 4) {
    if (data[i] + data[i + 1] + data[i + 2] < PRAG_INTUNECAT) {
      dark.push(data[i], data[i + 1], data[i + 2], 255);
    }
  }
  return dark.length ? medianColor(new Uint8ClampedArray(dark)) : [60, 55, 70];
}

const rgb = (c: [number, number, number]) => `rgb(${c[0]},${c[1]},${c[2]})`;

/** Acoperă fiecare casetă cu fundalul local și rescrie textul înlocuitor. */
export function redactImage(img: HTMLImageElement, edits: Edit[]): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(img, 0, 0);

  for (const { box, text } of edits) {
    const [x0, y0, x1, y1] = box;
    const w = Math.max(1, x1 - x0);
    const h = Math.max(1, y1 - y0);

    const inCaseta = ctx.getImageData(x0, y0, w, h).data;
    const cerneala = culoareCerneala(inCaseta);
    const bold = densitateCerneala(inCaseta) > PRAG_BOLD;

    const sus = Math.max(0, y0 - BANDA_FUNDAL);
    const fundal = medianColor(ctx.getImageData(x0, sus, w, Math.max(1, y0 - sus)).data);

    ctx.fillStyle = rgb(fundal);
    ctx.fillRect(x0 - PADDING, y0 - PADDING, w + PADDING * 2, h + PADDING * 2);

    const familie = `${bold ? "bold " : ""}%SIZE%px Arial, Helvetica, sans-serif`;
    const measure = (t: string, size: number) => {
      ctx.font = familie.replace("%SIZE%", String(size));
      return ctx.measureText(t).width;
    };
    const potrivit = fitText(text, w, h, measure);

    ctx.font = familie.replace("%SIZE%", String(potrivit.size));
    ctx.fillStyle = rgb(cerneala);
    ctx.textBaseline = "bottom";
    ctx.fillText(potrivit.text, x0, y1);
  }

  return new Promise((resolve) =>
    canvas.toBlob((b) => resolve(b!), "image/png")
  );
}
```

- [ ] **Step 4: Rulează — trebuie să treacă**

Run: `npm test`
Expected: toate testele PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/anonimizare/redact.ts frontend/lib/anonimizare/redact.test.ts
git commit -m "feat: redactare pe canvas cu esantionare fundal si cerneala"
```

---

### Task 5: Wrapper OCR (tesseract.js în browser)

**Files:**
- Create: `frontend/lib/anonimizare/ocr.ts`
- Modify: `frontend/.gitignore` (exclude fișierele de limbă descărcate)

**Interfaces:**
- Consumes: tipurile din `types.ts`; structura răspunsului confirmată în Task 1.
- Produces (Task 6 depinde): `recognizeImages(files: File[], onProgress: (done: number, total: number) => void): Promise<OcrLine[]>`

- [ ] **Step 1: Implementează wrapper-ul**

Create `frontend/lib/anonimizare/ocr.ts`:

```typescript
import { createWorker } from "tesseract.js";
import type { OcrLine, OcrWord } from "./types";

/** Extrage cuvintele din răspunsul tesseract (structura variază între versiuni). */
function extrageLinii(data: any, imageIndex: number): OcrLine[] {
  const linii: OcrLine[] = [];

  const adauga = (words: any[]) => {
    const w: OcrWord[] = words
      .filter((x) => (x.text || "").trim().length > 0)
      .map((x) => ({
        text: String(x.text).trim(),
        box: [x.bbox.x0, x.bbox.y0, x.bbox.x1, x.bbox.y1] as OcrWord["box"],
        conf: x.confidence ?? 0,
        imageIndex,
      }));
    if (w.length) linii.push({ text: w.map((x) => x.text).join(" "), words: w, imageIndex });
  };

  if (Array.isArray(data.lines) && data.lines.length) {
    for (const l of data.lines) adauga(l.words ?? []);
    return linii;
  }
  for (const b of data.blocks ?? []) {
    for (const p of b.paragraphs ?? []) {
      for (const l of p.lines ?? []) adauga(l.words ?? []);
    }
  }
  return linii;
}

/** Rulează OCR pe toate imaginile, în browser. Nimic nu se trimite pe server. */
export async function recognizeImages(
  files: File[],
  onProgress: (done: number, total: number) => void
): Promise<OcrLine[]> {
  const worker = await createWorker("ron");
  const toate: OcrLine[] = [];
  try {
    for (let i = 0; i < files.length; i++) {
      const ret = await worker.recognize(files[i], {}, { blocks: true });
      toate.push(...extrageLinii(ret.data, i));
      onProgress(i + 1, files.length);
    }
  } finally {
    await worker.terminate();
  }
  return toate;
}
```

- [ ] **Step 2: Exclude fișierele de limbă din git**

Datele de limbă se descarcă la runtime; dacă ajung vreodată în arborele proiectului (rulare de script local), nu trebuie comise. În `frontend/.gitignore`, adaugă la final:
```
# date de limba tesseract.js (se descarca la runtime, ~15 MB)
*.traineddata
*.traineddata.gz
```

- [ ] **Step 3: Verifică build-ul**

Run: `npm run build` (din `frontend/`)
Expected: build reușit, zero erori TypeScript

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/anonimizare/ocr.ts frontend/.gitignore
git commit -m "feat: wrapper OCR tesseract.js pentru browser"
```

---

### Task 6: Pagina tool-ului + tabelul de reguli

**Files:**
- Create: `frontend/components/anonimizare/MultiUploadZone.tsx`, `frontend/components/anonimizare/RulesTable.tsx`, `frontend/app/(app)/anonimizare/page.tsx`

**Interfaces:**
- Consumes: `recognizeImages` (Task 5), `buildEntities`/`numeroteaza` (Task 2).
- Produces (Task 7/8 depind): starea paginii (`Entity[]`, `File[]`), componentele de mai sus.

- [ ] **Step 1: Componenta de încărcare multiplă**

Create `frontend/components/anonimizare/MultiUploadZone.tsx`:

```tsx
"use client";
import { useRef, useState } from "react";

type Props = { onFiles: (files: File[]) => void };

export default function MultiUploadZone({ onFiles }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  function preia(list: FileList | null) {
    if (!list) return;
    const imagini = Array.from(list).filter((f) => f.type.startsWith("image/"));
    if (imagini.length) onFiles(imagini);
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); preia(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
      className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
        dragOver ? "border-[#18257f] bg-[#f1f3f8]" : "border-[#d6d9e2] hover:border-[#18257f]"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg"
        multiple
        className="hidden"
        onChange={(e) => preia(e.target.files)}
      />
      <p className="text-3xl mb-2">🖼️</p>
      <p className="text-sm font-semibold text-[#1e3a5f]">
        Trage capturile aici sau dă clic pentru a le alege
      </p>
      <p className="text-xs text-slate-400 mt-1">
        .png sau .jpg — oricâte deodată. Imaginile rămân în calculatorul tău.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Tabelul de reguli**

Create `frontend/components/anonimizare/RulesTable.tsx`:

```tsx
"use client";
import type { Entity } from "@/lib/anonimizare/types";

type Props = {
  entities: Entity[];
  onChange: (entities: Entity[]) => void;
};

export default function RulesTable({ entities, onChange }: Props) {
  function actualizeaza(id: string, patch: Partial<Entity>) {
    onChange(entities.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }

  if (!entities.length) {
    return (
      <p className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-4">
        Nu am găsit automat nume de firme sau persoane. Poți selecta manual zonele
        de anonimizat direct pe imagini, mai jos.
      </p>
    );
  }

  return (
    <div className="overflow-auto border border-[#e2e5f0] rounded-xl">
      <table className="w-full text-sm">
        <thead className="bg-[#f1f3f8] text-[#18257f]">
          <tr>
            <th className="px-3 py-2 text-left w-10"></th>
            <th className="px-3 py-2 text-left">Găsit în capturi</th>
            <th className="px-3 py-2 text-left w-28">Tip</th>
            <th className="px-3 py-2 text-left w-56">Înlocuiește cu</th>
            <th className="px-3 py-2 text-right w-24">Apariții</th>
          </tr>
        </thead>
        <tbody>
          {entities.map((e) => (
            <tr key={e.id} className={`border-t border-[#eef0f8] ${e.enabled ? "" : "opacity-45"}`}>
              <td className="px-3 py-2">
                <input
                  type="checkbox"
                  checked={e.enabled}
                  onChange={(ev) => actualizeaza(e.id, { enabled: ev.target.checked })}
                  className="w-4 h-4 accent-[#18257f]"
                />
              </td>
              <td className="px-3 py-2 font-medium text-slate-700">
                {e.originalText}
                {e.manual && (
                  <span className="ml-2 text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">
                    manual
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-slate-500">
                {e.kind === "firma" ? "Firmă" : "Persoană"}
              </td>
              <td className="px-3 py-2">
                <input
                  type="text"
                  value={e.replacement}
                  onChange={(ev) => actualizeaza(e.id, { replacement: ev.target.value, manual: true })}
                  className="w-full border border-[#d6d9e2] rounded-lg px-2 py-1 text-sm focus:outline-none focus:border-[#18257f]"
                />
              </td>
              <td className="px-3 py-2 text-right text-slate-500">{e.occurrences.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Pagina (stările idle → scanning → review)**

Create `frontend/app/(app)/anonimizare/page.tsx`:

```tsx
"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import MultiUploadZone from "@/components/anonimizare/MultiUploadZone";
import RulesTable from "@/components/anonimizare/RulesTable";
import { recognizeImages } from "@/lib/anonimizare/ocr";
import { buildEntities } from "@/lib/anonimizare/classify";
import type { Entity, OcrLine } from "@/lib/anonimizare/types";

type State = "idle" | "scanning" | "review" | "applying" | "done" | "error";

export default function AnonimizarePage() {
  const [state, setState] = useState<State>("idle");
  const [files, setFiles] = useState<File[]>([]);
  const [lines, setLines] = useState<OcrLine[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [progres, setProgres] = useState("");
  const [error, setError] = useState("");

  async function porneste(fisiere: File[]) {
    setFiles(fisiere);
    setState("scanning");
    setError("");
    setProgres(`Pregătesc analiza pentru ${fisiere.length} capturi...`);
    try {
      const l = await recognizeImages(fisiere, (done, total) =>
        setProgres(`Analizez captura ${done} din ${total}...`)
      );
      setLines(l);
      setEntities(buildEntities(l));
      setState("review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eroare la analiza imaginilor");
      setState("error");
    }
  }

  function reseteaza() {
    setFiles([]); setLines([]); setEntities([]); setState("idle"); setError("");
  }

  return (
    <div className="p-6 max-w-5xl">
      <ToolCard
        icon="🕶️"
        title="Anonimizare capturi"
        description="Ascunde numele de firme și parteneri din capturi de ecran — totul în browser"
      />

      {state === "idle" && (
        <div className="flex flex-col gap-3">
          <MultiUploadZone onFiles={porneste} />
          <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
            Confidențial: imaginile sunt analizate local, în browserul tău. Nu se
            încarcă pe server și nu se salvează nicăieri.
          </p>
        </div>
      )}

      {state === "scanning" && <ProcessingSpinner label={progres} />}

      {state === "review" && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-slate-600">
            Am analizat {files.length} capturi. Verifică propunerile, editează
            înlocuitorii dacă e nevoie și debifează ce nu vrei să fie schimbat.
          </p>
          <RulesTable entities={entities} onChange={setEntities} />
          <button onClick={reseteaza} className="text-sm text-blue-600 underline self-start">
            Începe cu alt set
          </button>
        </div>
      )}

      {state === "error" && (
        <div className="flex flex-col gap-3">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            {error}
          </div>
          <button onClick={reseteaza} className="text-sm text-blue-600 underline self-start">
            Încearcă din nou
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verifică build-ul**

Run: `npm run build`
Expected: build reușit; ruta `/anonimizare` apare în lista de pagini

- [ ] **Step 5: Commit**

```bash
git add frontend/components/anonimizare/ "frontend/app/(app)/anonimizare/"
git commit -m "feat: pagina Anonimizare cu incarcare multipla si tabel de reguli"
```

---

### Task 7: Selecție manuală inteligentă

**Files:**
- Create: `frontend/lib/anonimizare/selection.ts`, `frontend/components/anonimizare/ImageSelector.tsx`
- Test: `frontend/lib/anonimizare/selection.test.ts`
- Modify: `frontend/app/(app)/anonimizare/page.tsx` (afișează selectorul în starea `review`)

**Interfaces:**
- Consumes: `unionBox`, `detectInLine`, `normalizeKey`, `numeroteaza` (Task 2).
- Produces: `wordsInSelection(words: OcrWord[], sel: Box, minOverlap?: number): OcrWord[]`; `entityFromSelection(words: OcrWord[], sel: Box, imageIndex: number): Entity`; `propagateEntity(entity: Entity, lines: OcrLine[]): Entity` (adaugă aparițiile aceluiași text din celelalte imagini)

- [ ] **Step 1: Scrie testele (eșuează)**

Create `frontend/lib/anonimizare/selection.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { wordsInSelection, entityFromSelection, propagateEntity } from "./selection";
import type { OcrWord } from "./types";

const w = (text: string, box: [number, number, number, number]): OcrWord => ({
  text, box, conf: 90, imageIndex: 0,
});

describe("wordsInSelection", () => {
  const cuvinte = [w("ORCHID", [10, 10, 90, 26]), w("S.R.L.", [95, 10, 150, 26]), w("altceva", [400, 200, 480, 216])];

  it("ia cuvintele acoperite de selectie", () => {
    const r = wordsInSelection(cuvinte, [5, 5, 160, 30]);
    expect(r.map((x) => x.text)).toEqual(["ORCHID", "S.R.L."]);
  });

  it("ignora cuvintele care se suprapun sub 50%", () => {
    const r = wordsInSelection(cuvinte, [5, 5, 30, 30]); // acopera ~25% din ORCHID
    expect(r).toHaveLength(0);
  });

  it("intoarce lista goala cand selectia e pe zona fara text", () => {
    expect(wordsInSelection(cuvinte, [600, 600, 700, 650])).toHaveLength(0);
  });
});

describe("entityFromSelection", () => {
  const cuvinte = [w("ORCHID", [10, 10, 90, 26]), w("S.R.L.", [95, 10, 150, 26])];

  it("reconstituie textul in ordinea de citire si clasifica", () => {
    const e = entityFromSelection(cuvinte, [5, 5, 160, 30], 0);
    expect(e.originalText).toBe("ORCHID S.R.L.");
    expect(e.kind).toBe("firma");
    expect(e.manual).toBe(true);
    expect(e.enabled).toBe(true);
    expect(e.occurrences).toHaveLength(2);
  });

  it("cand OCR nu a gasit nimic, marcheaza (nedetectat) si pastreaza caseta", () => {
    const e = entityFromSelection(cuvinte, [600, 600, 700, 650], 0);
    expect(e.originalText).toBe("(nedetectat)");
    expect(e.occurrences).toHaveLength(1);
    expect(e.occurrences[0].box).toEqual([600, 600, 700, 650]);
  });
});

describe("propagateEntity", () => {
  const cuvinte = [w("ORCHID", [10, 10, 90, 26]), w("S.R.L.", [95, 10, 150, 26])];

  it("adauga aparitiile aceluiasi text din celelalte imagini", () => {
    const e = entityFromSelection(cuvinte, [5, 5, 160, 30], 0);
    const inAltaImagine: OcrWord[] = [
      { text: "ORCHID", box: [10, 40, 90, 56], conf: 90, imageIndex: 1 },
      { text: "S.R.L.", box: [95, 40, 150, 56], conf: 90, imageIndex: 1 },
    ];
    const lines = [
      { text: "ORCHID S.R.L.", words: cuvinte, imageIndex: 0 },
      { text: "ORCHID S.R.L.", words: inAltaImagine, imageIndex: 1 },
    ];
    const propagata = propagateEntity(e, lines);
    expect(propagata.occurrences).toHaveLength(4);
    expect(propagata.occurrences.some((o) => o.imageIndex === 1)).toBe(true);
  });

  it("nu dubleaza aparitiile deja existente", () => {
    const e = entityFromSelection(cuvinte, [5, 5, 160, 30], 0);
    const lines = [{ text: "ORCHID S.R.L.", words: cuvinte, imageIndex: 0 }];
    expect(propagateEntity(e, lines).occurrences).toHaveLength(2);
  });

  it("nu propaga entitatile (nedetectat)", () => {
    const e = entityFromSelection(cuvinte, [600, 600, 700, 650], 0);
    const lines = [{ text: "ORCHID S.R.L.", words: cuvinte, imageIndex: 0 }];
    expect(propagateEntity(e, lines).occurrences).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Rulează — trebuie să eșueze**

Run: `npm test`
Expected: FAIL — `Cannot find module './selection'`

- [ ] **Step 3: Implementează**

Create `frontend/lib/anonimizare/selection.ts`:

```typescript
import type { Box, Entity, OcrLine, OcrWord } from "./types";
import { detectInLine, normalizeKey } from "./classify";

/** Proporția din caseta cuvântului acoperită de selecție. */
function acoperire(word: Box, sel: Box): number {
  const latime = Math.max(0, Math.min(word[2], sel[2]) - Math.max(word[0], sel[0]));
  const inaltime = Math.max(0, Math.min(word[3], sel[3]) - Math.max(word[1], sel[1]));
  const arieCuvant = Math.max(1, (word[2] - word[0]) * (word[3] - word[1]));
  return (latime * inaltime) / arieCuvant;
}

/** Cuvintele acoperite de selecție cel puțin `minOverlap`, în ordine de citire. */
export function wordsInSelection(words: OcrWord[], sel: Box, minOverlap = 0.5): OcrWord[] {
  return words
    .filter((w) => acoperire(w.box, sel) >= minOverlap)
    .sort((a, b) => (Math.abs(a.box[1] - b.box[1]) > 6 ? a.box[1] - b.box[1] : a.box[0] - b.box[0]));
}

/**
 * Creează o entitate dintr-o selecție: reconstituie textul, îl clasifică și
 * propune un înlocuitor. Dacă OCR nu a găsit nimic acolo, caseta desenată
 * devine singura apariție, iar textul rămâne „(nedetectat)".
 */
export function entityFromSelection(words: OcrWord[], sel: Box, imageIndex: number): Entity {
  const gasite = wordsInSelection(words, sel);

  if (!gasite.length) {
    return {
      id: `manual-${sel.join("-")}`,
      originalText: "(nedetectat)",
      kind: "persoana",
      replacement: "",
      enabled: true,
      manual: true,
      occurrences: [{ text: "", box: sel, conf: 0, imageIndex }],
    };
  }

  const text = gasite.map((w) => w.text).join(" ");
  const detectat = detectInLine({ text, words: gasite, imageIndex });
  return {
    id: normalizeKey(text) || `manual-${sel.join("-")}`,
    originalText: text,
    kind: detectat[0]?.kind ?? "persoana",
    replacement: "",
    enabled: true,
    manual: true,
    occurrences: gasite,
  };
}

/**
 * Propagă entitatea în tot setul: caută în toate imaginile aceeași secvență de
 * cuvinte și o adaugă la apariții. Astfel, o zonă marcată manual într-o captură
 * se anonimizează automat și în celelalte capturi identice.
 */
export function propagateEntity(entity: Entity, lines: OcrLine[]): Entity {
  if (entity.originalText === "(nedetectat)") return entity;

  const cheie = normalizeKey(entity.originalText);
  const nrCuvinte = entity.occurrences.length;
  const existente = new Set(entity.occurrences.map((o) => `${o.imageIndex}:${o.box.join(",")}`));
  const gasite: OcrWord[] = [];

  for (const line of lines) {
    for (let i = 0; i + nrCuvinte <= line.words.length; i++) {
      const secventa = line.words.slice(i, i + nrCuvinte);
      if (normalizeKey(secventa.map((w) => w.text).join(" ")) !== cheie) continue;
      for (const w of secventa) {
        const id = `${w.imageIndex}:${w.box.join(",")}`;
        if (!existente.has(id)) {
          existente.add(id);
          gasite.push(w);
        }
      }
    }
  }

  return { ...entity, occurrences: [...entity.occurrences, ...gasite] };
}
```

- [ ] **Step 4: Rulează — trebuie să treacă**

Run: `npm test`
Expected: toate testele PASS

- [ ] **Step 5: Componenta de selecție pe imagine**

Create `frontend/components/anonimizare/ImageSelector.tsx`:

```tsx
"use client";
import { useRef, useState } from "react";
import type { Box } from "@/lib/anonimizare/types";

type Props = { src: string; onSelect: (box: Box) => void };

export default function ImageSelector({ src, onSelect }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [curent, setCurent] = useState<Box | null>(null);

  /** Coordonate în pixelii reali ai imaginii (nu cei afișați). */
  function pozitie(e: React.MouseEvent): { x: number; y: number } {
    const img = imgRef.current!;
    const r = img.getBoundingClientRect();
    const scaleX = img.naturalWidth / r.width;
    const scaleY = img.naturalHeight / r.height;
    return { x: (e.clientX - r.left) * scaleX, y: (e.clientY - r.top) * scaleY };
  }

  function afisaj(b: Box) {
    const img = imgRef.current!;
    const r = img.getBoundingClientRect();
    const sx = r.width / img.naturalWidth;
    const sy = r.height / img.naturalHeight;
    return { left: b[0] * sx, top: b[1] * sy, width: (b[2] - b[0]) * sx, height: (b[3] - b[1]) * sy };
  }

  return (
    <div className="relative inline-block select-none">
      <img
        ref={imgRef}
        src={src}
        alt="captură"
        className="max-w-full border border-[#e2e5f0] rounded-lg cursor-crosshair"
        draggable={false}
        onMouseDown={(e) => { const p = pozitie(e); setStart(p); setCurent([p.x, p.y, p.x, p.y]); }}
        onMouseMove={(e) => {
          if (!start) return;
          const p = pozitie(e);
          setCurent([Math.min(start.x, p.x), Math.min(start.y, p.y), Math.max(start.x, p.x), Math.max(start.y, p.y)]);
        }}
        onMouseUp={() => {
          if (curent && curent[2] - curent[0] > 5 && curent[3] - curent[1] > 5) onSelect(curent);
          setStart(null); setCurent(null);
        }}
      />
      {curent && (
        <div
          className="absolute border-2 border-[#18257f] bg-[#18257f]/15 pointer-events-none"
          style={afisaj(curent)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 6: Leagă selectorul în pagină**

În `frontend/app/(app)/anonimizare/page.tsx`:

Adaugă importurile:
```tsx
import ImageSelector from "@/components/anonimizare/ImageSelector";
import { entityFromSelection, propagateEntity } from "@/lib/anonimizare/selection";
import { numeroteaza } from "@/lib/anonimizare/classify";
import type { Box } from "@/lib/anonimizare/types";
```

Adaugă în componentă, după `const [error, setError] = useState("");`:
```tsx
  const [urls, setUrls] = useState<string[]>([]);
  const [activa, setActiva] = useState(0);

  function adaugaSelectie(box: Box) {
    const cuvinte = lines.filter((l) => l.imageIndex === activa).flatMap((l) => l.words);
    const noua = propagateEntity(entityFromSelection(cuvinte, box, activa), lines);
    if (entities.some((e) => e.id === noua.id)) return; // deja în tabel
    setEntities(numeroteaza([...entities, noua]));
  }
```

În `porneste`, după `setFiles(fisiere);` adaugă:
```tsx
    setUrls(fisiere.map((f) => URL.createObjectURL(f)));
    setActiva(0);
```

În `reseteaza`, la început adaugă:
```tsx
    urls.forEach((u) => URL.revokeObjectURL(u));
    setUrls([]);
```

În blocul `state === "review"`, după `<RulesTable ... />` adaugă:
```tsx
          <div className="border-t border-[#eef0f8] pt-4">
            <p className="text-sm font-semibold text-[#1e3a5f] mb-1">
              Lipsește ceva? Trage un dreptunghi peste zona de anonimizat
            </p>
            <p className="text-xs text-slate-400 mb-3">
              Citesc textul din selecție și îl adaug în tabel, ca să-l poți edita.
            </p>
            {urls.length > 1 && (
              <div className="flex gap-2 mb-3 flex-wrap">
                {urls.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setActiva(i)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold ${
                      i === activa ? "bg-[#18257f] text-white" : "bg-[#f1f3f8] text-[#18257f]"
                    }`}
                  >
                    Captura {i + 1}
                  </button>
                ))}
              </div>
            )}
            {urls[activa] && <ImageSelector src={urls[activa]} onSelect={adaugaSelectie} />}
          </div>
```

- [ ] **Step 7: Verifică build + teste**

Run: `npm test && npm run build`
Expected: teste PASS, build reușit

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/anonimizare/selection.ts frontend/lib/anonimizare/selection.test.ts frontend/components/anonimizare/ImageSelector.tsx "frontend/app/(app)/anonimizare/page.tsx"
git commit -m "feat: selectie manuala inteligenta care reconstituie textul din zona"
```

---

### Task 8: Aplicare, descărcare .zip și integrare în navigație

**Files:**
- Modify: `frontend/app/(app)/anonimizare/page.tsx` (stările `applying`/`done`), `frontend/components/Sidebar.tsx`, `frontend/app/(app)/dashboard/page.tsx`

**Interfaces:**
- Consumes: `redactImage`, `Edit` (Task 4); entitățile din pagină.

- [ ] **Step 1: Instalează jszip**

```bash
cd frontend
npm install jszip
```

- [ ] **Step 2: Adaugă aplicarea și descărcarea în pagină**

În `frontend/app/(app)/anonimizare/page.tsx` adaugă importurile:
```tsx
import JSZip from "jszip";
import { redactImage, type Edit } from "@/lib/anonimizare/redact";
```

Adaugă starea pentru rezultate, după `const [activa, setActiva] = useState(0);`:
```tsx
  const [rezultate, setRezultate] = useState<{ nume: string; url: string; blob: Blob }[]>([]);
```

Adaugă funcțiile, după `adaugaSelectie`:
```tsx
  function incarcaImagine(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Nu am putut încărca imaginea"));
      img.src = url;
    });
  }

  async function aplica() {
    setState("applying");
    setProgres("Aplic modificările...");
    try {
      const out: { nume: string; url: string; blob: Blob }[] = [];
      for (let i = 0; i < files.length; i++) {
        const edits: Edit[] = entities
          .filter((e) => e.enabled && e.replacement.trim())
          .flatMap((e) =>
            e.occurrences
              .filter((o) => o.imageIndex === i)
              .map((o) => ({ box: o.box, text: e.replacement.trim() }))
          );
        const img = await incarcaImagine(urls[i]);
        const blob = await redactImage(img, edits);
        const nume = files[i].name.replace(/(\.[^.]+)$/, "") + " - anonimizat.png";
        out.push({ nume, url: URL.createObjectURL(blob), blob });
        setProgres(`Procesez captura ${i + 1} din ${files.length}...`);
      }
      setRezultate(out);
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eroare la aplicarea modificărilor");
      setState("error");
    }
  }

  async function descarcaZip() {
    const zip = new JSZip();
    for (const r of rezultate) zip.file(r.nume, r.blob);
    const continut = await zip.generateAsync({ type: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(continut);
    a.download = "capturi-anonimizate.zip";
    a.click();
    URL.revokeObjectURL(a.href);
  }
```

În `reseteaza`, adaugă după `setUrls([]);`:
```tsx
    rezultate.forEach((r) => URL.revokeObjectURL(r.url));
    setRezultate([]);
```

În blocul `state === "review"`, imediat înainte de butonul „Începe cu alt set", adaugă:
```tsx
          <button
            onClick={aplica}
            className="w-full bg-[#18257f] hover:bg-[#131e66] text-white py-2.5 rounded-lg text-sm font-semibold transition-colors"
          >
            Aplică și generează capturile anonimizate
          </button>
```

Adaugă stările noi, înainte de blocul `state === "error"`:
```tsx
      {state === "applying" && <ProcessingSpinner label={progres} />}

      {state === "done" && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
            Gata — {rezultate.length} capturi anonimizate.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {rezultate.map((r) => (
              <a key={r.nume} href={r.url} download={r.nume} className="block group">
                <img src={r.url} alt={r.nume} className="w-full border border-[#e2e5f0] rounded-lg group-hover:border-[#18257f]" />
                <p className="text-[11px] text-slate-500 mt-1 truncate">{r.nume}</p>
              </a>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={descarcaZip}
              className="bg-[#18257f] hover:bg-[#131e66] text-white px-4 py-2 rounded-lg text-sm font-semibold"
            >
              ↓ Descarcă toate (.zip)
            </button>
            <button onClick={reseteaza} className="border border-[#d6d9e2] text-[#18257f] px-4 py-2 rounded-lg text-sm font-semibold">
              + Anonimizează alt set
            </button>
          </div>
        </div>
      )}
```

- [ ] **Step 3: Adaugă tool-ul în Sidebar**

În `frontend/components/Sidebar.tsx`, în lista `items`, după linia cu `/scenarii`, adaugă:
```tsx
  { href: "/anonimizare", icon: "🕶️", label: "Anonimizare" },
```

- [ ] **Step 4: Adaugă cardul în dashboard**

În `frontend/app/(app)/dashboard/page.tsx`:

În `TOOLS`, după obiectul `scenarii`, adaugă:
```tsx
  {
    href: "/anonimizare",
    tool: "anonimizare",
    icon: "🕶️",
    title: "Anonimizare",
    desc: "Capturi de ecran → nume de firme și parteneri ascunse, direct în browser.",
    faraIstoric: true,
  },
```

Schimbă clasa grilei de carduri din:
```tsx
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
```
în:
```tsx
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
```

Înlocuiește blocul link-ului „Istoric" cu varianta condiționată:
```tsx
              {!("faraIstoric" in t && t.faraIstoric) && (
                <Link
                  href={`/repository?tool=${t.tool}`}
                  className="border border-[#d6d9e2] text-[#18257f] hover:bg-[#f1f3f8] rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors"
                >
                  Istoric
                </Link>
              )}
```

- [ ] **Step 5: Verifică build + teste**

Run: `npm test && npm run build`
Expected: teste PASS, build reușit, `/anonimizare` în lista de rute

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json "frontend/app/(app)/anonimizare/page.tsx" frontend/components/Sidebar.tsx "frontend/app/(app)/dashboard/page.tsx"
git commit -m "feat: aplicare, descarcare zip si integrare in navigatie"
```

---

### Task 9: Verificare end-to-end cu capturile reale

**Files:** fără fișiere noi; eventuale fixuri descoperite acum.

- [ ] **Step 1: Rulează întreaga suită și build-ul**

Run (din `frontend/`): `npm test && npm run build`
Expected: toate verzi

- [ ] **Step 2: Pornește aplicația local**

Run: `npm run dev` (din `frontend/`); deschide `http://localhost:3000/anonimizare`

- [ ] **Step 3: Verifică fluxul complet cu capturile reale**

Încarcă ambele fișiere din `D:\AI_Claude\anonimizare\input\` (`poza 1.png`, `poza 2.png`) și verifică:
1. Progresul afișează „Analizez captura 1 din 2..." apoi „2 din 2".
2. Tabelul conține cel puțin `ORCHID S.R.L.` (Firmă → `TotalSoft`) și `AGACHE EUGEN` / `AGACHEEUGEN` (Persoană → `PartenerTest`).
3. Numărul de apariții este >1 pentru ORCHID (apare în ambele capturi).
4. Editarea unui înlocuitor se reflectă în rezultat.
5. Debifarea unei entități o exclude din rezultat.

- [ ] **Step 4: Verifică selecția manuală**

Trage un dreptunghi peste textul „Baza de date: Main\Orchid" din bara de jos (cazul ratat de detecția automată, documentat în spec). Verifică:
1. Apare un rând nou în tabel, marcat „manual", cu textul reconstituit.
2. **Numărul de apariții este 2, nu 1** — aceeași bară de status există în ambele capturi, deci selecția s-a propagat automat pe tot setul.
3. Poți edita înlocuitorul.
4. După aplicare, zona e acoperită și rescrisă în **ambele** capturi.

- [ ] **Step 5: Verifică rezultatul final**

Apasă „Aplică", apoi:
1. Previzualizările arată capturile cu numele înlocuite.
2. Compară vizual cu rezultatele de referință din `D:\AI_Claude\anonimizare\output\` (obținute cu scriptul Python).
3. „Descarcă toate (.zip)" produce o arhivă cu ambele fișiere.
4. Textul rescris nu iese din casete (verifică `PartenerTest1` peste `AGACHE EUGEN`).

- [ ] **Step 6: Commit final (doar dacă au fost fixuri)**

```bash
git add -A frontend/
git commit -m "fix: ajustari post-verificare e2e anonimizare"
```

---

## Post-implementare (deploy — separat, după acceptarea utilizatorului)

Nu face parte din plan; de discutat la final: `vercel --prod` din `frontend/`. **Backend-ul nu se modifică deloc** — nu e nevoie de deploy pe Render.
