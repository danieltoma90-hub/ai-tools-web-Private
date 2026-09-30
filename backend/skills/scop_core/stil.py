# -*- coding: utf-8 -*-
"""Clonarea stilurilor din documentul gazdă și builders de conținut .docx.

Stilurile nu se copiază definiție cu definiție. Documentul gazdă se deschide ca
template și i se golește corpul: astfel se moștenesc styles.xml, numbering.xml,
tema și setările de secțiune, fără potrivire manuală de culori sau dimensiuni.
"""
from __future__ import annotations

import pathlib

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RADACINA = pathlib.Path(__file__).resolve().parents[2]

# Gazde candidate, in ordinea preferintei. Sunt documente de client care pot fi mutate sau
# inlocuite, deci prima existenta cistiga, iar in lipsa tuturor se porneste de la un document
# nou — mai bine un rezultat cu stiluri implicite decat o eroare de fisier lipsa. Pe server
# (backend/skills/scop_core/stil.py, copia acestui fisier) `_DIR_PRODUCTIE` nu exista deloc —
# `_gazda_implicita` degradeaza atunci direct la `None`, ceea ce e comportamentul corect acolo:
# fara upload de gazda, nu exista nicio candidata locala de la care sa se imprumute stilurile.
_DIR_PRODUCTIE = RADACINA / "Document de Scop" / "input" / "1-structura-Charisma-PRODUCTIE"
GAZDE_CANDIDATE = (
    _DIR_PRODUCTIE / "Descriere_Solutie_Ofertata_Productie_Teldo.docx",
    _DIR_PRODUCTIE / "Descriere_Solutie_Ofertata_Productie_Carmangeria_Godac.docx",
)


def _gazda_implicita():
    """Prima gazda candidata existenta, sau oricare .docx din folderul de structura."""
    for cale in GAZDE_CANDIDATE:
        if cale.is_file():
            return cale
    if _DIR_PRODUCTIE.is_dir():
        for cale in sorted(_DIR_PRODUCTIE.glob("*.docx")):
            if not cale.name.startswith("~$"):
                return cale
    return None


GAZDA_IMPLICITA = _gazda_implicita()

ANTET_TABEL = ("Cod", "Flux", "Ce presupune")
ANTET_TABEL_DELIMITARI = ("Element", "Precizare")
CULOARE_ANTET = "1F3864"     # aceeași cu Heading 1 al gazdei


class DocumentInvalid(Exception):
    """Fișierul încărcat nu poate fi deschis ca document Word (.docx) valid.

    Mesajul e mereu curat — text simplu în română, fără nicio cale de fișier
    de pe server — sigur de arătat direct utilizatorului. Excepțiile brute pe
    care le poate ridica python-docx nu sunt: un `.xlsx` redenumit `.docx`
    produce un `ValueError` care include calea temporară internă a serverului
    (``file 'C:\\Users\\...\\tmpXXXX.docx' is not a Word file, content type is
    '...'``), iar un pachet corupt/nu-e-zip produce alte excepții tehnice —
    niciuna potrivită pentru un mesaj către client.
    """


def deschide_docx(cale) -> Document:
    """Deschide `cale` ca document Word, cu eroare curată la conținut invalid.

    Punct unic de trecere prin `Document(...)` pentru fișiere încărcate de
    utilizator (gazdă sau document suplimentar) — vezi `document_din_gazda`,
    `skills.scop_core.insereaza.insereaza_capitol` și
    `skills.scop_core.extractie._extrage_text`. Orice excepție ridicată de
    python-docx la deschidere devine aici `DocumentInvalid`, cu un mesaj în
    română fără nicio cale de sistem de fișiere.
    """
    try:
        return Document(str(cale))
    except Exception as e:
        raise DocumentInvalid(
            "Fișierul încărcat nu este un document Word (.docx) valid."
        ) from e


def _elimina_imagini_orfane(doc) -> None:
    """Scoate din relațiile documentului principal cele de tip imagine,
    devenite orfane după golirea corpului în `document_din_gazda`.

    Corpul e deja gol în acest punct (doar `sectPr` rămâne, cu
    `headerReference`/`footerReference` către antet/subsol — niciodată către
    o imagine), deci ORICE relație de tip imagine de pe partea principală e
    garantat neutilizată: nu mai există niciun `r:embed` în `document.xml`
    care s-o mai țintească. Antetul și subsolul își țin propriile imagini în
    *propriile* fișiere `.rels` (`header1.xml.rels`/`footer1.xml.rels`) —
    părți OPC distincte, neatinse aici — deci imaginile lor rămân intacte.

    Ștergerea e directă din `doc.part.rels`, nu prin `part.drop_rel`: acela
    decide dacă șterge numărând aparițiile atributului `r:id` în XML — dar
    imaginile sunt legate prin `r:embed`, nu `r:id`, deci numărătoarea lui
    ar întoarce mereu 0 și n-ar oferi nicio protecție reală aici. Corpul gol
    e deja dovada suficientă că ștergerea e sigură; python-docx nu scrie la
    salvare nicio parte care nu mai e accesibilă din graful de relații
    pornind de la pachet, deci imaginea (`word/media/imageN.*`) dispare
    automat din fișierul rezultat odată cu relația ei.
    """
    rels = doc.part.rels
    id_uri_imagine = [rId for rId, rel in rels.items() if rel.reltype == RT.IMAGE]
    for rId in id_uri_imagine:
        del rels[rId]


def document_din_gazda(cale_gazda=None):
    """Deschide gazda ca template și îi golește corpul, păstrând sectPr.

    `cale_gazda` e opțională: fără ea (sau `None`), se folosește prima gazdă
    candidată existentă din `GAZDE_CANDIDATE` (vezi `_gazda_implicita`), cu
    degradare la un document nou, cu stilurile implicite din python-docx,
    dacă nicio candidată nu există pe disc — mai bine un rezultat cu stiluri
    implicite decât o eroare de fișier lipsă (pe server, unde nu există nicio
    candidată locală, acesta e mereu cazul: gazda vine exclusiv din upload).
    O cale explicită dar inexistentă e altă situație: acolo chiar e o
    greșeală a apelantului, deci ridică `FileNotFoundError`, nu degradează
    tăcut.

    Deschiderea propriu-zisă trece prin `deschide_docx`, care ridică
    `DocumentInvalid` — cu mesaj curat, fără nicio cale de fișier — dacă
    fișierul există dar nu e un `.docx` valid (pachet corupt, `.xlsx`
    redenumit etc.); esențial când `cale_gazda` vine dintr-un upload de
    utilizator, ca mesajul să nu ajungă cu o cale de server în față.

    Imaginile din corpul gazdei (ex. logo pe copertă) devin orfane odată
    golit corpul — vezi `_elimina_imagini_orfane`, apelată la final, ca
    fișierul rezultat să nu care mai departe conținut al gazdei pe care
    nimic nu-l mai referă (capitolul a scăzut astfel de la 390 KB la 115 KB
    pe o gazdă reală).
    """
    if cale_gazda:
        cale = pathlib.Path(cale_gazda)
        if not cale.is_file():
            raise FileNotFoundError(f"Documentul gazdă nu există: {cale}")
    else:
        cale = _gazda_implicita()
        if cale is None:
            # Fara gazda disponibila: document nou, cu stilurile implicite python-docx.
            doc = Document()
            doc._cale_gazda = None
            return doc

    doc = deschide_docx(cale)
    # Reținută pentru bullets(): golirea corpului de mai jos șterge singurul loc
    # din care se poate afla ce numId folosește gazda pentru bulinele ei proprii
    # (vezi _numid_pentru_buline).
    doc._cale_gazda = cale
    body = doc.element.body
    for child in list(body):
        if not child.tag.endswith("}sectPr"):
            body.remove(child)
    _elimina_imagini_orfane(doc)
    return doc


def _text_container(container) -> str:
    """Tot textul vizibil dintr-un antet/subsol (`container` = `section.header`
    sau `section.footer`): paragrafele lui și, la fel de important, celulele
    oricăror tabele — gazda reală (Turkish Doner Steakhouse) ține numele
    clientului într-un tabel din subsol („Turkish Doner Steakhouse S.R.L. |
    Charisma ERP | v1.0”), nu într-un paragraf simplu; o citire care s-ar opri
    la `container.paragraphs` n-ar găsi niciodată acel text.
    """
    bucati = [p.text.strip() for p in container.paragraphs if p.text.strip()]
    for tabel in container.tables:
        for row in tabel.rows:
            for cell in row.cells:
                if cell.text.strip():
                    bucati.append(cell.text.strip())
    return "\n".join(bucati)


def texte_antet_subsol(doc) -> tuple[str, str]:
    """Întoarce `(text_antet, text_subsol)` — tot textul vizibil din antetele,
    respectiv subsolurile documentului, pe toate secțiunile lui.

    Folosit pentru detectarea mismatch-ului de client (vezi
    `pipelines.scop_core_pipeline`): antetul/subsolul sunt moștenite de la
    documentul gazdă (vezi `document_din_gazda`), corecte doar când gazda și
    clientul curent sunt aceiași — altfel poartă mai departe numele altui
    client. O secțiune legată de cea precedentă (`is_linked_to_previous`) nu
    are propriul antet/subsol — ar duplica textul secțiunii de la care
    moștenește, deci se sare.
    """
    antet, subsol = [], []
    for sectiune in doc.sections:
        if not sectiune.header.is_linked_to_previous:
            t = _text_container(sectiune.header)
            if t:
                antet.append(t)
        if not sectiune.footer.is_linked_to_previous:
            t = _text_container(sectiune.footer)
            if t:
                subsol.append(t)
    return "\n".join(antet), "\n".join(subsol)


def _goleste_paragrafele(paragrafe) -> None:
    """Golește textul vizibil (`.text`) al fiecărui run din `paragrafe`.

    Un run fără text vizibil (de ex. unul care poartă doar un `w:drawing` —
    un logo — sau doar cod de câmp `w:fldChar`/`w:instrText`) rămâne neatins:
    `run.text = ""` pe un asemenea run i-ar șterge conținutul non-text
    (`CT_R.clear_content` scoate orice copil în afară de `w:rPr`), pierzând
    logo-ul fără niciun motiv legat de numele clientului. Rezultatul cache-uit
    al unui câmp (ex. numărul de pagină din PAGE/NUMPAGES) chiar are text
    vizibil și se golește ca oricare alt run — exact ca la Cuprinsul din
    `insereaza.py`, Word îl recalculează la reîmprospătare (F9), nu e o
    corupere.
    """
    for p in paragrafe:
        for run in p.runs:
            if run.text:
                run.text = ""


def _goleste_container(container) -> None:
    """Golește textul vizibil dintr-un antet/subsol: paragrafele lui direct
    și, pe rând, paragrafele din fiecare celulă a oricăror tabele — nu se
    șterge niciun paragraf, celulă, tabel sau relație, doar textul din runuri.
    """
    _goleste_paragrafele(container.paragraphs)
    for tabel in container.tables:
        for row in tabel.rows:
            for cell in row.cells:
                _goleste_paragrafele(cell.paragraphs)


def curata_antet_subsol(doc) -> None:
    """Golește textul vizibil din antetul și subsolul fiecărei secțiuni.

    Opțiune explicită a utilizatorului (vezi routerul `/scop-core/genereaza`)
    pentru cazul în care documentul gazdă a fost reutilizat ca șablon de stil
    pentru un alt client — vezi docstring-ul `document_din_gazda`: antetul și
    subsolul se moștenesc mereu de acolo, corect doar când gazda și clientul
    curent coincid.

    Nu se șterge nicio parte OPC și nicio relație (`headerReference`/
    `footerReference` din `sectPr`, `.rels`-urile antetului/subsolului) —
    doar textul vizibil al runurilor existente. Ștergerea unor PĂRȚI cât timp
    RELAȚIILE către ele rămân în picioare produce exact fișierul stricat pe
    care Word refuză să-l deschidă fără reparare; golirea în loc (păstrând
    paragrafele, tabelele, stilurile și relațiile) nu are cum să ajungă acolo.

    O secțiune legată de cea precedentă (`is_linked_to_previous`) nu are
    propria parte de antet/subsol — a o atinge ar forța crearea uneia noi,
    distinctă de a secțiunii de la care moștenește (exact opusul dorit); se
    sare, la fel ca în `texte_antet_subsol`, iar antetul/subsolul REAL, al
    secțiunii de la care moștenește, tot se golește când ajungem la ea.
    """
    for sectiune in doc.sections:
        if not sectiune.header.is_linked_to_previous:
            _goleste_container(sectiune.header)
        if not sectiune.footer.is_linked_to_previous:
            _goleste_container(sectiune.footer)


def heading(doc, text: str, nivel: int) -> None:
    doc.add_paragraph(text, style=f"Heading {nivel}")


def para(doc, text: str, bold: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold


def _formate_bulina_per_numid(sursa_doc) -> dict[int, bool]:
    """Mapează, din numbering.xml al ``sursa_doc``, fiecare numId la True dacă
    nivelul 0 al listei respective produce o bulină (``w:numFmt="bullet"``) și
    nu o numerotare (decimal, literă etc.) — o gazdă poate avea liste de
    ambele tipuri, iar numai cele cu bulină ne interesează aici.
    """
    root = sursa_doc.part.numbering_part.element
    bulina_per_abstract = {}
    for abstract in root.findall(qn("w:abstractNum")):
        aid = abstract.get(qn("w:abstractNumId"))
        e_bulina = False
        for lvl in abstract.findall(qn("w:lvl")):
            if lvl.get(qn("w:ilvl")) == "0":
                fmt = lvl.find(qn("w:numFmt"))
                e_bulina = fmt is not None and fmt.get(qn("w:val")) == "bullet"
                break
        bulina_per_abstract[aid] = e_bulina

    rezultat: dict[int, bool] = {}
    for num in root.findall(qn("w:num")):
        abst = num.find(qn("w:abstractNumId"))
        numid_txt = num.get(qn("w:numId"))
        if abst is None or numid_txt is None:
            continue
        rezultat[int(numid_txt)] = bulina_per_abstract.get(abst.get(qn("w:val")), False)
    return rezultat


def _numid_din_paragraf(p) -> int | None:
    """Extrage numId-ul din w:numPr al unui paragraf, dacă poartă unul."""
    pPr = p._p.pPr
    if pPr is None:
        return None
    numPr = pPr.find(qn("w:numPr"))
    if numPr is None:
        return None
    numId_el = numPr.find(qn("w:numId"))
    if numId_el is None:
        return None
    val = numId_el.get(qn("w:val"))
    return int(val) if val is not None else None


def _numid_pentru_buline(doc) -> int | None:
    """Detectează numId-ul de listă-cu-bulină pe care gazda îl folosește deja.

    ``document_din_gazda`` golește corpul lui ``doc`` înainte ca ``bullets``
    să apuce să-l vadă, deci exemplul de paragraf cu bulină nu mai există în
    ``doc`` până aici. Redeschidem gazda separat, doar pentru citire (calea e
    reținută în ``doc._cale_gazda``), căutăm un paragraf cu stilul
    "List Paragraph" care poartă ``w:numPr`` și verificăm în numbering.xml că
    numId-ul lui chiar produce o bulină, nu o listă numerotată — gazdele reale
    au ambele tipuri amestecate (vezi Turkish Doner Steakhouse: 17 paragrafe
    cu numId=2 cu bulină, 4 cu numId=3 numerotate). Alegem numId-ul cel mai
    frecvent dintre cele calificate ca bulină, ca un rând ocazional numerotat
    să nu decidă rezultatul. Nu inventăm nicio definiție de numerotare nouă.

    Rezultatul e reținut pe ``doc`` ca să nu se recitească fișierul de pe disc
    la fiecare apel al lui ``bullets`` (un capitol generat cheamă bullets o
    dată per secțiune).

    Întoarce ``None`` dacă gazda n-are niciun paragraf de listă cu bulină de
    la care să învețe (sau dacă redeschiderea eșuează din orice motiv) —
    ``bullets`` tratează asta ca "nimic de reprodus" și nu ridică eroare.
    """
    if hasattr(doc, "_numid_buline_cache"):
        return doc._numid_buline_cache

    numid = None
    cale = getattr(doc, "_cale_gazda", None)
    if cale is not None:
        try:
            sursa = Document(str(cale))
            bulina_per_numid = _formate_bulina_per_numid(sursa)
            aparitii: dict[int, int] = {}
            for p in sursa.paragraphs:
                if p.style is not None and p.style.name == "List Paragraph":
                    n = _numid_din_paragraf(p)
                    if n is not None and bulina_per_numid.get(n):
                        aparitii[n] = aparitii.get(n, 0) + 1
            if aparitii:
                numid = max(aparitii, key=aparitii.get)
        except Exception:
            numid = None

    doc._numid_buline_cache = numid
    return numid


def _aplica_bulina(paragraf, numid: int, ilvl: int = 0) -> None:
    """Adaugă <w:numPr> paragrafului, la poziția corectă în pPr (după pStyle,
    conform ordinii de schemă), legându-l de definiția de listă ``numid``.
    """
    pPr = paragraf._p.get_or_add_pPr()
    numPr = pPr.get_or_add_numPr()
    el_ilvl = OxmlElement("w:ilvl")
    el_ilvl.set(qn("w:val"), str(ilvl))
    el_numid = OxmlElement("w:numId")
    el_numid.set(qn("w:val"), str(numid))
    numPr.append(el_ilvl)
    numPr.append(el_numid)


def bullets(doc, items: list[str]) -> None:
    """Scrie fiecare element ca paragraf cu bulină, la fel ca-n gazdă.

    Stilul "List Paragraph" singur dă doar indentare — bulina vizibilă vine
    din ``w:numPr``, care trimite spre o definiție din numbering.xml. Ca să nu
    inventăm o definiție de numerotare proprie (risc de conflict cu numId-uri
    deja folosite în numbering.xml al gazdei), refolosim numId-ul pe care
    gazda însăși îl folosește pentru propriile paragrafe cu bulină — vezi
    ``_numid_pentru_buline``. Dacă gazda n-are niciun asemenea paragraf de la
    care să învățăm, rămânem la "List Paragraph" simplu, fără ``w:numPr``:
    text indentat corect, dar fără glif — comportamentul documentat pentru
    acest caz.
    """
    numid = _numid_pentru_buline(doc)
    for it in items:
        p = doc.add_paragraph(it, style="List Paragraph")
        if numid is not None:
            _aplica_bulina(p, numid)


def _umbreste(cell, hexc: str) -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), hexc)
    tcpr.append(sh)


def _borduri_grila(table) -> None:
    """Aplică borduri de grilă direct în XML.

    Gazdele reale (Turkish Doner Steakhouse, Carmangeria Godac) nu au stilul
    de tabel "Table Grid" definit în styles.xml — au doar "Normal Table" —
    deci ``table.style = "Table Grid"`` ridică ``KeyError`` la ele. Bordurile
    setate direct pe ``tblPr`` dau același rezultat vizual fără să depindă de
    un stil numit prezent în gazdă.
    """
    tblPr = table._tbl.tblPr
    borduri = OxmlElement("w:tblBorders")
    for latura in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{latura}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        borduri.append(el)
    # `tblPr.append` scrie tblBorders la finalul secvenței de copii, în afara
    # ordinii de schemă CT_TblPr._tag_seq (care așteaptă tblBorders imediat
    # după tblInd/înainte de shd, deci înaintea lui tblLook). Un append brut
    # produce un tblPr invalid din punct de vedere al schemei OOXML — Word îl
    # tolerează la afișare, dar `jc` (setat ulterior de `t.alignment = CENTER`
    # prin get_or_add_jc) se inserează apoi înaintea primului succesor găsit,
    # ceea ce strică și mai mult ordinea. `insert_element_before` inserează
    # tblBorders la poziția corectă din schemă.
    tblPr.insert_element_before(
        borduri, "w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook",
        "w:tblCaption", "w:tblDescription", "w:tblPrChange",
    )


def tabel_fluxuri(doc, fluxuri):
    """Tabel de fluxuri pe 3 coloane, un rând per cod, fără vMerge."""
    t = doc.add_table(rows=1, cols=3)
    try:
        t.style = "Table Grid"
    except KeyError:
        _borduri_grila(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER

    for celula, titlu in zip(t.rows[0].cells, ANTET_TABEL):
        celula.text = ""
        run = celula.paragraphs[0].add_run(titlu)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _umbreste(celula, CULOARE_ANTET)

    for f in fluxuri:
        celule = t.add_row().cells
        celule[0].text = f.cod
        celule[0].paragraphs[0].runs[0].bold = True
        celule[1].text = f.flux
        celule[2].text = f.presupune

    for row in t.rows:
        row.cells[0].width = Cm(1.6)
        row.cells[1].width = Cm(5.4)
        row.cells[2].width = Cm(9.6)

    doc.add_paragraph()
    return t


def tabel(doc, antet: list[str], randuri, latimi=None, bold_prima_coloana: bool = True):
    """Tabel generic, în aceeași ținută ca `tabel_fluxuri`: cap alb pe fundal închis.

    Folosit de skills/generare-scope-core/ pentru tabelele care nu sunt de fluxuri
    (situația actuală, delimitări, sinteză, semnături).
    """
    t = doc.add_table(rows=1, cols=len(antet))
    try:
        t.style = "Table Grid"
    except KeyError:
        _borduri_grila(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER

    for celula, titlu in zip(t.rows[0].cells, antet):
        celula.text = ""
        run = celula.paragraphs[0].add_run(titlu)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _umbreste(celula, CULOARE_ANTET)

    for rand in randuri:
        celule = t.add_row().cells
        for i, valoare in enumerate(rand):
            celule[i].text = str(valoare)
            if bold_prima_coloana and i == 0 and celule[i].paragraphs[0].runs:
                celule[i].paragraphs[0].runs[0].bold = True

    if latimi:
        for row in t.rows:
            for i, lat in enumerate(latimi):
                row.cells[i].width = Cm(lat)

    doc.add_paragraph()
    return t


def tabel_doua_coloane(doc, antet: list[str], randuri):
    """Scurtătură pentru tabelele de tip «situația actuală / cum se adresează»."""
    return tabel(doc, antet, randuri, latimi=[8.3, 8.3])


def tabel_delimitari(doc, delimitari):
    """Tabel de delimitări de scop pe 2 coloane, un rând per intrare.

    Antetul „Element | Precizare” nu e inventat aici: e cel pe care
    documentul gazdă real (Turkish Doner Steakhouse, capitolul „6.
    Delimitari de scop”) îl folosește deja pentru exact același conținut —
    ce anume rămâne în afara scopului ofertat. Stilul (bordură, antet
    umbrit) e în oglindă cu `tabel_fluxuri`, ca cele două tabele ale
    capitolului să arate la fel.
    """
    t = doc.add_table(rows=1, cols=2)
    try:
        t.style = "Table Grid"
    except KeyError:
        _borduri_grila(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER

    for celula, titlu in zip(t.rows[0].cells, ANTET_TABEL_DELIMITARI):
        celula.text = ""
        run = celula.paragraphs[0].add_run(titlu)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _umbreste(celula, CULOARE_ANTET)

    for d in delimitari:
        celule = t.add_row().cells
        celule[0].text = d.element
        celule[0].paragraphs[0].runs[0].bold = True
        celule[1].text = d.precizare

    for row in t.rows:
        row.cells[0].width = Cm(4.5)
        row.cells[1].width = Cm(12.1)

    doc.add_paragraph()
    return t


# Transliterare fara diacritice: cerere de redactare, nu de continut. Se aplica la randare, ca
# textul-sursa sa ramana corect scris pentru clientii care vor diacritice.
_FARA_DIACRITICE = str.maketrans({
    "ă": "a", "Ă": "A", "â": "a", "Â": "A", "î": "i", "Î": "I",
    "ș": "s", "Ș": "S", "ş": "s", "Ş": "S",     # si varianta cu sedila, din fonturi mai vechi
    "ț": "t", "Ț": "T", "ţ": "t", "Ţ": "T",
})


def elimina_diacritice(text: str) -> str:
    """Inlocuieste diacriticele romanesti cu literele de baza."""
    return text.translate(_FARA_DIACRITICE)


def transliterare_document(doc) -> int:
    """Scoate diacriticele din tot documentul: corp, tabele, anteturi, subsoluri, forme.

    Parcurge nodurile w:t, deci ajunge si in casetele de text si in formele de pe coperta, unde
    `doc.paragraphs` nu intra. Intoarce numarul de noduri modificate.
    """
    parti = [doc.element.body]
    parti += [c._element for c in _containere_antet_subsol(doc)]

    schimbate = 0
    for parte in parti:
        for nod in parte.iter(qn("w:t")):
            if not nod.text:
                continue
            nou = elimina_diacritice(nod.text)
            if nou != nod.text:
                nod.text = nou
                schimbate += 1

    props = doc.core_properties
    for camp in ("title", "subject", "comments", "keywords", "category"):
        valoare = getattr(props, camp, None)
        if valoare:
            curat = elimina_diacritice(valoare)
            if curat != valoare:
                setattr(props, camp, curat)
                schimbate += 1
    return schimbate


def _containere_antet_subsol(doc, antet: bool = True, subsol: bool = True):
    """Containerele reale de antet/subsol, sarind secțiunile legate de precedenta.

    Aceeasi regula ca in `texte_antet_subsol` si `curata_antet_subsol`: o secțiune legata nu are
    parte proprie, iar atingerea ei ar forța crearea uneia noi.
    """
    for sectiune in doc.sections:
        if antet and not sectiune.header.is_linked_to_previous:
            yield sectiune.header
        if subsol and not sectiune.footer.is_linked_to_previous:
            yield sectiune.footer


def _paragrafe_container(container):
    """Paragrafele unui antet/subsol, inclusiv cele din celulele tabelelor.

    Sablonul TotalSoft tine linia de identificare intr-un tabel de subsol, nu intr-un paragraf
    simplu — o parcurgere care s-ar opri la `container.paragraphs` ar rata exact numele clientului.
    """
    for p in container.paragraphs:
        yield p
    for tabel in container.tables:
        for row in tabel.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def _are_camp(paragraf) -> bool:
    """Paragraful conține un camp Word (numerotare de pagina, referinta)."""
    return bool(paragraf._p.findall(".//" + qn("w:instrText")))


def _scrie_linia(container, text: str) -> bool:
    """Scrie `text` in primul paragraf fara camp din container. Intoarce True daca a scris."""
    for par in _paragrafe_container(container):
        if _are_camp(par):
            continue
        par.add_run(text)
        return True
    return False


def rescrie_antet_subsol(doc, text_antet=None, text_subsol=None) -> None:
    """Inlocuieste liniile moștenite din gazda cu cele ale documentului curent.

    Gazda e un document de client: antetul ii numeste aria, iar subsolul ii poarta numele si
    versiunea. Lasate asa, documentul nou le tipareste pe fiecare pagina. Se goleste cu
    `curata_antet_subsol` (care pastreaza tabelele, logourile si codurile de camp) si se scrie
    linia noua in primul paragraf fara camp, ca numerotarea paginii sa ramana intacta.
    """
    if text_antet is None and text_subsol is None:
        return
    curata_antet_subsol(doc)
    if text_antet:
        for container in _containere_antet_subsol(doc, antet=True, subsol=False):
            _scrie_linia(container, text_antet)
    if text_subsol:
        for container in _containere_antet_subsol(doc, antet=False, subsol=True):
            _scrie_linia(container, text_subsol)


_CONTOR_FIGURI = {"n": 0}


def reseteaza_contorul_figurilor() -> None:
    """Contorul de figuri e per document; se reseteaza la inceputul fiecarei generari."""
    _CONTOR_FIGURI["n"] = 0


def captura(doc, cale, legenda: str = "", latime_cm: float = 16.0):
    """Insereaza o captura de ecran, centrata, cu legenda numerotata dedesubt.

    Latimea implicita umple zona utila a paginii A4 cu marginile sablonului. Legenda foloseste
    stilul `Caption` daca gazda il are; altfel un paragraf italic mic, ca sa nu depindem de un
    stil care poate lipsi.
    """
    import pathlib

    cale = pathlib.Path(cale)
    if not cale.is_file():
        raise FileNotFoundError(f"Captura nu exista: {cale}")

    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run().add_picture(str(cale), width=Cm(latime_cm))

    if legenda:
        _CONTOR_FIGURI["n"] += 1
        try:
            leg = doc.add_paragraph(style="Caption")
        except KeyError:
            leg = doc.add_paragraph()
        leg.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = leg.add_run(f"Figura {_CONTOR_FIGURI['n']}. {legenda}")
        run.italic = True
        run.font.size = Pt(8.5)
    return par
