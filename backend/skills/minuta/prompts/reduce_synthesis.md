# Prompt: Sinteza finală a minutei din notițe parțiale

Primești notițe compacte extrase din fragmentele consecutive ale unui transcript
de ședință TotalSoft (FRAGMENT 1..N, în ordine cronologică). Le combini într-o
minută F.05 coerentă, ca și cum ai fi văzut întreaga ședință.

## Output

JSON valid, fără markdown fence:

```json
{
  "context_si_scop": [
    {"type": "bullets", "items": ["scopul ședinței, 1-2 bullets"]}
  ],
  "sectiuni": [
    {
      "titlu": "Titlu secțiune (Title Case, max 80 char, fără punct final)",
      "blocuri": [
        {"type": "paragraph", "text": "Text continuu. Suportă **bold** pentru decizii agreate."},
        {"type": "subheading", "text": "Titlu intermediar"},
        {"type": "bullets", "items": ["element 1", "element cu **decizie agreată**"]},
        {"type": "table_2col", "header": ["Parametru", "Explicatie agreata"], "rows": [["X", "explicație"]]}
      ]
    }
  ],
  "pasi_urmatori": [
    {"responsabil": "Nume client / TotalSoft / persoană", "actiune": "Verb pers. III + acțiune. Max 200 char.", "termen": "DD.MM.YYYY sau omite câmpul"}
  ]
}
```

## Reguli de combinare

- **Fuzionează subiectele duplicate**: același subiect discutat în fragmente diferite = O singură secțiune care combină toate punctele.
- Secțiunile urmează ordinea cronologică a discuției.
- Minutele tipice au **4-8 secțiuni**, fiecare cu 2-6 blocuri. Nu fragmenta excesiv.
- Folosește `table_2col` doar când 3+ elemente similare au explicații agreate (headers tipice: „Parametru/Explicatie agreata", „Functionalitate/Comportament").
- Deciziile agreate → `**bold**` în text. Întrebări deschise → prefix „TBD:" + `**bold**`.
- Titluri secțiuni: substantive concrete („Clarificare Parametrii MRP"), nu generice („Discuții", „Diverse").

## Reguli pași următori

- Consolidează acțiunile duplicate/similare ale aceluiași responsabil.
- Ordine: cu termen (cronologic) → nominale fără termen → de grup → TBD.
- Responsabil concret sau „TBD" — niciodată „Toți"/„Echipa".
- Tipic 3-5 pași, maxim 8. Minim 1.
- Deciziile deja agreate NU sunt pași — merg ca **bold** în secțiuni.
