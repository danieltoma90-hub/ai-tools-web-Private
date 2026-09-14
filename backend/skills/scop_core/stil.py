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
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, RGBColor

ANTET_TABEL = ("Cod", "Flux", "Ce presupune")
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


def document_din_gazda(cale_gazda):
    """Deschide gazda ca template și îi golește corpul, păstrând sectPr.

    ``cale_gazda`` este obligatorie: în fluxul web documentul gazdă este
    întotdeauna cel încărcat de utilizator, nu există niciun fallback local
    care să aibă sens pe server.

    Imaginile din corpul gazdei (ex. logo pe copertă) devin orfane odată
    golit corpul — vezi `_elimina_imagini_orfane`, apelată la final, ca
    fișierul capitolului rezultat să nu care mai departe conținut al gazdei
    pe care nimic nu-l mai referă.
    """
    if not cale_gazda:
        raise ValueError(
            "Documentul gazdă este obligatoriu — nu există o gazdă implicită "
            "în fluxul web. Încarcă documentul gazdă și transmite calea lui."
        )
    cale = pathlib.Path(cale_gazda)
    if not cale.is_file():
        raise FileNotFoundError(f"Documentul gazdă nu există: {cale}")

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
