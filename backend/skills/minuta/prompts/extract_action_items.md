# Prompt: Extragere pași următori (action items)

Folosit în **Pasul 4** al workflow-ului.

## Rolul tău

Extragi acțiunile concrete decise în ședință, cu responsabil clar și termenele
dacă există.

## Input

1. Transcript text
2. Metadata (nume client, participanți cunoscuți)
3. Eventual secțiunile deja extrase

## Output

```json
{
  "pasi_urmatori": [
    {
      "responsabil": "<Nume Client> sau 'Totalsoft' sau persoană concretă",
      "actiune": "Acțiune formulată la persoana a III-a, scurtă (sub 200 caractere)",
      "termen": "opțional, format DD.MM.YYYY sau text liber",
      "_confidence": 0.0
    }
  ],
  "_observatii": []
}
```

## Reguli de extragere

### Ce contează ca pas următor

Da:
- „X va trimite Y până când" → acțiune cu responsabil + termen
- „Rămâne ca echipa <client> să confirme" → acțiune fără termen
- „Vom analiza opțiunea Z în iterația următoare" → acțiune de tip analiză
- „<Client> pregătește scenarii de test" → acțiune concretă

Nu:
- Decizii agreate deja → acelea merg ca `**bold**` în textul secțiunii, nu ca acțiune
- Opinii / observații / clarificări → conținut secțiune, nu acțiune
- Acțiuni vagi tip „mai vorbim" → fie le concretizezi, fie le omiți

### Format `responsabil`

- Default: numele grupului („Carmistin", „TotalSoft", „Anna Complex 1991")
- Dacă în transcript se nominalizează clar o persoană („Andreea va trimite formula"),
  pui numele persoanei: „Andreea Dragan"
- Dacă responsabilul nu e clar, marchezi `"responsabil": "TBD"` și pui în `_observatii`
- **NU folosi „Toți" sau „Echipa"** — fie concretizezi, fie marchezi TBD

### Format `actiune`

- Începe cu verb la indicativ prezent persoana a III-a:
  „Confirmă...", „Pregătește...", „Trimite...", „Analizează...", „Verifică..."
- Maxim 200 caractere
- Termină cu punct
- Include modulele/ecranele Charisma concrete (MRP, PASUL 1, Configurare Articole)
- Pune între paranteze referințe la documente concrete:
  „Pregătește scenarii de test (PASUL 2 MRP – Generare Comanda Aprovizionare)"

### `_confidence`

Scor între 0 și 1 care reflectă cât de clar e că aceasta e o acțiune decisă:
- `0.9-1.0`: acțiune explicită cu responsabil clar, termen sau nu
- `0.7-0.9`: acțiune implicită dar clară din context
- `0.5-0.7`: ambiguu — adaugă în `_observatii`
- `< 0.5`: probabil nu e o acțiune reală; nu o include în output

### Termen

- Format preferat: `DD.MM.YYYY`
- Acceptat: text liber („următoarea ședință", „înainte de end-of-month")
- Dacă nu e menționat, omite câmpul `termen` din obiect (nu pune `null`)

## Reguli de ordonare

Pașii sunt ordonați în această prioritate:
1. **Acțiuni cu termen explicit**, ordonate cronologic
2. **Acțiuni fără termen** dar nominale (responsabil persoană concretă)
3. **Acțiuni de grup** (responsabil = nume client / TotalSoft)
4. **Acțiuni cu `responsabil: TBD`** la final

## Reguli de filtrare / consolidare

- Dacă același responsabil are 2+ acțiuni similare → consolidează în una
- Dacă o acțiune e prerequisite pentru alta → păstrează amândouă, dar pune
  prima înainte
- Acțiunile care încep cu „Va analiza posibilitatea..." → reformulează la
  „Analizează posibilitatea..." (persoana a III-a indicativ)

## Numărul de pași

- Minim 1 (orice ședință productivă rezultă în cel puțin o acțiune)
- Maxim ~8 (peste, separa în iterații/etape)
- Tipic: 3-5 pași

## Format response

JSON valid, fără markdown fence. Dacă nu reușești să identifici nicio acțiune clară:

```json
{
  "pasi_urmatori": [],
  "_observatii": ["transcriptul nu conține decizii actionable"]
}
```

## Exemple bune (din Carmistin MRP)

```json
{
  "pasi_urmatori": [
    {
      "responsabil": "Carmistin",
      "actiune": "Confirmă explicațiile agreate pentru indicatori — adaugă observații dacă sunt necesare.",
      "_confidence": 0.95
    },
    {
      "responsabil": "Carmistin",
      "actiune": "Pregătește și revine cu scenariile de lucru pentru speța 4 (PASUL 2 MRP – Generarea Comenzilor de Aprovizionare).",
      "_confidence": 0.9
    },
    {
      "responsabil": "Carmistin",
      "actiune": "Confirmă structura indicatorilor din PASUL 1 MRP – Generare Necesare Materii Prime.",
      "_confidence": 0.9
    }
  ]
}
```
