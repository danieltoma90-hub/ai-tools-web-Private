# -*- coding: utf-8 -*-
"""Catalogul standard de training CORE.

Orele sunt EFORTUL DE REFERINTA pentru acoperirea completa a modulului, la
ritm normal. Planificatorul le scaleaza dupa numarul de zile cerut (vezi
scheduler.py) — aici stau proportiile, nu durata finala.

Continutul CORE provine din agenda reala de scolarizare folosita la client
(3 zile, 7 module) si din manualele Charisma CORE. Denumirile de documente
sunt cele din sistem — nu se inventeaza.
"""

# Profiluri de audienta — sugereaza cine sa participe la fiecare modul
A_TOTI = "Toți utilizatorii"
A_DEPOZIT = "Gestionari, operatori depozit"
A_ACHIZ = "Achiziții, aprovizionare"
A_VANZ = "Vânzări, facturare"
A_FIN = "Financiar, casierie"
A_CONTA = "Contabilitate"
A_PROD = "Operatori producție, maiștri"
A_PLAN = "Planificare, programare producție"
A_CALITATE = "Calitate, laborator"

# Modulele de baza raman in plan chiar si la o durata foarte scurta: fara
# navigare si nomenclatoare, restul modulelor nu pot fi predate.
CORE = [
    {
        "nr": 1,
        "nume": "Modul General (Informații Generale)",
        "ore": 3.5,
        "audienta": A_TOTI,
        "esential": True,
        "grupe": [
            ("Introducere în sistem", [
                "Structura sistemului, prezentare sumară module, accesul în sistem",
                "Stări ale documentelor și implicațiile acestora în operațional și contabilitate",
                "Modalități de înregistrare a documentelor — tranzacții (manuale/automate)",
            ]),
            ("Nomenclator Articole", [
                "Câmpuri obligatorii (Cod, Denumire, TVA, Tip, U.M.) + Denumire scurtă, bifa Stocabil, bifa Compus",
                "Proprietăți obligatorii de stoc, neobligatorii, atribut",
                "Set U.M. și configurare stoc",
                "Conturi contabile, taxe asociate, coduri de bare",
                "Raportarea UE, clasificare mijloace fixe, catalog de articole",
            ]),
            ("Liste de prețuri, Persoane, Parteneri", [
                "Liste de prețuri: configurare și valabilitate",
                "Persoane: adăugare persoane noi (angajați)",
                "Parteneri — câmpuri obligatorii (Cod, Denumire, Tip, Stare, Cod fiscal, Locație)",
                "Parteneri — taburi: Locații, Persoane de contact, Telefoane, Conturi bancare",
                "Detalii plăți, Credit control, Proprietăți (document sau articol)",
            ]),
            ("Configurare organizatorică", [
                "Dicționare și rolul lor în sistem",
                "Metoda de descărcare a gestiunii",
                "Locații și semnificația lor",
                "Gestiuni (gestiuni, departamente, celule)",
                "Dimensiuni de analiză, cursuri valutare",
            ]),
        ],
    },
    {
        "nr": 2,
        "nume": "Modul Depozit",
        "ore": 2.5,
        "audienta": A_DEPOZIT,
        "esential": True,
        "grupe": [
            ("Configurări gestiuni și mișcări de bază", [
                "Configurări specifice gestiunilor (celule, departamente, gestiuni)",
                "Notă de transfer",
                "Notă de predare",
                "Fișa de magazie",
            ]),
            ("Consumuri, restituiri și casare", [
                "Bon consum materiale",
                "Bon de restituire materiale",
                "Notă de casare",
            ]),
            ("Inventar și corecții de stoc", [
                "Inventar de numărare",
                "Proces verbal diferențe inventar numărare",
                "Proces verbal de corecție stoc",
            ]),
            ("Obiecte de inventar și procesare stoc", [
                "Bon de consum obiecte de inventar",
                "Bon de restituire obiecte de inventar",
                "Proces verbal de scoatere din uz obiecte de inventar",
                "Procesare stoc",
            ]),
        ],
    },
    {
        "nr": 3,
        "nume": "Modul Achiziții",
        "ore": 2.5,
        "audienta": A_ACHIZ,
        "esential": True,
        "grupe": [
            ("Prezentare modul și flux intern", [
                "Prezentare modul Achiziții",
                "Necesar aprovizionare > Comandă furnizor > Confirmare comandă furnizor",
                "Confirmare comandă > Aviz > NIR > Factură",
                "Confirmare comandă > Factură > NIR",
            ]),
            ("Achiziții externe (UE)", [
                "Confirmare comandă > Factură proformă (aviz extern) > NIR > Factură de import",
                "Confirmare comandă > Factură de import > NIR",
            ]),
            ("Achiziții din import (extra-UE)", [
                "Necesar aprovizionare > Comandă furnizor > Confirmare comandă > Factură > DVI > NIR",
            ]),
            ("Fluxuri de retur", [
                "Emitere Aviz retur de aprovizionare > Factură storno",
                "Emitere Factură de aprovizionare > NIR > Factură storno de aprovizionare",
            ]),
        ],
    },
    {
        "nr": 4,
        "nume": "Modul Vânzări",
        "ore": 2.0,
        "audienta": A_VANZ,
        "esential": True,
        "grupe": [
            ("Prezentare modul și liste de prețuri", [
                "Prezentare modul Vânzări",
                "Definire liste preț de vânzare",
            ]),
            ("Vânzări interne", [
                "Aviz de expediție",
                "Factură de vânzare",
                "Aviz de expediție retur",
            ]),
            ("Vânzări externe și custodie", [
                "Factură de export",
                "Flux mărfuri trimise în custodie la terți",
            ]),
            ("Fluxuri de retur, rapoarte și tipărituri", [
                "Aviz de vânzare > Factură de vânzare > Aviz retur de vânzare > Factură storno de vânzare",
                "Emitere aviz de retur > NIR > Factură storno",
                "Factură de vânzare > Factură storno de vânzare",
                "Rapoarte; tipărire aviz de vânzare / aviz intern / factură de export — Standard",
            ]),
        ],
    },
    {
        "nr": 5,
        "nume": "Modul Financiar",
        "ore": 1.5,
        "audienta": A_FIN,
        "esential": False,
        "grupe": [
            ("Încasări, plăți, casă și bancă", [
                "Prezentare modul financiar",
                "Definire casierii, bănci și conturi, asociere cont bancar-bancă",
                "Înregistrare încasări de la parteneri",
                "Înregistrare plăți către parteneri",
                "Operații cu casa și operații cu banca",
            ]),
            ("Deconturi, reglări, compensări și rapoarte", [
                "Deconturi (dispoziție de plată avans spre decontare, decont, dispoziție de încasare rest avans)",
                "Datorii și creanțe diverse — dispoziție de plată/încasare diverse",
                "Notă de reglare, închidere avansuri, compensări între facturi",
                "Reevaluare creanțe și datorii în valută (facturi furnizori/clienți)",
                "Rapoarte: facturi și plăți asociate, documente financiare partener, facturi neplătite/neîncasate",
            ]),
        ],
    },
    {
        "nr": 6,
        "nume": "Modul Mijloace Fixe",
        "ore": 2.0,
        "audienta": A_CONTA,
        "esential": False,
        "grupe": [
            ("Intrări și procese verbale", [
                "Înregistrarea intrării mijloacelor fixe",
                "PV-uri: de recepție, de punere în funcțiune, de reevaluare, de creștere/diminuare a valorii",
                "Bon de mișcare mijloace fixe; PV de conservare, de repunere în funcțiune",
                "PV de scoatere din uz (de casare), PV de corecție",
            ]),
            ("Amortizare, ieșiri și rapoarte", [
                "Fișa de amortizare lunară",
                "Emitere factură de vânzare mijloace fixe",
                "Emitere factură de export mijloace fixe",
                "Înregistrare factură storno de achiziție mijloace fixe",
                "Rapoarte: raport mijloace fixe, registrul numerelor de inventar",
            ]),
        ],
    },
    {
        "nr": 7,
        "nume": "Modul Contabilitate",
        "ore": 3.0,
        "audienta": A_CONTA,
        "esential": False,
        "grupe": [
            ("Configurare contabilă de bază", [
                "Exerciții financiare, sisteme contabile",
                "Plan de conturi (și mapări)",
                "Abordări contabile în Charisma: plan de conturi utilizat, modele de contare, tipuri de articole / conturi asociate",
            ]),
            ("Note contabile și regimuri speciale", [
                "Note contabile din documente primare",
                "Note contabile manuale",
                "TVA la încasare — operațiuni specifice de retratare a facturilor de vânzare și achiziție",
                "Cheltuieli parțial deductibile",
            ]),
            ("Operațiuni periodice și închiderea perioadei", [
                "Urmărire cheltuieli / venituri în avans",
                "Operațiuni periodice (închiderea conturilor de TVA, a veniturilor, cheltuielilor, reevaluarea disponibilităților în valută)",
                "Operații / verificări lunare",
                "Închiderea operațională și contabilă a perioadei",
                "Bilet la ordin în afara bilanțului; alte garanții ce nu se regăsesc pe factură",
                "Rapoarte specifice",
            ]),
        ],
    },
]

# Doar CORE are catalog. Productia NU are unul si nu trebuie sa capete: fiecare
# implementare are alte entitati tehnologice, alte retete si alt mod de
# raportare, iar un „standard de productie" scris aici ar ajunge predat unui
# client care nu il are. Agenda de productie se ridica din specificatie —
# vezi skills/training/spec_build.py.
CATALOGS = {"core": CORE}

LABELS = {
    "core": "Charisma ERP CORE",
    "productie": "Charisma ERP — Modul Producție",
}


def get_catalog(tip: str) -> list[dict]:
    if tip not in CATALOGS:
        raise ValueError(f"Nu există catalog standard pentru: {tip!r}")
    # copie adanca superficiala: planificatorul modifica orele, catalogul ramane intact
    return [dict(m, grupe=list(m["grupe"])) for m in CATALOGS[tip]]


def ore_referinta(tip: str) -> float:
    return sum(m["ore"] for m in CATALOGS[tip])
