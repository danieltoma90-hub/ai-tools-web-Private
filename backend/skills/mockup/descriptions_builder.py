from .parser import ScreenSpec

_HEADERS = {"Observatii", "Descriere functionalitate", "Mod de lucru"}


def _group_observatii(observatii: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    current = None
    for line in observatii:
        if line in _HEADERS:
            current = line
            groups[current] = []
        elif current is not None:
            groups[current].append(line)
    return groups


def _enrich(raw: str, label: str, field_type: str, spec_context: dict) -> str:
    """
    Develop a raw Excel comment into a full description understandable by both
    technical and business users. Adds role context, constraints, and cross-references.
    """
    base = raw.strip() if raw and raw != label else ""
    parts = []

    if base:
        # Capitalize first letter, end with period
        sentence = base[0].upper() + base[1:]
        if not sentence.endswith("."):
            sentence += "."
        parts.append(sentence)

    # --- Mandatory field context ---
    if field_type == "filter_mandatory":
        parts.append(
            "Câmp obligatoriu: procesul nu poate fi inițiat fără completarea acestuia. "
            "Din perspectivă tehnică, valoarea este validată la client înainte de orice apel server."
        )
    elif field_type == "filter_optional":
        parts.append(
            "Câmp opțional de filtrare: dacă este lăsat gol, nu restricționează rezultatele returnate. "
            "Util atunci când utilizatorul dorește să vizualizeze date pentru toate valorile posibile ale acestui criteriu."
        )

    # --- Readonly/auto-filled detection ---
    readonly_keywords = ["nu se poate modifica", "se completează automat", "se afișează", "read-only", "calculat"]
    if any(kw in base.lower() for kw in readonly_keywords):
        parts.append(
            "Câmp read-only — valoarea este calculată sau completată automat de sistem "
            "și nu poate fi modificată direct de utilizator."
        )

    # --- Bulk-fill detection ---
    if "bulk" in base.lower() or "din campul de filtrare" in base.lower() or "din filtru" in base.lower():
        parts.append(
            "Mecanism bulk: valoarea din filtru se propagă automat pe toate rândurile selectate, "
            "eliminând necesitatea completării manuale rând cu rând."
        )

    # --- Import/Export context ---
    if field_type == "button_direct" and "import" in label.lower():
        parts.append(
            "Declanșează procesul de import dintr-un fișier Excel extern. "
            "Tehnic: datele sunt încărcate mai întâi într-un buffer intermediar (nu direct în baza de date), "
            "permițând verificarea consistenței înainte de confirmare."
        )
    if field_type == "button_direct" and "export" in label.lower():
        parts.append(
            "Exportă conținutul curent al ecranului în format Excel, inclusiv filtrele aplicate. "
            "Util pentru raportare sau reconcilieri offline."
        )

    # --- Action buttons context ---
    if field_type == "button_action":
        workflow = spec_context.get("workflow", [])
        # Add step context from Mod de lucru if this button appears in workflow
        for step in workflow:
            if label.lower() in step.lower():
                parts.append(f"Context flux de lucru: {step.strip()}")
                break

    # --- Status column context ---
    if "status" in label.lower() or "mesaj" in label.lower():
        parts.append(
            "Din perspectivă business: acest câmp oferă feedback în timp real despre starea "
            "procesării fiecărui rând — permite operatorului să identifice rapid rândurile cu erori "
            "și să le corecteze înainte de generarea documentului final."
        )

    # --- Stoc column context ---
    if "stoc" in label.lower() and "proprietate" not in label.lower():
        parts.append(
            "Valoarea reflectă stocul fizic disponibil la data specificată în filtrul 'Data', "
            "calculat FIFO. Este baza pentru distribuția automată efectuată de acțiunea "
            "'Distribuție stoc pe detalii de mașini' — dacă stocul este insuficient față de "
            "cantitățile solicitate, sistemul va marca rândurile respective cu mesaj de eroare."
        )

    # --- Proiect/dimensiune analiza context ---
    if "proiect" in label.lower() or "dimensiune" in label.lower():
        parts.append(
            "Dimensiune de analiză pentru controlul de gestiune: permite alocarea consumului "
            "pe centru de cost sau proiect. Din punct de vedere tehnic, această valoare se "
            "propagă pe documentul 'Bon de Consum' generat în Core Charisma."
        )

    # --- Nr. Inmatriculare / vehicul context ---
    if "inmatriculare" in label.lower() or "flota" in label.lower():
        parts.append(
            "Identificator al vehiculului în sistemul Charisma. "
            "Legătura cu modulul Fleet permite trasabilitatea completă a consumului "
            "pe vehicul și raportarea costurilor per unitate de transport."
        )

    if not parts:
        parts.append(f"Câmp '{label}' din ecranul {spec_context.get('screen_title', '')}.")

    return " ".join(parts)


def _build_descriere_from_comments(spec: ScreenSpec) -> str:
    """Build a general description from cell comments when Observatii sheet is missing."""
    comments = spec.cell_comments
    all_sections = spec.sections
    if not all_sections:
        return f"Raport {spec.screen_title}."

    sec = all_sections[0]
    col_count = len(sec.columns)
    filter_count = len(sec.filter_fields)
    btn_count = len(sec.buttons)

    # Synthesize from available data
    parts = [
        f"Ecranul '{spec.screen_title}' este un raport interactiv din sistemul Charisma ERP."
    ]
    if filter_count:
        mandatory = [f.label for f in sec.filter_fields if f.mandatory]
        optional = [f.label for f in sec.filter_fields if not f.mandatory]
        if mandatory:
            parts.append(
                f"Raportul necesită completarea obligatorie a câmpurilor: {', '.join(mandatory)}."
            )
        if optional:
            parts.append(
                f"Filtrele opționale disponibile sunt: {', '.join(optional)}."
            )
    if col_count:
        parts.append(
            f"Grila de date conține {col_count} coloane și prezintă informații detaliate "
            f"extrase din modulele Charisma ERP."
        )
    if btn_count:
        direct = [b.label for b in sec.buttons if b.group == "direct"]
        if direct:
            parts.append(f"Acțiunile disponibile: {', '.join(direct)}.")

    return " ".join(parts)


def build_descriptions(spec: ScreenSpec) -> dict:
    groups = _group_observatii(spec.observatii)
    comments = spec.cell_comments
    has_observatii = bool(spec.observatii)
    workflow = groups.get("Mod de lucru", [])
    ctx = {"workflow": workflow, "screen_title": spec.screen_title}

    # Descriere generala
    if has_observatii:
        raw_desc = " ".join(groups.get("Descriere functionalitate", []))
        if raw_desc:
            descriere = (
                f"{raw_desc.strip()}. "
                f"Ecranul implementează un flux în 4 pași: import date sursă, salvare în buffer, "
                f"verificare consistență și distribuție stoc, urmate de generarea documentului final "
                f"(Bon de Consum). Acesta este un ecran editabil — datele pot fi ajustate manual "
                f"înainte de confirmare, oferind flexibilitate operatorului."
            )
        else:
            descriere = f"Ecran pentru {spec.screen_title}."
    else:
        descriere = _build_descriere_from_comments(spec)

    # Reguli business
    raw_rules = groups.get("Observatii", []) if has_observatii else []

    # If no Observatii, extract rules from comments that mention constraints
    if not raw_rules:
        rule_keywords = ["obligatoriu", "nu se poate", "doar", "trebuie", "valideaza", "verifica"]
        for coord, text in comments.items():
            if any(kw in text.lower() for kw in rule_keywords):
                raw_rules.append(text)

    reguli = []
    for r in raw_rules:
        r = r.strip()
        if "fifo" in r.lower():
            reguli.append(
                f"{r}. Aceasta înseamnă că la distribuirea stocului se consumă mai întâi "
                f"intrările cu data cea mai veche, respectând principiul First In First Out. "
                f"Impactul business: costul de consum reflectă prețul de achiziție al celor mai "
                f"vechi loturi, relevant pentru evaluarea stocurilor."
            )
        elif "discriminant" in r.lower() or "data de intrare" in r.lower():
            reguli.append(
                f"{r}. Filtrul 'Data ≤' din ecran controlează vizibilitatea intrărilor de stoc — "
                f"afișează doar loturile intrate până la data specificată, asigurând că distribuția "
                f"FIFO se face corect în contextul perioadei de raportare."
            )
        else:
            reguli.append(r)

    if not reguli:
        reguli = [f"Ecran editabil pentru {spec.screen_title}."]

    # Mod de lucru — build from Observatii or synthesize from buttons
    if not workflow and not has_observatii:
        # Synthesize workflow from button order
        all_btns = [b for s in spec.sections for b in s.buttons]
        direct = [b for b in all_btns if b.group == "direct"]
        for b in direct:
            raw = comments.get(b.coord, "")
            step = f"{b.label}: {raw}" if raw else b.label
            workflow.append(step)

    mod_enriched = []
    for step in workflow:
        step = step.strip()
        if "importa" in step.lower():
            mod_enriched.append(
                f"{step} — Tehnic: datele sunt validate structural la import "
                f"(coloane obligatorii, tipuri de date). Erorile de format sunt raportate imediat."
            )
        elif "salveaza" in step.lower() or "salvare" in step.lower():
            mod_enriched.append(
                f"{step} — Datele intră într-un buffer temporar, nu direct în tranzacție. "
                f"Permite reluarea procesului (Ștergere Buffer) fără impact în baza de date."
            )
        elif "verificare" in step.lower() or "validare" in step.lower():
            mod_enriched.append(
                f"{step} — Sistemul validează consistența business: stoc suficient, "
                f"vehicule existente în flotă, proiecte active. Rândurile cu erori sunt marcate "
                f"vizual și blocate de la generarea documentului."
            )
        elif "distributie" in step.lower() or "distribuție" in step.lower():
            mod_enriched.append(
                f"{step} — Algoritmul FIFO alocă stocul disponibil pe fiecare rând în ordinea "
                f"datelor de intrare. Dacă stocul este insuficient pentru un rând, acesta "
                f"primește mesaj de eroare și nu poate fi importat."
            )
        elif "genereaza" in step.lower():
            mod_enriched.append(
                f"{step} — Creează documentul contabil 'Bon de Consum' în Core Charisma, "
                f"cu alocare pe dimensiunile Proiect și Nr. Înmatriculare. "
                f"Doar rândurile fără erori și cu status validat sunt incluse în document."
            )
        else:
            mod_enriched.append(step)

    # Descriptions for each field using comments + enrichment
    descrieri_filtre = {}
    descrieri_butoane = {}
    descrieri_coloane = {}

    for sec in spec.sections:
        for f in sec.filter_fields:
            raw = comments.get(f.coord, "")
            ftype = "filter_mandatory" if f.mandatory else "filter_optional"
            descrieri_filtre[f.label] = _enrich(raw, f.label, ftype, ctx)
        for b in sec.buttons:
            raw = comments.get(b.coord, "")
            ftype = f"button_{b.group}"
            descrieri_butoane[b.label] = _enrich(raw, b.label, ftype, ctx)
        for c in sec.columns:
            raw = comments.get(c.coord, "")
            descrieri_coloane[c.name] = _enrich(raw, c.name, "column", ctx)

    return {
        "descriere_generala": descriere,
        "reguli_business": reguli,
        "descrieri_filtre": descrieri_filtre,
        "descrieri_butoane": descrieri_butoane,
        "descrieri_coloane": descrieri_coloane,
        "mod_de_lucru": mod_enriched,
    }
