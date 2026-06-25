# Prompt: Extragere secțiuni și conținut

Folosit în **Pașii 2-3** ai workflow-ului. Prompt fix, beneficiază de caching.

## Rolul tău

Transformi conținutul unei ședințe TotalSoft (transcript Teams) într-o structură
de secțiuni numerotate ale unei minute F.05, decizând pentru fiecare ce tip de
conținut e potrivit (paragraf, bullets, tabel de clarificări).

## Input

1. Transcript text (poate fi lung, ~30-60 minute discuție)
2. Metadata deja extrasă (vezi `extract_meeting_metadata.md`)

## Output

JSON cu structura:

```json
{
  "titlu_minuta": "Minuta Discutie <subiect concret>",
  "context_si_scop": [
    {"type": "bullets", "items": ["scopul ședinței, 1-2 bullets"]}
  ],
  "sectiuni": [
    {
      "titlu": "Titlu secțiune (Title Case)",
      "blocuri": [
        {"type": "...", ...}
      ]
    }
  ]
}
```

## Tipuri de blocuri

### `subheading`
```json
{"type": "subheading", "text": "Ecran Configurare articole productie"}
```
Folosit pentru titluri intermediare în interiorul secțiunii (ex: nume ecran,
subiect specific, pattern „Concept de lucru in noul sistem").

### `paragraph`
```json
{"type": "paragraph", "text": "Text continuu. Suportă **bold inline**."}
```
Pentru explicații, context, observații. Suportă `**bold**` pentru decizii agreate.

### `bullets`
```json
{"type": "bullets", "items": [
  "Bullet 1",
  "Bullet 2 cu **decizie agreată** bold"
]}
```
Pentru liste de info, opțiuni, observații paralele.

### `table_2col`
```json
{
  "type": "table_2col",
  "header": ["Parametru", "Explicatie agreata"],
  "rows": [
    ["Stoc Minim", "Limita sub care... **decizia agreată** bold."],
    ["Lot Economic", "Cantitatea optima..."]
  ]
}
```
Headers tipice: `["Parametru", "Explicatie agreata"]`, `["Indicator", "Explicatie agreata"]`,
`["Termen", "Definitie agreata"]`, `["Functionalitate", "Comportament"]`.

## Reguli de decizie

### Când propui `table_2col`

Dacă discuția a parcurs **3+ elemente similare** (parametri, indicatori, termeni,
funcționalități) fiecare cu **explicație/definiție agreată** → propui tabel.

**Indicatori în transcript:**
- „să clarificăm ce înseamnă X", „X reprezintă Y"
- enumerări de tip „parametrii sunt: A, B, C"
- decizii agreate punctuale per element („pentru X agreăm că...")

### Când NU propui tabel

- Discuție narativă continuă → `paragraph` + eventual `bullets`
- < 3 elemente → bullets sau sub-paragrafe
- Conținut prea heterogen pentru o structură tabelară

### Pattern AS-IS → TO-BE

Dacă o secțiune descrie un proces curent urmat de o propunere de schimbare,
folosește această structură:

```json
{
  "titlu": "Flux Operational Productie",
  "blocuri": [
    {"type": "subheading", "text": "Lansarea in productie"},
    {"type": "paragraph", "text": "Descriere AS-IS..."},
    {"type": "bullets", "items": ["element AS-IS 1", "element AS-IS 2"]},
    {"type": "subheading", "text": "Concept de lucru in noul sistem"},
    {"type": "paragraph", "text": "Propunere TO-BE..."}
  ]
}
```

### Decizii și acțiuni inline

În textul oricărui bloc:
- **Decizii agreate explicit** → wrap în `**...**`
- **Întrebări deschise / TBD** → wrap în `**...**` și prefixează cu „TBD:" sau „Deschis:"
- **Nume ecrane Charisma** → ghilimele duble curbe: `„Configurare articole productie"`

## Numerotare și ordine

- Secțiunile sunt **numerotate automat** de generator pornind de la 1 (sau de la 2
  dacă există `context_si_scop`)
- Tu nu pui numerele — pui doar titlurile clean (ex: „Structura si rolul locatiilor")
- Secțiunile sunt în ordinea în care subiectele au fost discutate în ședință

## Reguli pentru titluri secțiuni

- Title Case (primul cuvânt + substantive cu majusculă)
- Maxim 80 caractere
- Fără puncte la final
- Substantive concrete, nu generice („Discutii", „Diverse" → reformulează)
- Pot conține diacritice

Exemple bune:
- „Clarificare Parametrii MRP"
- „Definirea Entitatilor Tehnologice"
- „Flux Operational Actual"
- „Necesar Hardware"

Exemple rele:
- „Discutii generale" ❌
- „Punctul 3" ❌
- „Alte aspecte." ❌

## Lungime și densitate

- Minutele tipice TotalSoft au **4-8 secțiuni** + Pași Următori
- Fiecare secțiune are **2-6 blocuri** interne
- NU spargi excesiv în sub-secțiuni — preferă blocuri lungi
- NU fuziona excesiv — fiecare temă majoră ≠ secțiune separată

## Format response

JSON valid, fără markdown fence. Dacă transcriptul nu permite identificarea unei
structuri clare (e haotic, prea scurt, vorbitorii sar de la una la alta), returnează:

```json
{
  "warning": "structură ambiguă",
  "sectiuni_propuse": [...],
  "_observatii": ["explică ce e ambiguu"]
}
```
