# -*- coding: utf-8 -*-
"""Distribuie modulele pe numarul de zile cerut.

Doua operatii distincte:
  1. SCALARE — orele de referinta ale catalogului se strang sau se lasa mai
     larg, ca sa incapa exact in bugetul zilelor cerute.
  2. IMPARTIRE PE ZILE — modulele se aseaza in ordine, fara sa fie taiate in
     doua zile decat daca nu incap altfel.

Un modul nu coboara sub `MIN_ORE`: sub pragul asta nu mai poti preda nimic,
doar bifezi subiectul. Cand bugetul e prea mic chiar si asa, modulele
neesentiale ies din plan si sunt raportate explicit — mai bine spui ce nu ai
acoperit decat sa promiti 15 minute pentru Contabilitate.
"""
from __future__ import annotations

ORE_PE_ZI = 6.0        # ore nete de training dintr-o zi de lucru (~7h brut minus pauze)
MIN_ORE = 0.5          # sub asta un modul nu mai are sens
PAS = 0.5              # orele se rotunjesc la jumatati de ora


def _rotunjeste(ore: float) -> float:
    return max(MIN_ORE, round(ore / PAS) * PAS)


def scaleaza(module: list[dict], buget_ore: float) -> tuple[list[dict], list[dict]]:
    """Ajusteaza orele modulelor la bugetul disponibil.

    Returneaza (module_incluse, module_excluse). Modulele esentiale nu se
    exclud niciodata — daca nici ele nu incap, primesc minimul si bugetul e
    depasit, iar apelantul avertizeaza.
    """
    incluse = [dict(m) for m in module]
    excluse: list[dict] = []

    # Cat timp nici la minim nu incape totul, scoatem modulul neesential cel
    # mai putin costisitor de pierdut (ultimul din ordinea catalogului).
    while incluse:
        minim_posibil = sum(MIN_ORE for _ in incluse)
        if minim_posibil <= buget_ore:
            break
        candidati = [m for m in incluse if not m.get("esential")]
        if not candidati:
            break
        de_scos = candidati[-1]
        incluse.remove(de_scos)
        excluse.append(de_scos)

    referinta = sum(m["ore"] for m in incluse)
    if referinta > 0:
        factor = buget_ore / referinta
        for m in incluse:
            m["ore"] = _rotunjeste(m["ore"] * factor)

    # Rotunjirea la 0.5 duce totalul putin langa buget; corectam pe modulul
    # cel mai mare, ca ajustarea sa se simta cel mai putin.
    diferenta = round(buget_ore - sum(m["ore"] for m in incluse), 2)
    if incluse and abs(diferenta) >= PAS:
        tinta = max(incluse, key=lambda m: m["ore"])
        tinta["ore"] = _rotunjeste(tinta["ore"] + diferenta)

    return incluse, excluse


PRAG_SPARGERE = 1.0  # sub atat, golul ramas nu merita recuperat taind un modul


def imparte_pe_zile(module: list[dict], zile: int) -> list[dict]:
    """Aseaza modulele in zile de cate ORE_PE_ZI, in ordinea catalogului.

    Un modul rupt intre doua zile inseamna ca a doua zi incepi prin a relua
    contextul, asa ca il taiem doar cand chiar merita: daca in ziua curenta a
    ramas un gol de cel putin o ora. Sub pragul asta modulul trece intreg in
    ziua urmatoare si ziua ramane putin mai scurta — mai bine asa decat un
    subiect de 30 de minute lipit la finalul zilei.
    """
    plan: list[dict] = [{"zi": i + 1, "module": [], "ore": 0.0} for i in range(zile)]
    idx = 0

    def liber_in(i: int) -> float:
        return round(ORE_PE_ZI - plan[i]["ore"], 2)

    for m in module:
        ramase = m["ore"]
        parte = 0

        while ramase > 0 and idx < zile:
            liber = liber_in(idx)

            if ramase <= liber:                      # incape intreg aici
                bucata = dict(m, ore=ramase)
                if parte:
                    bucata["nume"] = f"{m['nume']} (continuare)"
                    bucata["continuare"] = True
                plan[idx]["module"].append(bucata)
                plan[idx]["ore"] = round(plan[idx]["ore"] + ramase, 2)
                ramase = 0
                break

            # Taiem doar daca AMBELE bucati raman utilizabile: si cea care
            # umple ziua curenta, si restul. Altfel modulul ar aparea a doua zi
            # cu o coada de 30 de minute, care nu e o sesiune, ci o intrerupere.
            rest_dupa = round(ramase - liber, 2)
            if liber >= PRAG_SPARGERE and rest_dupa >= PRAG_SPARGERE:
                parte += 1
                bucata = dict(m, ore=liber)
                if parte > 1:
                    bucata["nume"] = f"{m['nume']} (continuare)"
                    bucata["continuare"] = True
                plan[idx]["module"].append(bucata)
                plan[idx]["ore"] = ORE_PE_ZI
                ramase = round(ramase - liber, 2)

            idx += 1                                  # gol mic sau zi plina

        if ramase > 0:
            # Nu mai sunt zile. Daca modulul are deja o bucata in ultima zi,
            # o marim pe aceea — doua linii cu acelasi modul in aceeasi zi ar
            # fi o eroare de citit in agenda.
            ultima = plan[-1]
            existenta = next(
                (b for b in ultima["module"] if b["nr"] == m["nr"]), None
            )
            if existenta is not None:
                existenta["ore"] = round(existenta["ore"] + ramase, 2)
                existenta["nume"] = m["nume"]
                existenta.pop("continuare", None)
                existenta["suprapus"] = True
            else:
                bucata = dict(m, ore=ramase, suprapus=True)
                if parte:
                    bucata["nume"] = f"{m['nume']} (continuare)"
                    bucata["continuare"] = True
                ultima["module"].append(bucata)
            ultima["ore"] = round(ultima["ore"] + ramase, 2)

    return [z for z in plan if z["module"]]


def construieste_plan(module: list[dict], zile: int) -> dict:
    """Planul complet pentru numarul de zile cerut."""
    if zile < 1:
        raise ValueError("Numărul de zile trebuie să fie cel puțin 1")

    capacitate = zile * ORE_PE_ZI

    # Asezarea pe zile pierde inevitabil cate un pic la fiecare tranzitie (golul
    # sub pragul de spargere). Daca scalam fix la capacitate, exact acel pic
    # ramane pe dinafara si ultima zi iese peste program. Coboram bugetul in
    # pasi de o jumatate de ora pana cand planul incape cu adevarat.
    buget = capacitate
    incluse: list[dict] = []
    excluse: list[dict] = []
    zile_plan: list[dict] = []
    for _ in range(int(capacitate / PAS)):
        incluse, excluse = scaleaza(module, buget)
        zile_plan = imparte_pe_zile(incluse, zile)
        if not any(z["ore"] > ORE_PE_ZI + 0.01 for z in zile_plan):
            break
        buget = round(buget - PAS, 2)

    total = round(sum(m["ore"] for z in zile_plan for m in z["module"]), 2)

    return {
        "zile": zile_plan,
        "excluse": excluse,
        "total_ore": total,
        "buget_ore": capacitate,
        "supraincarcat": any(z["ore"] > ORE_PE_ZI + 0.01 for z in zile_plan),
    }
