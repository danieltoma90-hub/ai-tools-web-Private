# Tool „Anonimizare capturi" — Design

**Data:** 2026-08-05
**Status:** aprobat de utilizator (sesiune brainstorming)
**Scop:** al 4-lea tool în ai-tools-web — ascunde datele sensibile (nume de firme, parteneri) din capturi de ecran, pentru documentație / training / demo.

## Problemă

Capturile din Charisma ERP folosite în documentație conțin date reale de client (denumiri de firme, nume de parteneri). Anonimizarea manuală în editoare de imagini e lentă și inconsecventă. Există deja un skill local (`D:\AI_Claude\skills\anonimizare-screenshot`) care rezolvă redactarea, dar cere coordonate introduse manual și rulează doar pe calculatorul autorului.

## Decizii (cu utilizatorul)

1. **Zero backend** — tot procesul rulează în browser. Imaginile NU urcă pe server (nici temporar), nu se salvează în Repository.
2. **Batch** — se încarcă mai multe capturi odată; regulile de înlocuire sunt globale pe tot setul; descărcare `.zip`.
3. **Detecție automată + confirmare** — aplicația propune, utilizatorul confirmă/editează/debifează. Câmpul de înlocuire este **editabil**.
4. **Numerotare** — entități multiple de același tip primesc sufix numeric (`PartenerTest1`, `PartenerTest2`); dacă e una singură, fără număr (`TotalSoft`).
5. **Cost zero** — fără AI, fără API plătit, fără tokeni din abonament. OCR local open-source.

**Respinse:** OCR pe server cu RapidOCR (vârf 409 MB RAM măsurat > 512 MB Render free); AI vision (ar consuma credite plătite; abonamentul Claude Code nu poate fi folosit ca API de backend multi-user).

## Arhitectură

100% client-side, într-o pagină Next.js nouă `frontend/app/(app)/anonimizare/page.tsx`. Fără endpoint de backend, fără storage.

| Componentă | Tehnologie | Rol |
|---|---|---|
| OCR | `tesseract.js` (WASM) | extrage textul + casetele (bounding boxes) |
| Clasificare | TypeScript, regex | firmă / persoană / nedetectat |
| Redactare | Canvas 2D API | acoperă cu fundal eșantionat + rescrie textul |
| Împachetare | `jszip` | descărcare set ca `.zip` |

Assets tesseract (WASM + `traineddata`) se descarcă de la CDN la prima utilizare și rămân în cache-ul browserului. *(Revizuit la scrierea planului: auto-găzduirea în `frontend/public/tesseract/` ar adăuga ~15 MB în repo; se comută pe ea doar dacă spike-ul de validare arată că rețeaua corporate blochează CDN-ul.)*

### Module (fișiere)

- `lib/anonimizare/ocr.ts` — inițializare worker tesseract, `recognize(file) -> Word[]` (text + box + confidence).
- `lib/anonimizare/classify.ts` — `classifyEntities(words) -> Entity[]`; euristici firmă/persoană; grupare pe text normalizat.
- `lib/anonimizare/redact.ts` — `redactImage(image, edits) -> Blob`; eșantionare culoare fundal/cerneală, acoperire, rescriere text pe Canvas.
- `components/anonimizare/RulesTable.tsx` — tabelul de reguli (bifă, text găsit, tip, înlocuitor editabil, nr. apariții).
- `components/anonimizare/ManualBoxEditor.tsx` — selecție cu dreptunghi pe imagine; reconstituie textul din selecție și creează un rând nou în tabelul de reguli (vezi „Selecție manuală inteligentă").
- `app/(app)/anonimizare/page.tsx` — mașina de stări și orchestrarea.

### Model de date

```ts
type Word = { text: string; box: [number, number, number, number]; conf: number; imageIndex: number };
type EntityKind = "firma" | "persoana";
type Entity = {
  id: string;
  originalText: string;      // text normalizat, cheia de grupare
  kind: EntityKind;
  replacement: string;       // propus automat, editabil
  enabled: boolean;          // bifa din tabel
  occurrences: Word[];       // toate aparițiile, în toate imaginile
};
type ManualEdit = { imageIndex: number; box: [number,number,number,number]; text: string };
```

## Detecție (euristici validate)

Testate pe capturile reale (rezultate: toate cele 5 apariții „ORCHID S.R.L." și 3 „AGACHE EUGEN" găsite, încredere 86-92%):

- **Firmă**: cuvânt capitalizat urmat de sufix juridic — `S.R.L.`, `S.A.`, `SRL`, `SA`, `PFA`, `LTD`, `GMBH`, `SNC`, `SCS`. **Sufixul trebuie să fie cu MAJUSCULE în textul original** — altfel cuvântul românesc „sa" produce fals pozitiv (constatat la test).
- **Persoană**: ≥2 cuvinte consecutive cu MAJUSCULE (≥4 litere fiecare), excluzând lista de termeni de interfață: `ADMINISTRATOR, TOTALSOFT, TOTAL, MAIN, ORC, TVA, RON, TEST, PARTENER, NUME, CLIENT, DATA, PUNCT, LUCRU, NUMAR, SERIAL, VALOARE, REST, PLATA, SCADENTA, FACTURA, INTERN`.
- **Grupare**: aparițiile cu același text normalizat (fără spații/punctuație, uppercase) = aceeași entitate → același înlocuitor în toate imaginile.
- **Casete la nivel de cuvânt**: se lucrează pe `word.bbox` furnizat de tesseract.js, nu pe linii întregi — astfel se redactează doar denumirea, nu toată eticheta din jur.
- **Propagare pe tot setul (potrivire exactă)**: o entitate — detectată automat sau marcată manual — se caută în **toate** imaginile și primește același înlocuitor peste tot. Marcarea manuală într-o singură captură acoperă astfel întregul set (ex. bara de status identică în 10 capturi).

*Revizuit la scrierea planului:* propagarea **prin subșir** (a găsi automat `Orchid` în interiorul cuvântului `Main\Orchid` și a rescrie `Main\TotalSoft`) a fost **scoasă din scop** ca YAGNI — ar cere text de înlocuire diferit per apariție. Cazul e acoperit de selecția manuală, care se propagă pe tot setul cu o singură marcare.

**Limitări cunoscute și acceptate:** adresele scrise cu MAJUSCULE (ex. „NUFERILOR") sunt clasificate ca persoană — fals pozitiv de tip, dar sunt oricum date sensibile; utilizatorul decide din tabel. Textul ratat complet se acoperă prin selecție manuală.

## Selecție manuală inteligentă

Pe orice imagine, utilizatorul trage un dreptunghi peste zona de anonimizat. Aplicația **reconstituie singură textul din selecție** și populează un rând nou în tabelul de reguli, identic ca formă cu cele detectate automat — utilizatorul doar editează înlocuitorul.

Comportament:
1. Se colectează cuvintele OCR ale căror casete **se intersectează ≥50%** cu selecția.
2. Se reconstituie textul în ordinea de citire (sus→jos, stânga→dreapta), separat prin spațiu.
3. Se rulează aceeași clasificare (firmă/persoană) pe textul reconstituit → se propune înlocuitorul (`TotalSoft` / `PartenerTestN`), **editabil**.
4. Se creează un rând nou în tabel, cu bifa activă, marcat vizual ca „manual". Aparițiile sunt cuvintele din selecție.
5. Ca orice altă entitate, textul reconstituit se propagă în tot setul (aceeași denumire găsită în alte imagini primește același înlocuitor).

**Dacă OCR nu a găsit niciun cuvânt în selecție** (text ratat complet): rândul se creează cu textul original marcat `(nedetectat)`, caseta desenată devine singura apariție, iar utilizatorul scrie manual înlocuitorul. Redactarea funcționează identic — se acoperă și se rescrie.

Selecția se poate șterge (rândul dispare din tabel).

## Redactare

Portarea tehnicii validate din skill-ul local:
1. Se eșantionează **culoarea fundalului** = mediana unei benzi de 4 px deasupra casetei (prinde gradientul barelor de status).
2. Se eșantionează **culoarea cernelii** = mediana pixelilor întunecați din casetă.
3. Se acoperă caseta (+2 px padding) cu fundalul.
4. Se scrie textul înlocuitor, aliniat pe caseta originală.

**Font (regulă unică, fără decizii ambigue):** familie `Arial, Helvetica, sans-serif`; se folosește **bold** dacă densitatea pixelilor de cerneală din casetă depășește 22% (heuristică pentru text îngroșat). Mărimea = înălțimea casetei × 1,35.

**Text prea lung — prioritate lizibilității.** Dacă înlocuitorul depășește lățimea casetei + 4 px:
1. Se micșorează fontul în pași de 0,5 px, **dar nu sub 90%** din mărimea inițială (limită de lizibilitate).
2. Dacă tot nu încape, se **trunchiază** textul caracter cu caracter și se adaugă elipsă: `PartenerTest1` → `Parten…`.

Regula: **nu se micșorează textul până devine ilizibil** — se taie și se marchează cu `…`, convenția uzuală. Mărimea rezultată și eventuala trunchiere se aplică per apariție (aceeași entitate poate încăpea întreagă într-o casetă lată și trunchiată într-una îngustă).

## Flux UI (mașină de stări)

`idle → scanning → review → applying → done | error`

- **idle** — zonă drag & drop, acceptă `.png`, `.jpg`; oricâte fișiere.
- **scanning** — progres per imagine („Analizez 2 din 7...").
- **review** — tabelul de reguli + galeria de imagini; pe fiecare imagine se poate trage o selecție care adaugă automat un rând nou în tabel (vezi „Selecție manuală inteligentă").
- **applying** — redactare pe Canvas.
- **done** — previzualizare rezultate + „Descarcă toate (.zip)"; buton „Anonimizează alt set".
- **error** — mesaj în română + reluare.

Texte în română cu diacritice, în stilul celorlalte pagini (ToolCard, UploadZone, ProcessingSpinner refolosite).

## Risc principal și plan de validare

**Riscul:** euristicile și acuratețea au fost validate cu **RapidOCR** (motor Python). În browser se folosește **tesseract.js** — alt motor, acuratețe potențial diferită pe text mic de interfață.

**Mitigare — prima activitate de implementare este un test de validare:** se rulează tesseract.js pe aceleași două capturi (`D:\AI_Claude\anonimizare\input\`) și se compară: câte dintre cele 8 apariții-țintă sunt găsite, cu ce încredere și cu ce acuratețe a casetelor. Rezultatul se raportează utilizatorului **înainte** de a construi interfața.

**Praguri de decizie:**
- Găsește ≥6 din 8 apariții → se continuă cu design-ul complet.
- Găsește <6 → se continuă cu **marcarea manuală** ca mod principal (tool-ul rămâne util), iar detecția automată se amână.

## Testare

- Unitar: `classify.ts` — firmă cu/fără sufix, falsul pozitiv „sa", termenii de interfață excluși, gruparea aparițiilor, numerotarea entităților multiple.
- Unitar: `redact.ts` — eșantionarea culorilor pe imagine sintetică, acoperirea casetei, **trunchierea cu elipsă** (text lung într-o casetă îngustă → `Parten…`, fără a coborî sub 90% din mărime).
- Unitar: reconstituirea textului din selecție (intersecție ≥50%, ordine de citire, cazul „niciun cuvânt găsit").
- Vizual: capturile reale, comparate cu rezultatul deja obținut manual (`D:\AI_Claude\anonimizare\output\`).

## În afara scopului (YAGNI)

Salvare pe server / Repository; procesare PDF; detecție AI; editare avansată de imagine (blur, pixelare); OCR pentru alte limbi decât română/engleză.
