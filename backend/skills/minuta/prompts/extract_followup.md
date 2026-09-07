# Prompt: Stadiul acțiunilor deschise anterior

Primești CONTEXTUL proiectului (care conține acțiunile rămase deschise din ședințele
anterioare) și transcriptul ședinței curente.

## Rolul tău

Pentru FIECARE acțiune deschisă din context, stabilești ce s-a întâmplat cu ea în
ședința curentă — strict pe baza transcriptului, fără să presupui.

## Output

JSON valid, fără markdown fence:

```json
{
  "stadiu_actiuni": [
    {
      "actiune": "textul acțiunii, exact ca în context",
      "responsabil": "cine era responsabil",
      "stare": "Finalizată" | "În lucru" | "Nediscutată" | "Anulată",
      "detaliu": "ce s-a spus concret în ședință; gol dacă nu s-a discutat"
    }
  ]
}
```

## Reguli

- **Nu inventa**: dacă acțiunea nu apare deloc în discuție, starea e „Nediscutată" și `detaliu` rămâne gol.
- „Finalizată" doar dacă din transcript reiese explicit că s-a făcut (cineva confirmă livrarea/execuția).
- „În lucru" dacă se discută despre ea dar nu e încheiată — pune în `detaliu` ce s-a spus (blocaje, termen nou).
- „Anulată" dacă se agreează explicit că nu se mai face.
- Păstrează acțiunile în ordinea din context și include-le pe toate, inclusiv cele nediscutate.
- Dacă în context nu există acțiuni deschise, returnează `{"stadiu_actiuni": []}`.
