# Prompt: Notițe compacte dintr-un fragment de transcript

Primești un FRAGMENT dintr-un transcript de ședință TotalSoft (nu întreaga ședință).
Extragi notițe compacte care vor fi combinate ulterior cu notițele celorlalte fragmente.

## Output

JSON valid, fără markdown fence:

```json
{
  "subiecte": [
    {"titlu": "Subiect discutat (Title Case, max 80 char)", "puncte": ["idee concretă 1", "idee concretă 2"]}
  ],
  "decizii": ["decizie agreată explicit în acest fragment"],
  "actiuni": [
    {"responsabil": "Nume client / TotalSoft / persoană", "actiune": "Verb pers. III + acțiune concretă.", "termen": "DD.MM.YYYY sau omite câmpul"}
  ]
}
```

## Reguli

- Maxim 6 subiecte per fragment, maxim 5 puncte per subiect.
- Punctele sunt fraze scurte dar complete și informative: includ cifre, nume de ecrane Charisma, termeni tehnici, cerințe și răspunsuri exact cum apar în discuție. NU pierde nicio informație de business.
- `decizii` = doar acorduri explicite („s-a agreat", „rămâne stabilit"). Dacă nu există, listă goală.
- `actiuni` = doar sarcini concrete cu responsabil identificabil. Dacă nu există, listă goală.
- NU inventa conținut. NU repeta politeturi, small talk, probleme tehnice de conexiune.
- Dacă fragmentul continuă un subiect început anterior (începe în mijlocul unei idei), extrage ce se înțelege din fragment.
- Totalul output-ului să nu depășească ~1.500 caractere.
