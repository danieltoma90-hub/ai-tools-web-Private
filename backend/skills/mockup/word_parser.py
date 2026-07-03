from __future__ import annotations
from pathlib import Path
from docx import Document
from .parser import ScreenSpec, Section, FilterField, ButtonDef, ColumnDef

_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_FILTER_MARKERS = {"Zona de Filtrare", "Zona de filtrare"}
_BUTTON_MARKERS = {"Butoane și Acțiuni", "Butoane si Actiuni", "Butoane", "Butoane și Acțiuni"}
_COLUMN_MARKERS = {"Coloane Grid", "Coloane grid"}
_ZONE_MARKERS = {"Zone Ecran", "Zone ecran"}
_ALL_MARKERS = _FILTER_MARKERS | _BUTTON_MARKERS | _COLUMN_MARKERS | _ZONE_MARKERS


def _para_text(p_el) -> str:
    """Extract paragraph text only from w:t elements (avoids itertext() duplication)."""
    return "".join(t.text or "" for t in p_el.findall(f".//{{{_NS}}}t")).strip()


def _cell_text(tc_el) -> str:
    """Extract cell text only from w:t elements."""
    return "".join(t.text or "" for t in tc_el.findall(f".//{{{_NS}}}t")).strip()


def _table_rows(tbl_el) -> list[list[str]]:
    """Return list of rows, each a list of cell texts. Skips duplicate merged cells."""
    rows = []
    for tr in tbl_el.findall(f".//{{{_NS}}}tr"):
        cells = [_cell_text(tc) for tc in tr.findall(f"{{{_NS}}}tc")]
        rows.append(cells)
    return rows


def _body_items(doc: Document):
    """Yield ('p', element) or ('tbl', element) in document body order."""
    for child in doc.element.body:
        tag = child.tag.split("}")[1] if "}" in child.tag else child.tag
        if tag == "p":
            yield "p", child
        elif tag == "tbl":
            yield "tbl", child


def parse_word(path: Path) -> tuple[ScreenSpec, dict]:
    """Parse a Word .docx describing a screen into (ScreenSpec, descriptions dict)."""
    doc = Document(str(path))
    items = list(_body_items(doc))

    screen_title = ""
    main_section: Section | None = None
    secondary_sections: list[Section] = []

    filter_descs: dict[str, str] = {}
    button_descs: dict[str, str] = {}
    col_descs: dict[str, str] = {}

    expect_next: str | None = None  # "filter" | "buttons" | "columns"
    pending_secondary_title: str | None = None

    for kind, el in items:
        if kind == "p":
            text = _para_text(el)
            if not text:
                continue

            # First non-empty paragraph = screen title
            if not screen_title:
                screen_title = text
                continue

            if text in _ZONE_MARKERS:
                if main_section is None:
                    main_section = Section(title=screen_title)
                continue

            if text in _FILTER_MARKERS:
                expect_next = "filter"
                pending_secondary_title = None
                continue

            if text in _BUTTON_MARKERS:
                expect_next = "buttons"
                pending_secondary_title = None
                continue

            if text in _COLUMN_MARKERS:
                expect_next = "columns"
                # pending_secondary_title carries over if set
                continue

            # Unknown non-marker paragraph = secondary section title
            pending_secondary_title = text

        elif kind == "tbl":
            rows = _table_rows(el)
            if not rows:
                continue
            data_rows = rows[1:]  # skip header row

            if expect_next == "filter" and main_section is not None:
                for cells in data_rows:
                    if not cells or not cells[0]:
                        continue
                    label = cells[0]
                    mandatory = cells[1].strip().lower() in ("da", "yes", "true") if len(cells) > 1 else False
                    desc = cells[2] if len(cells) > 2 else ""
                    main_section.filter_fields.append(FilterField(label=label, mandatory=mandatory))
                    if desc:
                        filter_descs[label] = desc
                expect_next = None

            elif expect_next == "buttons" and main_section is not None:
                for cells in data_rows:
                    if not cells or not cells[0]:
                        continue
                    label = cells[0]
                    tip = cells[1].strip().lower() if len(cells) > 1 else ""
                    desc = cells[2] if len(cells) > 2 else ""
                    group = "actiuni" if tip in ("acțiune", "actiune", "action") else "direct"
                    if not any(b.label == label for b in main_section.buttons):
                        main_section.buttons.append(ButtonDef(label=label, group=group))
                    if desc:
                        button_descs[label] = desc
                expect_next = None

            elif expect_next == "columns":
                if pending_secondary_title:
                    sec = Section(title=pending_secondary_title)
                    for cells in data_rows:
                        if not cells or not cells[0]:
                            continue
                        col_name = cells[0]
                        desc = cells[1] if len(cells) > 1 else ""
                        sec.columns.append(ColumnDef(name=col_name))
                        if desc:
                            col_descs[col_name] = desc
                    secondary_sections.append(sec)
                    pending_secondary_title = None
                elif main_section is not None:
                    for cells in data_rows:
                        if not cells or not cells[0]:
                            continue
                        col_name = cells[0]
                        desc = cells[1] if len(cells) > 1 else ""
                        main_section.columns.append(ColumnDef(name=col_name))
                        if desc:
                            col_descs[col_name] = desc
                expect_next = None

    all_sections = ([main_section] if main_section else []) + secondary_sections
    spec = ScreenSpec(
        screen_title=screen_title,
        source_file=Path(path).name,
        sections=all_sections,
    )
    descriptions = {
        "descriere_generala": "",
        "reguli_business": [],
        "descrieri_filtre": filter_descs,
        "descrieri_butoane": button_descs,
        "descrieri_coloane": col_descs,
        "mod_de_lucru": [],
    }
    return spec, descriptions
