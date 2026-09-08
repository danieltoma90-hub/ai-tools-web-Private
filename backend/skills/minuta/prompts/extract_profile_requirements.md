# Prompt: Profil beneficiar, cerințe exprimate și puncte deschise

Extragi din transcript trei lucruri pe care restul minutei nu le acoperă: cine este
beneficiarul, ce a cerut explicit, și ce a rămas nerezolvat.

## Output

JSON valid, fără markdown fence:

```json
{
  "profil_beneficiar": [
    {"aspect": "Domeniu de activitate", "detaliu": "..."},
    {"aspect": "Specificul producției", "detaliu": "..."}
  ],
  "cerinte_beneficiar": [
    {"zona": "Blocaj campanie", "cerinta": "Echipamentele dintr-o campanie să nu poată fi alocate altei comenzi până la finalizare."}
  ],
  "puncte_deschise": [
    "Cuanta de timp în programare (10 sau 15 minute): de decis la testare, în funcție de performanță."
  ]
}
```

## 1. Profilul beneficiarului

Portretul firmei client, așa cum reiese din ce a povestit ea despre sine. Aspecte
utile (folosește-le doar pe cele despre care s-a vorbit efectiv):
domeniu de activitate · specificul producției/activității · structura (linii, locații,
depozite) · volume și resurse (număr de angajați, ore/zi, capacități) · sisteme
existente cu care se integrează · cerința principală care a motivat proiectul.

Between 3 și 8 rânduri. `detaliu` e concret, cu cifre acolo unde s-au spus.
Dacă transcriptul nu conține informații despre firmă, returnează listă goală.

## 2. Cerințe exprimate de beneficiar

Ce a cerut clientul EXPLICIT să facă sistemul — formulări de tipul „avem nevoie să…",
„ar trebui ca sistemul să…", „vrem ca…", „este obligatoriu să…".

- `zona` = aria funcțională, 2-4 cuvinte („Raportare mobilă", „Codificare lot")
- `cerinta` = cerința reformulată clar, la persoana a III-a, o singură propoziție
- Doar cerințe ale BENEFICIARULUI, nu propuneri ale consultantului
- Nu include aici deciziile deja agreate (acelea aparțin secțiunilor de conținut)
- Maximum 12 rânduri, cele mai importante

## 3. Puncte rămase deschise

Ce NU s-a hotărât: întrebări fără răspuns, variante între care nu s-a ales, lucruri
amânate pentru altă discuție sau pentru faza de testare.

- O propoziție per punct, cu ce anume trebuie decis și de ce depinde decizia
- Distincția față de „pași următori": aici stau **întrebările deschise**; acolo stau
  **sarcinile atribuite cuiva**. Dacă are responsabil și e clar ce trebuie făcut, e pas următor, nu punct deschis.
- Maximum 10 puncte
- Dacă totul s-a tranșat, returnează listă goală

## Reguli generale

Scrie în română cu diacritice. Nu inventa: fiecare rând trebuie să aibă acoperire în
transcript. Mai bine o listă mai scurtă decât una completată cu presupuneri.
