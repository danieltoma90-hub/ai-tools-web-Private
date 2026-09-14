# -*- coding: utf-8 -*-
"""Conținutul standard Charisma ERP CORE, ca date.

Sursă unică de adevăr, consumată de:
  - skills/scop-core-capitol/  — produce capitolul standard pentru un document de verticală
  - skills/document-scop-core/ — produce documentul de ofertă complet

Modulul NU importă python-docx. Este date + validare, testabil fără Word.

Regulă: denumirile de tranzacții și module se extrag din manualele CORE
(docs/erp_training/surse/) — nu se inventează.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Flux:
    """Un flux operațional acoperit de implementare. Un flux = un rând de tabel."""
    cod: str          # "C1"; prefixul trebuie să fie cel al secțiunii
    flux: str         # denumirea fluxului; variantele multiple separate prin " / "
    presupune: str    # ce presupune concret, cu denumiri reale din manual


@dataclass(frozen=True)
class Beneficiu:
    titlu: str
    text: str


@dataclass(frozen=True)
class Grup:
    """Un grup de puncte de detaliere sub un sub-titlu propriu."""
    titlu: str
    puncte: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Sectiune:
    cheie: str                      # "contabilitate" — folosită de --fara / --doar
    titlu: str                      # "Modulul Contabilitate"
    prefix: str                     # "C" — prefixul codurilor de flux
    scop: str
    functionalitate: str
    beneficii: list[Beneficiu] = field(default_factory=list)
    detaliere: list[str] = field(default_factory=list)
    grupe: list[Grup] = field(default_factory=list)
    fluxuri: list[Flux] = field(default_factory=list)


SECTIUNI: list[Sectiune] = [
    Sectiune(
        cheie="configurare",
        titlu="Configurare inițială a sistemului",
        prefix="CF",
        scop=(
            "Înainte de operarea propriu-zisă, sistemul se configurează pe specificul organizației."
        ),
        functionalitate=(
            "Configurarea inițială reprezintă baza pe care se așază toate fluxurile operaționale "
            "ale sistemului."
        ),
        beneficii=[],
        detaliere=[
            "Datele societății și ale locațiilor (puncte de lucru, gestiuni, structura organizatorică).",
            "Definirea utilizatorilor, a grupurilor de drepturi și a politicilor de securitate (reguli de complexitate a parolelor).",
            "Cursurile valutare — preluate automat de pe site-ul BNR sau introduse manual, cu blocarea documentelor în valută pentru care nu există curs definit.",
            "Centrele de cost pentru alocarea veniturilor și a cheltuielilor.",
            "Clasificările (ierarhiile) de articole și de parteneri, folosite în operare și în raportare.",
            "Configurările strict contabile — sisteme contabile, perioade, cote de TVA și modele de contare — sunt detaliate la modulul Contabilitate.",
        ],
        fluxuri=[
            Flux("CF1", "Definire societate și structură organizatorică",
                 "Completarea datelor de identificare ale societății, a locațiilor și a "
                 "conturilor în bănci prin Configurare societate — Date societate, și "
                 "definirea structurii interne prin Departamente."),
            Flux("CF2", "Utilizatori, grupuri de utilizatori și reguli de parole",
                 "Crearea utilizatorilor Charisma, asociați cu o persoană din nomenclator, "
                 "gruparea lor pentru gestionarea unitară a drepturilor de acces prin "
                 "Grupuri de utilizatori, și definirea politicii de complexitate a "
                 "parolelor prin Reguli de definire parole, toate din Administrare — "
                 "Configurare drepturi."),
            Flux("CF3", "Cursuri valutare și valute de lucru",
                 "Definirea valutelor utilizate și preluarea automată a cursului valutar zilnic "
                 "de pe site-ul BNR prin Cursuri valutare, cu istoric păstrat pentru "
                 "reevaluările și diferențele de curs ulterioare."),
            Flux("CF4", "Centre de cost și clasificări de articole și parteneri",
                 "Definirea centrelor de cost — pe departamente, contracte, proiecte, agenți "
                 "de vânzări sau alte structuri interne — prin Centre de cost, și organizarea "
                 "articolelor și partenerilor în ierarhii de clasificare prin Clasificări, "
                 "folosite ulterior în operare și în raportare."),
        ],
    ),
    Sectiune(
        cheie="nomenclatoare",
        titlu="Modul General — Nomenclatoare și structuri de bază",
        prefix="N",
        scop=(
            "Nomenclatoarele reprezintă fundația soluției: se configurează în orice implementare "
            "CORE și, fără ele, fluxurile operaționale descrise mai jos nu pot funcționa."
        ),
        functionalitate="Modulul General oferă nomenclatoarele și structurile de bază ale sistemului.",
        beneficii=[],
        detaliere=[],
        grupe=[
            Grup(
                titlu="Catalogul de articole",
                puncte=[
                    "Crearea articolelor pe tipuri (produs finit, materie primă, semifabricat, serviciu fără stoc), cu codificare automată sau manuală și verificarea unicității codului.",
                    "Unități de măsură multiple și duale (bază + alternativă), cu conversie automată.",
                    "Caracteristici și proprietăți extinse pe articol, asocierea cataloagelor de furnizor și importul articolelor din Excel.",
                ],
            ),
            Grup(
                titlu="Partenerii (clienți și furnizori)",
                puncte=[
                    "Crearea partenerilor cu date fiscale complete și validarea stării de plătitor de TVA la ANAF.",
                    "Conturi bancare și persoane de contact asociate partenerului; definirea băncilor și a conturilor proprii.",
                    "Credit control: blocare sau avertizare la depășirea limitei de credit ori a numărului de zile de întârziere.",
                ],
            ),
            Grup(
                titlu="Listele de prețuri",
                puncte=[
                    "Creare manuală sau import din Excel, cu intervale de valabilitate.",
                    "Generarea automată din contract și actualizarea prin act adițional.",
                    "Liste de prețuri distincte pentru intrare și pentru ieșire; verificarea aplicării corecte a prețului pe documente.",
                ],
            ),
            Grup(
                titlu="Codurile de bare",
                puncte=[
                    "Generarea automată a codului de bare la crearea articolului, cu verificarea unicității.",
                    "Tipărirea etichetelor (cu denumire și caracteristici) și scanarea la recepție.",
                    "Asocierea codurilor de bare de furnizor la articolul intern.",
                ],
            ),
        ],
        fluxuri=[
            Flux("N1", "Catalog de articole",
                 "Definirea articolelor cu tip, unități de măsură și seturi de conversie, "
                 "proprietăți, conturi contabile, furnizori și coduri de bare, prin Articole și "
                 "Catalog articole, inclusiv relațiile dintre articole și articolele componente."),
            Flux("N2", "Nomenclator de parteneri",
                 "Definirea clienților și furnizorilor cu locații, persoane de contact, conturi "
                 "în bănci, domenii de activitate și detalii de plată, prin Parteneri, cu "
                 "validarea plătitorului de TVA și configurarea de credit control."),
            Flux("N3", "Liste de prețuri",
                 "Crearea listelor de prețuri de intrare și de ieșire prin Liste de prețuri, cu "
                 "interval de valabilitate, tip de listă și listă implicită pe fiecare tip; o "
                 "listă nouă se poate genera prin copierea unei liste de referință existente, cu "
                 "aplicarea unui factor de conversie a prețului."),
            Flux("N4", "Coduri de bare",
                 "Generarea codului de bare la crearea articolului, automată printr-un generator "
                 "predefinit sau introdusă manual, cu verificarea unicității în sistem; un "
                 "articol poate avea mai multe coduri de bare, pentru unități de măsură "
                 "alternative sau pentru furnizori diferiți, tipărite pe etichetă și scanate la "
                 "recepție."),
        ],
    ),
    Sectiune(
        cheie="contabilitate",
        titlu="Modulul Contabilitate",
        prefix="C",
        scop=(
            "Modulul adună datele din toate modulele operaționale ale sistemului Charisma ERP și le "
            "integrează într-o formă contabilă."
        ),
        functionalitate=(
            "Indiferent de structura, dimensiunea, cadrul internațional, limba, moneda sau planul de "
            "conturi ale companiei, furnizează centralizat date financiar-contabile și informații "
            "esențiale despre poziția economică și evoluția performanței financiare în timp."
        ),
        beneficii=[
            Beneficiu(
                "Reduce costurile operaționale",
                "Datorită reducerii timpului și a resurselor umane necesare integrării proceselor de "
                "afaceri la nivel de organizație, modulul Contabilitate reduce semnificativ costurile "
                "operaționale și îmbunătățește coordonarea la nivelul departamentelor.",
            ),
        ],
        detaliere=[
            "Management în paralel al mai multor locații sau societăți, părți ale unui holding, chiar independente.",
            "Grad înalt de configurabilitate: planuri de conturi pe fiecare sistem contabil, centre de cost, modele de contare pe fiecare tranzacție operațională, clasificări de conturi, cote de TVA.",
            "Definirea exercițiilor financiare și a perioadelor contabile, cu închiderea perioadelor la nivel de perioadă și sistem contabil.",
            "Funcționare multi-valută, cu tratamentul specific fiecărui cont (monetar / nemonetar).",
            "Contarea automată a documentelor operaționale, disponibilă instantaneu în rapoartele contabile și în rulajele conturilor; note contabile manuale pentru situații speciale.",
            "Atașarea mai multor dimensiuni de analiză (departamente, proiecte, contracte) pe fiecare notă contabilă, cu rapoarte filtrate pe aceste dimensiuni.",
            "Rapoarte legale și uzuale: Registru jurnal, Carte mare, Cartea mare-șah, Fișe de cont (multi-perioadă, multi-valută), Jurnal de vânzări / cumpărări, Declarațiile 300, 390, 394, Intrastat, Balanța configurabilă.",
        ],
        fluxuri=[
            Flux("C1", "Definire și management Plan de Conturi",
                 "Definirea structurii pe clase, grupe și conturi sintetice și analitice, cu "
                 "tipul și funcția contabilă a fiecărui cont, prin Plan de conturi. Structura "
                 "susține sisteme contabile paralele, fiecare cu planul său."),
            Flux("C2", "Definire perioade contabile și management stare perioadă (închidere operațională / închidere contabilă)",
                 "Configurarea exercițiilor și lunilor contabile prin Perioade contabile, apoi "
                 "gestionarea stării fiecărei luni — deschisă, închisă operațional (nu se mai "
                 "introduc documente primare) sau închisă contabil (nu se mai introduc nici note "
                 "contabile manuale) — prin Stare perioade contabile, cu marcarea Perioadei raportate."),
            Flux("C3", "Generare note contabile din documente operaționale",
                 "Contarea automată a documentelor primare — Factură de achiziție, Factură de "
                 "vânzare, Notă de intrare-recepție, Bon de consum — pe baza modelelor de "
                 "contare configurate la inițializare, prin Generare note contabile din "
                 "documente primare. Înregistrările devin imediat vizibile în rulajele conturilor."),
            Flux("C4", "Operații periodice: închidere conturi de venit și cheltuială / închidere TVA / reevaluare disponibilități și creanțe în valută / producție în curs",
                 "Rularea, din Operațiuni periodice, a închiderilor de fine de lună — închiderea "
                 "conturilor de cheltuieli, închiderea conturilor de venituri, închiderea conturilor "
                 "de TVA și reevaluarea disponibilităților în valută — cu generare automată de note "
                 "contabile; creanțele și datoriile în valută se reevaluează separat, din Reevaluare "
                 "creanțe și datorii în valută."),
            Flux("C5", "TVA la încasare: actualizare parteneri în scopuri de TVA (ANAF) / exigibilitate facturi și plăți",
                 "Verificarea încadrării partenerilor în regimul de TVA la încasare și operarea, "
                 "în aplicația TVA la încasare (extensie a sistemului Charisma), a celor trei "
                 "documente de exigibilitate TVA — facturi, încasări/plăți și facturi peste 90 "
                 "de zile — potrivit O.G. nr. 15/2012."),
            Flux("C6", "Declarații: D300 / D390 / D394 / Intrastat",
                 "Generarea declarațiilor fiscale din rulajele perioadei, cu export în formatul "
                 "cerut de ANAF: decontul de TVA (D300), declarația recapitulativă VIES (D390), "
                 "declarația informativă (D394) și raportarea Intrastat."),
        ],
    ),
    Sectiune(
        cheie="financiar",
        titlu="Modulul Financiar",
        prefix="F",
        scop=(
            "Modulul monitorizează fluxurile de bani prezente și viitoare din cadrul companiei, pe "
            "ansamblul ei sau pe subunități componente."
        ),
        functionalitate=(
            "Integrează toate datele relevante despre circulația banilor, utilizabile pentru analiza "
            "activității anterioare și eficientizarea operațiunilor viitoare."
        ),
        beneficii=[
            Beneficiu(
                "Eficientizează operațiunile financiare",
                "Datorită posibilității automatizării generării plăților centralizat în formatul "
                "solicitat de instituțiile bancare, soluția reduce semnificativ timpul și efortul "
                "manual consumat pe introducerea datelor financiare. În plus, existența unei surse "
                "unice de informare asupra indicatorilor financiari oferă transparență asupra "
                "evoluției și performanței companiei, oferind managementului posibilitatea deciziilor "
                "proactive pentru eficientizarea operațiunilor.",
            ),
            Beneficiu(
                "Reduce costurile de exploatare",
                "Datorită controlului fluxului de bani în interiorul organizației, modulul Financiar "
                "reduce costurile cu taxele bancare și riscurile asociate, printr-o îmbunătățire și o "
                "supervizare mai bună a acestor fluxuri.",
            ),
        ],
        detaliere=[
            "Gestionarea sumelor încasate / plătite prin bancă și casă în orice valută, repartizate pe parteneri, facturi sau documente echivalente.",
            "Compensări între facturi, creanțe și datorii, multi-partener și multi-valută; reglări de facturi pentru situații speciale.",
            "Reevaluarea automată a creanțelor și datoriilor în valută, cu păstrarea cursului istoric al documentelor.",
            "Toate tipurile de documente bancare (OP, chitanță, bon fiscal, CEC, bilet la ordin, card), fiecare cu tratamentul propriu.",
            "Gestiunea avansurilor plătite / încasate, cu închidere automată a avansurilor cu facturile ulterioare.",
            "Managementul deconturilor cu angajații sau cu terți.",
            "Generarea automată a plăților scadente în formatul solicitat de bănci; preluarea automată a cursului valutar BNR.",
            "Rapoarte legale și uzuale: registre de bancă și de casă, facturi neînchise, balanțe de parteneri pe vechime, legături factură–plată, avansuri neînchise.",
        ],
        fluxuri=[
            Flux("F1", "Plăți către parteneri: chitanță numerar / ordin de plată / CEC / bilet la ordin / chitanță decont / bon fiscal",
                 "Înregistrarea plăților către furnizori prin Plăți pentru parteneri, cu documentele "
                 "Chitanță numerar, Ordin de plată, CEC și Bilet la ordin, alocate direct pe facturile "
                 "din sold; cheltuielile fără factură sursă se achită din casierie prin Bon fiscal "
                 "diverse sau Dispoziția de plată diverse."),
            Flux("F2", "Încasări de la parteneri: chitanță numerar / ordin de plată / CEC / bilet la ordin",
                 "Înregistrarea încasărilor de la clienți prin Încasări de la parteneri, cu "
                 "documentele Chitanță numerar, Ordin de plată, CEC, Bilet la ordin și Carte de "
                 "credit, alocate pe facturile din sold sau înregistrate ca avans încasat."),
            Flux("F3", "Deconturi angajați: plată avans (numerar / bancă) / justificare avansuri / încasare avansuri nejustificate / plată diferență",
                 "Acordarea unui avans spre decontare angajatului — în numerar prin Dispoziție de "
                 "plată sau prin bancă prin Ordin de plată — din Deconturi > Acordare avansuri. "
                 "Justificarea cheltuielilor se face în Deconturi angajați, prin împerecherea "
                 "avansului cu documentele decontate, iar închiderea decontului generează Dispoziția "
                 "de plată diferență avans sau Dispoziția de încasare restituire rest avans."),
            Flux("F4", "Operații cu casa: intrări numerar din bancă / depuneri numerar în bancă / încasări și plăți diverse",
                 "Înregistrarea mișcărilor de numerar fără document sursă direct pe extras, prin "
                 "ecranul Diverse sume (opțiunea Diverse încasări și plăți din Extras de cont, tip "
                 "Debit pentru plată sau Credit pentru încasare) — inclusiv ridicări sau depuneri de "
                 "numerar din/în bancă — completată de Bon fiscal diverse și Dispoziția de plată "
                 "diverse pentru cheltuielile achitate din casierie."),
            Flux("F5", "Operații cu banca: schimb valutar / transfer bancar / extras de cont",
                 "Reconcilierea operațiunilor bancare din Extras de cont (Financiar > Operații cu "
                 "bancă > Extrase de cont), prin confirmarea pe extras a documentelor de plată sau "
                 "încasare deja înregistrate (OP, CEC, BO) ori prin adăugarea lor directă, cu sumele "
                 "în valută convertite la cursul din Cursuri valutare."),
            Flux("F6", "Compensări: compensări facturi / închidere avansuri furnizori și clienți",
                 "Compensarea facturilor de la un furnizor cu facturile de vânzare către un client "
                 "care are, la rândul lui, o creanță asupra acelui furnizor, prin Compensări între "
                 "facturi, și închiderea avansurilor plătite sau încasate cu facturile aferente prin "
                 "Închidere avansuri clienți / Închidere avansuri furnizori."),
            Flux("F7", "Note de reglare: note de reglare avansuri și facturi",
                 "Închiderea resturilor de avansuri sau facturi rămase în operațional prin Note de "
                 "reglare — Facturi clienți, Facturi furnizori, Avansuri clienți, Avansuri furnizori "
                 "— cu opțiunea de a reflecta sau nu suma în contabilitate; realocările de încasări/"
                 "plăți din luni închise se tratează separat, prin Realocare facturi."),
            Flux("F8", "Reevaluări financiare: reevaluări avansuri și facturi",
                 "Reevaluarea la cursul de închidere a facturilor de la furnizori și clienți, "
                 "respectiv a avansurilor primite și acordate, altele decât cele în RON, prin "
                 "Reevaluare creanțe și datorii în valută (Facturi de furnizori și clienți / "
                 "Avansuri de furnizori și clienți), cu diferența de curs evidențiată ca venit sau "
                 "cheltuială."),
        ],
    ),
    Sectiune(
        cheie="vanzari",
        titlu="Modulul Vânzări",
        prefix="V",
        scop="Modulul gestionează corect și eficient activitățile de vânzare specifice companiei.",
        functionalitate=(
            "Cererile de ofertă, ofertele, comenzile, facturile, avizele, campaniile de discount și "
            "promoții, tipurile de clienți, zonele de vânzare și de livrare."
        ),
        beneficii=[
            Beneficiu(
                "Îmbunătățește relația cu clienții",
                "Datorită evidenței unitare, complete și permanent actualizate a portofoliului de "
                "produse și servicii, a creditelor și discount-urilor oferite clienților sau a "
                "campaniilor în curs de derulare, sistemul oferă toate instrumentele necesare unei "
                "voci unice a organizației în relația cu clientul.",
            ),
            Beneficiu(
                "Sporește vânzările",
                "Prin informațiile relevante despre evoluția preferințelor de achiziție a clienților, "
                "compania va putea adresa produse și servicii orientate spre a satisface aceste "
                "preferințe, susținând creșterea vânzărilor, dar și satisfacția și loialitatea "
                "clienților.",
            ),
            Beneficiu(
                "Reduce costurile și sporește productivitatea angajaților",
                "Datorită unei baze unice de date, disponibile și accesibile în orice moment, din "
                "orice loc, pe baza unor reguli de acces conforme cu politica internă a organizației, "
                "sistemul elimină munca redundantă, reducând costurile operaționale și sporind "
                "productivitatea angajaților.",
            ),
        ],
        detaliere=[
            "Clasificări ierarhizate multiple de clienți și de produse, pentru eficientizarea vânzării și a raportării.",
            "Fluxul complet de documente al unei vânzări (comandă client, confirmare, aviz de însoțire, factură), cu facturare în formatul specific companiei.",
            "Motor de prețuri cu grad mare de configurabilitate: discount-uri și promoții pe produs, client, termen de plată, agent, grupă de produse / clienți; liste de prețuri multiple în lei sau valută.",
            "Credit control din perspectiva datoriei și a zilelor de întârziere, cu blocare sau avertizare la preluarea comenzii.",
            "Scăderea automată a stocului pe baza configurărilor la nivel de tranzacție; funcționalitatea de rezervare stoc (opțională).",
            "Operații automate: facturi din avize, avize din confirmări de comandă; vânzare în mai multe unități de măsură și împachetări.",
            "Sistem puternic de rapoarte de vânzări, operaționale și manageriale (pe clienți, articole, perioade, agenți, zone).",
        ],
        fluxuri=[
            Flux("V1", "Livrări intern – Aviz de expediție: Comandă client → Aviz de expediție → Factură de vânzare",
                 "Înregistrarea Comenzii client (Vânzări > Comandă client), cu interpunerea opțională "
                 "a Confirmării comenzii client, generarea Avizului de expediție cu scădere de stoc "
                 "prin tranzacția Generare Aviz de Expediție de Vânzare din Confirmare Comandă Client "
                 "și facturarea ulterioară prin Generare Factură de Vânzare din Aviz de Expediție de "
                 "Vânzare, fără scădere de stoc suplimentară."),
            Flux("V2", "Livrări intern – Factură de vânzare: Comandă client → Factură de vânzare",
                 "Facturarea directă a Comenzii client, fără Aviz de expediție intermediar, prin "
                 "tranzacția Emitere Factură de Vânzare în Rate, cu scădere de stoc pe factură — spre "
                 "deosebire de fluxul cu aviz, unde scăderea de stoc are loc deja la expediere și "
                 "factura ulterioară nu mai afectează stocul."),
            Flux("V3", "Livrări externe – Factură de export: înregistrare Factură de export",
                 "Înregistrarea Facturii de export (Vânzări > Export > Facturi de export), cu "
                 "completarea câmpurilor specifice operațiunii externe — Tip livrare, Condiții "
                 "livrare, Tip transport, Natura tranzacției, monedă și curs valutar — și scăderea "
                 "de stoc direct pe factură, la validare."),
            Flux("V4", "Retururi și corecții: retur de vânzare / factură storno de vânzare",
                 "Preluarea articolelor returnate de client prin Avizul de expediție retur — cu "
                 "intrare în stoc, fără efect financiar — generat, de regulă, din Avizul de expediție "
                 "de vânzare inițial, urmat de Factura storno de vânzare generată din acesta (sau "
                 "direct din Factura de vânzare, dacă avizul retur lipsește), care stinge total sau "
                 "parțial datoria clientului."),
        ],
    ),
    Sectiune(
        cheie="achizitii",
        titlu="Modulul Achiziții",
        prefix="A",
        scop="Modulul monitorizează și controlează procesele de aprovizionare.",
        functionalitate=(
            "De la cererea de achiziționare a unui articol până la intrarea în gestiune a "
            "articolelor achiziționate — automatizând și optimizând întregul ciclu."
        ),
        beneficii=[
            Beneficiu(
                "Creșterea productivității angajaților",
                "Datorită flexibilității și configurabilității excepționale a modulului, sistemul "
                "generează automat necesarul de aprovizionare pe baza unor algoritmi specifici "
                "companiei, asigură trasabilitatea documentelor și alocă automat cheltuielile pe "
                "centre de cost, optimizând activitățile procesului de achiziție și degrevând "
                "angajații de activitățile redundante, consumatoare de timp.",
            ),
            Beneficiu(
                "Reducerea costurilor de analiză",
                "Modulul Achiziții oferă o transparență totală asupra proceselor de aprovizionare și "
                "achiziții, generând rapoarte în timp real conform nevoilor fiecărui client în parte.",
            ),
            Beneficiu(
                "Îmbunătățește puterea de cumpărare",
                "Sistemul oferă o imagine actualizată și unitară a oportunităților de negociere, a "
                "informațiilor și balanțelor conturilor partenerilor de business, fiind un punct de "
                "sprijin important în procesul de negociere cu terți furnizori.",
            ),
        ],
        detaliere=[
            "Liste de furnizori agreați pe produse / tipuri de produse, cu constrângeri de utilizare în comenzile de achiziție.",
            "Date detaliate despre articole, taxe și liste de prețuri, multi-valută și multi-discount; urmărire după cataloage interne și ale furnizorilor.",
            "Fluxul complet de documente al unei achiziții (necesar de aprovizionare, comandă, factură, proformă), cu toate legăturile dintre ele și cu proces de aprobare.",
            "Recepția și/sau inspecția bunurilor, cu trasabilitate; generarea automată a procesului-verbal de constatare a diferențelor; recepție pe loturi sau serii, inclusiv articole echivalente.",
            "Recepție în zonă tampon, în depozit sau spre vânzare; recepția articolelor fără comandă, cu alocare ulterioară.",
            "Încărcarea cheltuielilor pe centre de cost și trasabilitatea completă a documentelor de aprovizionare.",
        ],
        fluxuri=[
            Flux("A1", "Achiziții intern – Aviz de expediție: Comandă → Aviz de însoțire → NIR; înregistrare Aviz → NIR; Aviz → retur de aprovizionare",
                 "Emiterea Comenzii furnizor (Achiziții > Comenzi) și generarea Avizului de însoțire "
                 "de achiziție din comandă, prin tranzacția Generare Aviz de Aprovizionare din "
                 "Comandă Furnizor; avizul validat devine document sursă pentru Nota de "
                 "intrare-recepție și, la nevoie, pentru Avizul retur către furnizor, generat cu "
                 "scădere de stoc din avizul de însoțire."),
            Flux("A2", "Achiziții intern – Factură de aprovizionare: Comandă → Factură → NIR; înregistrare Factură → NIR; storno de aprovizionare",
                 "Generarea Facturii de achiziție din Comanda furnizor prin tranzacția Generare "
                 "Factură de Aprovizionare din Comandă Furnizor, cu ajustarea cantităților sau "
                 "prețurilor dacă recepția a constatat diferențe, urmată de Nota de intrare-recepție "
                 "generată din factură; corecțiile ulterioare se fac prin Factură storno de "
                 "aprovizionare, generată din factura de achiziție, cu scădere de stoc."),
            Flux("A3", "Achiziții intern – Diferențe la recepție: proces-verbal diferențe (plus / minus) → aviz retur furnizor / factură / storno",
                 "Consemnarea diferențelor constatate la recepție prin Proces verbal de diferențe, "
                 "generat din Nota de intrare-recepție cu indicarea sensului diferenței; diferențele "
                 "în plus generează Aviz retur către furnizor din PVD, iar cele în minus generează "
                 "Factură storno de aprovizionare din PVD, ambele cu scădere de stoc."),
            Flux("A4", "Achiziții de servicii: înregistrare factură de aprovizionare (ex. utilități)",
                 "Înregistrarea manuală a Facturii de servicii, prin Achiziții > Facturi > Facturi "
                 "de achiziție, tranzacția Înregistrare Factură de Aprovizionare, fără notă de "
                 "intrare-recepție, cu articol de tip serviciu sau cheltuială — de exemplu utilități "
                 "— și cantitate 1."),
            Flux("A5", "Achiziții externe – Factură de import: Factură de import → DVI → NIR; storno de import",
                 "Înregistrarea manuală a Facturii de import (Achiziții > Facturi > Facturi de "
                 "achiziție, tranzacția Înregistrare Factură de Import) ca prim document al fluxului, "
                 "cu dată, curs valutar și articole aliniate codurilor vamale definite; Nota de "
                 "intrare-recepție se generează ulterior din factură și din Declarația vamală de "
                 "import, iar corecțiile se fac prin Factură storno de aprovizionare, cu sau fără "
                 "scădere de stoc."),
            Flux("A6", "Achiziții externe – Declarație vamală de import (DVI): Comandă → Factură de import → DVI → NIR; storno de import",
                 "Generarea Declarației vamale de import din Factura de import, prin tranzacția "
                 "Generare DVI din Factura de import, cu preluarea Facturilor auxiliare (transport, "
                 "asigurare, comision vamal) și calculul bazei de impozitare, taxei vamale și TVA pe "
                 "coduri vamale; Nota de intrare-recepție se generează apoi din Factura de import cu "
                 "DVI și Factura de transport, iar corecțiile ulterioare se fac prin factură storno."),
        ],
    ),
    Sectiune(
        cheie="mijloace-fixe",
        titlu="Modulul Mijloace Fixe",
        prefix="MF",
        scop="Modulul oferă o imagine unitară asupra imobilizărilor deținute de companie.",
        functionalitate=(
            "Alocări, cantități, locații, întreținere și depreciere — asigurând urmărirea corectă a "
            "imobilizărilor corporale (mijloace fixe și obiecte de inventar) și necorporale "
            "amortizabile (programe, licențe, brevete, mărci)."
        ),
        beneficii=[
            Beneficiu(
                "Reduce cheltuielile",
                "Datorită centralizării tuturor informațiilor referitoare la mijloacele fixe într-o "
                "bază unică de date, sistemul previne pierderile sau „rătăcirile” mijloacelor fixe și "
                "îmbunătățește semnificativ întreținerea activelor companiei. În plus, sistemul "
                "diminuează rata de achiziționare de echipamente noi sau inutile, printr-o gestiune "
                "corectă a mijloacelor fixe disponibile în anumite locații și nefolosite în diverse "
                "operațiuni.",
            ),
            Beneficiu(
                "Reduce volumul activităților consumatoare de timp",
                "Datorită accesului rapid la informații, pe baza unor reguli de securitate internă, "
                "personalul calificat poate obține imediat situații la zi despre valoarea activelor "
                "companiei, dar și alte informații relevante predefinite în sistem și afișate prin "
                "intermediul unor rapoarte complete. În plus, modulul Imobilizări calculează "
                "cheltuielile cu amortizarea pe baza planurilor de amortizare pentru toate metodele "
                "folosite în România, reducând erorile umane.",
            ),
        ],
        detaliere=[
            "Gestiunea imobilizărilor corporale și necorporale, pe baza fișei mijlocului fix, cu amortizări lunare și cumulate.",
            "Clase și grupuri de mijloace fixe cu caracteristici comune; acoperirea tuturor schimbărilor logistice, de valoare și de amortizare.",
            "Sisteme multiple de amortizare (liniar, accelerat, degresiv, degresiv cu uzură morală etc.), urmărite în paralel.",
            "Modificări de structură, creșteri / diminuări de valoare, de locație și de centru de cost; reevaluări pe baze legale sau politici de firmă.",
            "Istoricul complet al modificărilor pe durata de viață a mijlocului fix; Registrul Mijloacelor Fixe.",
            "Rapoarte legale și uzuale (jurnale de amortizare, lista numerelor de inventar).",
        ],
        fluxuri=[
            Flux("MF1", "Intrări imobilizări: factură / proces-verbal de recepție",
                 "Deschiderea Fișei mijlocului fix (Mijloace fixe > Fișa mijlocului fix) pe baza "
                 "documentului de intrare — Factura de achiziție sau, în lipsa acesteia, Procesul "
                 "verbal de recepție mijloace fixe — din care se preiau mijlocul fix, numărul de "
                 "inventar, seria și identificatorul, completate cu departamentul, responsabilul, "
                 "centrul de cost și modul de obținere."),
            Flux("MF2", "Gestiune imobilizări: activare, conservare / reactivare, reevaluare, modificări de valoare, corecții, mișcări interne și între sucursale",
                 "Activarea mijlocului fix prin Procesul verbal de punere în funcțiune, generat din "
                 "Fișa mijlocului fix, declanșează calculul amortizării; conservarea/repunerea în "
                 "funcțiune schimbă starea între Activ și Inactiv, reevaluarea (procent, valoare "
                 "nouă sau capitalizare de cheltuieli) și creșterea/diminuarea valorii ajustează "
                 "valoarea de inventar, iar Procesul verbal de corecție și Bonul de mișcare "
                 "actualizează centrul de cost, departamentul, responsabilul sau locația."),
            Flux("MF3", "Amortizare: fișă de amortizare lunară",
                 "Generarea lunară a Fișei de amortizare lunară (Mijloace fixe > Fișa de amortizare "
                 "lunară), cu antet pe număr, dată de sfârșit de lună și sistem contabil; opțiunea "
                 "Preluare amortizare din meniul Acțiuni populează automat lista cu toate mijloacele "
                 "fixe active din luna respectivă, iar validarea generează nota contabilă cu "
                 "cheltuiala lunară de amortizare."),
            Flux("MF4", "Ieșire imobilizări: factură de vânzare / factură de export / casare",
                 "Vânzarea mijlocului fix prin Factura de vânzare a mijloacelor fixe (Vânzări > "
                 "Facturi > Facturi de vânzare a mijloacelor fixe), cu bifarea mijlocului fix la "
                 "numărul de inventar corespunzător în zona Selecție mijloace fixe, care trece "
                 "activul în starea Vândut și calculează cheltuiala rezultată dacă vânzarea are loc "
                 "înainte de amortizarea completă; exportul, prin Factura de export mijloace fixe "
                 "(Vânzări > Export > Facturi de export mijloace fixe); casarea, prin Procesul "
                 "verbal de scoatere din uz, cu selectarea mijlocului fix și, opțional, a motivului "
                 "modificării din dicționarul Motive modificare valoare, care schimbă starea în "
                 "Casat și oprește calculul amortizării."),
        ],
    ),
    Sectiune(
        cheie="stocuri",
        titlu="Modulul Gestiunea Stocurilor",
        prefix="D",
        scop=(
            "Modulul asigură monitorizarea și administrarea eficientă a stocurilor de materii "
            "prime, materiale, produse finite și semifabricate, precum și a obiectelor de inventar, "
            "cu actualizarea la zi a stării stocurilor."
        ),
        functionalitate=(
            "Informație pe baza căreia se iau decizii de aprovizionare și se evită întreruperea "
            "proceselor de producție sau livrare."
        ),
        beneficii=[
            Beneficiu(
                "Maximizarea satisfacției clienților",
                "Datorită controlului optim al stocurilor și al integrării cu procesele de "
                "aprovizionare, soluția asigură permanent produse disponibile pe stoc, îndeplinind "
                "sau depășind așteptările clienților.",
            ),
            Beneficiu(
                "Maximizarea profitului net",
                "Datorită minimizării nivelului stocului conform cu cererea clienților și "
                "sezonalitățile specifice, soluția elimină factorii de risc și minimizează costurile "
                "de aprovizionare, logistică și transport, maximizând profitul net al organizației.",
            ),
            Beneficiu(
                "Maximizarea cotei de piață a organizației",
                "Prin eliberarea capitalului uman și financiar și prin utilizarea lui strategică în "
                "activități cu valoare adăugată mare, modulul asigură creșterea puterii de competitor "
                "în piață.",
            ),
        ],
        detaliere=[
            "Gestiune flexibilă pe niveluri: gestiune, depozit, locație de stocare; număr nelimitat de depozite.",
            "Codificare flexibilă (automată sau manuală), caracteristici extinse pe articol, coduri de bare, clasificări multiple cu ierarhii paralele.",
            "Urmărire pe loturi, serii, revizii sau proprietăți atașate; unități de măsură multiple cu conversie automată.",
            "Calculul costului stocului prin orice metodă, în paralel (FIFO, LIFO, identificare directă, CMP instantaneu, CMP global), inclusiv în valută.",
            "Toate tipurile de mișcări de stoc (intrare, ieșire, transfer, retururi, reevaluare, inventar); gestiunea stocurilor de custodie și consignație.",
            "Gestionarea în paralel a informațiilor logistice și contabile; trasabilitatea completă a stocurilor și generarea automată a documentelor conform fluxurilor predefinite.",
        ],
        fluxuri=[
            Flux("D1", "Consumuri: bon de consum / restituire bon de consum",
                 "Ieșirea materialelor din gestiune prin Bonul de consum (Depozit > Bon de consum "
                 "materiale), cu articol, cantitate solicitată și cantitate livrată, care "
                 "actualizează fișa de magazie la validare; corectarea unei ieșiri greșite se face "
                 "prin Bonul de restituire materiale, generat automat din bonul de consum inițial "
                 "sau introdus manual prin tranzacția Emitere bon de retur, cu reintrare în stoc a "
                 "cantității restituite."),
            Flux("D2", "Transferuri: între gestiuni ale aceleiași locații / între locații",
                 "Transferul articolelor între gestiuni ale aceleiași locații prin Nota de transfer "
                 "(Depozit > Nota de transfer), cu gestiune sursă, gestiune destinație și cantitatea "
                 "transferată, care descarcă stocul din gestiunea sursă și îl încarcă în cea de "
                 "destinație la validare, cu preț calculat automat la procesarea de stoc de final "
                 "de lună; transferul între locații diferite (sucursale) se face prin Avizul de "
                 "expediție intern, cu efect similar între locația sursă și cea de destinație."),
            Flux("D3", "Inventar: inventariere / corecții de stoc",
                 "Inventarierea periodică sau parțială a gestiunii prin Inventarul de numărare "
                 "(Depozit > Inventar > Inventar de numărare), cu preluarea automată a cantității "
                 "scriptice și înregistrarea manuală a cantității faptice pe articol; diferențele "
                 "constatate generează automat Procesul verbal de diferențe la inventariere, cu "
                 "impact contabil, iar corecțiile de cantitate și valoare din afara ciclului de "
                 "inventariere se operează prin Procesul verbal corecție stoc."),
            Flux("D4", "Obiecte de inventar: bon de consum și bon de restituire obiecte de inventar",
                 "Repartizarea obiectelor de inventar către angajați prin Bonul de consum obiecte "
                 "de inventar, cu gestiune sursă de depozitare, gestiune destinație de folosință, "
                 "departament și persoană, operat cu sau fără identificare individuală pe număr de "
                 "inventar; restituirea de către angajat se înregistrează prin Bonul de restituire "
                 "obiect de inventar, cu reintrare într-o gestiune de tranzit."),
            Flux("D5", "Reevaluări de stoc",
                 "Ajustarea valorii de inventar a obiectelor de inventar prin Procesul verbal de "
                 "reevaluare obiecte de inventar (Depozit > Obiecte de inventar > Proces verbal de "
                 "reevaluare obiecte de inventar), prin selectarea numărului de inventar și "
                 "introducerea noii valori dorite, fără modificarea cantității; validarea "
                 "actualizează valoarea vizibilă ulterior în Fișa obiectului de inventar."),
        ],
    ),
    Sectiune(
        cheie="analiza",
        titlu="Analiza multidimensională",
        prefix="AM",
        scop=(
            "Componenta permite gruparea informațiilor după diverse criterii de analiză și "
            "folosirea lor ulterioară în rapoarte (contabile și de tip BI)."
        ),
        functionalitate=(
            "Se pot implementa maximum 10 dimensiuni de analiză (de exemplu: departament, proiect, "
            "contract, obiectiv, persoană, utilaj)."
        ),
        beneficii=[
            Beneficiu(
                "Asigură urmărirea profitabilității",
                "Prin detalierea informației operaționale și contabile la nivel de contract/obiectiv "
                "se asigură o mai mare transparență a informației și identificarea din timp a "
                "ponderii diferitelor cheltuieli în cadrul proiectului. Se poate verifica în orice "
                "moment profitul la nivel de proiect și obiectiv direct din balanța contabilă, "
                "conform cu alocările directe pe aceste dimensiuni de analiză.",
            ),
            Beneficiu(
                "Asigură un control sporit al resurselor companiei",
                "Prin definirea unor dimensiuni specifice activității (ex: persoană, utilaj) se pot "
                "urmări costurile directe pe orice combinație de dimensiuni de analiză, informațiile "
                "fiind centralizate la acest nivel în rapoartele contabile.",
            ),
        ],
        detaliere=[
            "Alocarea manuală a detaliilor de document sau preluarea automată a alocărilor de pe documentele sursă.",
            "Generarea notelor contabile alocate pe dimensiunile de analiză.",
            "Filtrarea datelor din balanța contabilă și a rapoartelor contabile pe orice combinație de dimensiuni.",
            "Generarea balanței contabile și a fișei de cont cu detalierea pe dimensiunile de analiză configurate.",
            "Alocarea automată a dimensiunilor de analiză conform regulilor identificate în timpul analizei.",
            "Prin detalierea informației operaționale și contabile la nivel de proiect / obiectiv, componenta asigură urmărirea profitabilității și un control sporit al resurselor companiei.",
        ],
        fluxuri=[
            Flux("AM1", "Configurare sistem de analiză",
                 "Definirea unui sistem de analiză pe baza ierarhiei de centre de cost "
                 "configurate, prin Centre de cost — Sisteme de analiză, cu activarea alocării "
                 "pe documentele operaționale și setarea sistemului implicit la nivel de "
                 "parametru de inițializare."),
            Flux("AM2", "Alocare pe documente și note contabile",
                 "Alocarea procentual-valorică a documentelor operaționale pe centre de analiză "
                 "— la nivelul fiecărui detaliu de document sau identic pe toate detaliile — "
                 "prin opțiunea Alocă disponibilă direct pe document, completată de alocarea "
                 "automată pe centrul de cost asociat contului contabil din modelul de contare."),
            Flux("AM3", "Rapoarte pe dimensiuni de analiză",
                 "Filtrarea și detalierea Balanței contabile și a Fișei de cont pe centrele de "
                 "cost incluse în sistemul de analiză, pentru urmărirea veniturilor și a "
                 "cheltuielilor pe fiecare departament, contract, proiect sau altă structură "
                 "definită."),
        ],
    ),
    Sectiune(
        cheie="migrare",
        titlu="Migrarea și inițializarea datelor",
        prefix="M",
        scop=(
            "Pornirea sistemului presupune încărcarea datelor inițiale, realizată ca parte a "
            "proiectului."
        ),
        functionalitate="Migrarea pregătește sistemul cu datele inițiale necesare pornirii în producție.",
        beneficii=[],
        detaliere=[
            "Nomenclatoarele de bază: parteneri și articole (cu unități de măsură, taxe și liste de prețuri).",
            "Soldurile partenerilor: facturi în sold și avansuri la data de inițializare.",
            "Stocul inițial, pe gestiuni.",
            "Mijloacele fixe, cu amortizarea cumulată.",
            "Este inclus un singur import de inițializare. Dacă datele se transmit în mai multe tranșe, importurile ulterioare se estimează și se facturează separat. Datele se furnizează de către beneficiar în formatul agreat (șabloanele puse la dispoziție de TotalSoft).",
        ],
        fluxuri=[
            Flux("M1", "Migrarea nomenclatoarelor",
                 "Importul articolelor, partenerilor și listelor de prețuri din sistemul actual, "
                 "pe baza formatului de import pus la dispoziție, cu validarea unicității "
                 "codurilor și a corespondenței conturilor contabile."),
            Flux("M2", "Migrarea soldurilor de deschidere",
                 "Preluarea soldurilor de deschidere ale partenerilor — facturile rămase în sold "
                 "și avansurile primite sau acordate — și a stocului inițial pe gestiuni, la data "
                 "de inițializare a sistemului, cu verificarea corespondenței totalurilor cu "
                 "balanța contabilă de deschidere."),
            Flux("M3", "Migrarea mijloacelor fixe",
                 "Preluarea mijloacelor fixe existente, cu valoarea de intrare și amortizarea "
                 "cumulată la data inițializării, astfel încât calculul amortizării să continue "
                 "de unde a rămas, fără recalcul de la zero."),
        ],
    ),
]   # populat în Task 2; Task 3-6 au completat tabelul de fluxuri (cod, flux, „ce presupune”)


def valideaza(sectiuni: list[Sectiune]) -> list[str]:
    """Întoarce lista de erori de conținut. Listă goală = valid.

    O secțiune e validă cu `detaliere` SAU `grupe` (nu neapărat ambele) —
    conținutul poate fi organizat plat sau pe sub-titluri. `beneficii` gol e
    acceptat: nu orice secțiune are un beneficiu propriu documentat în sursă
    (ex. `configurare`, `nomenclatoare`, `migrare`); randarea omite blocul.
    """
    erori: list[str] = []
    chei_vazute: set[str] = set()
    coduri_vazute: set[str] = set()

    for s in sectiuni:
        if s.cheie in chei_vazute:
            erori.append(f"{s.cheie}: cheie duplicată")
        chei_vazute.add(s.cheie)

        for camp in ("titlu", "prefix", "scop", "functionalitate"):
            if not getattr(s, camp).strip():
                erori.append(f"{s.cheie}: {camp} gol")

        if not s.detaliere and not s.grupe:
            erori.append(f"{s.cheie}: detaliere sau grupe lipsă")
        if not s.fluxuri:
            erori.append(f"{s.cheie}: fluxuri lipsă")

        for g in s.grupe:
            if not g.titlu.strip():
                erori.append(f"{s.cheie}: grup fără titlu")
            if not g.puncte:
                erori.append(f'{s.cheie}: grupul „{g.titlu}" fără puncte')

        for f in s.fluxuri:
            if f.cod in coduri_vazute:
                erori.append(f"{s.cheie}: cod de flux duplicat {f.cod}")
            coduri_vazute.add(f.cod)
            if not f.flux.strip():
                erori.append(f"{s.cheie}/{f.cod}: denumirea fluxului lipsește")
            if not f.presupune.strip():
                erori.append(f'{s.cheie}/{f.cod}: coloana „Ce presupune" lipsește')

    return erori


CHEI: list[str] = [s.cheie for s in SECTIUNI]


def sectiune_dupa_cheie(cheie: str) -> Sectiune | None:
    for s in SECTIUNI:
        if s.cheie == cheie:
            return s
    return None
