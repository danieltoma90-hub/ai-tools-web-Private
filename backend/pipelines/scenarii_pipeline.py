import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from docx import Document


def _extract_structure(docx_path: Path) -> dict[str, list[dict]]:
    """Extrage ierarhia de heading-uri din DOCX, grupate pe secțiunea H1."""
    doc = Document(str(docx_path))
    modules: dict[str, list[dict]] = defaultdict(list)
    current_h1 = "General"
    current_cap: dict | None = None

    for p in doc.paragraphs:
        style = p.style.name if p.style else ""
        text = p.text.strip()
        if not text:
            continue

        if re.match(r"Heading 1", style, re.I):
            current_h1 = text
            current_cap = None
        elif re.match(r"Heading 2", style, re.I):
            current_cap = {"titlu": text, "subcapitole": []}
            modules[current_h1].append(current_cap)
        elif re.match(r"Heading [3-9]", style, re.I):
            if current_cap is not None:
                current_cap["subcapitole"].append({"titlu": text})
            else:
                cap = {"titlu": text, "subcapitole": []}
                modules[current_h1].append(cap)

    return dict(modules)


def _stub(modul: str, capitol: str, subcapitol: str) -> dict:
    titlu = subcapitol or capitol
    return {
        "capitol": capitol,
        "subcapitol": subcapitol,
        "titlu_scenariu": f"Verificare: {titlu}",
        "obiectiv": f"Verifică funcționalitatea '{titlu}' din modulul {modul}.",
        "preconditii": "• Utilizator autentificat cu drepturi pe modul\n• Date de test pregătite",
        "pasi": "1. Navigare la funcționalitate\n2. Execuție flux conform specificației\n3. Validare rezultat",
        "rezultat_asteptat": "Sistemul procesează fluxul conform specificației. Nu apar erori.",
        "tip_test": "Funcțional - Pozitiv",
        "prioritate": "High" if subcapitol else "Critical",
        "dependente": "—",
        "observatii": "",
    }


def run_scenarii_pipeline(docx_path: Path) -> Path:
    """DOCX spec → Excel cu scenarii de testare. Returns path to .xlsx."""
    structure = _extract_structure(docx_path)

    scenarios: list[dict] = []
    for modul, capitole in structure.items():
        for cap in capitole:
            subs = cap.get("subcapitole", [])
            if subs:
                for sub in subs:
                    scenarios.append(_stub(modul, cap["titlu"], sub["titlu"]))
            else:
                scenarios.append(_stub(modul, cap["titlu"], ""))

    if not scenarios:
        scenarios.append({
            "capitol": "General",
            "subcapitol": "",
            "titlu_scenariu": "Verificare generală",
            "obiectiv": "Verifică funcționalitățile generale din specificație.",
            "preconditii": "• Utilizator autentificat",
            "pasi": "1. Navigare la funcționalitate\n2. Execuție flux\n3. Validare",
            "rezultat_asteptat": "Funcționare conform specificației.",
            "tip_test": "Funcțional - Pozitiv",
            "prioritate": "High",
            "dependente": "—",
            "observatii": "Nicio structură de headings detectată în document.",
        })

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Scenarii"

    headers = [
        "ID", "Capitol", "Subcapitol", "Titlu Scenariu",
        "Obiectiv", "Precondiții", "Pași de Execuție", "Rezultat Așteptat",
        "Tip Test", "Prioritate", "Dependente", "Observații",
    ]
    header_fill = PatternFill(fill_type="solid", fgColor="1F3864")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    wrap = Alignment(wrap_text=True, vertical="top")
    for i, s in enumerate(scenarios, start=1):
        ws.append([
            f"TC-{i:03d}",
            s["capitol"],
            s["subcapitol"],
            s["titlu_scenariu"],
            s["obiectiv"],
            s["preconditii"],
            s["pasi"],
            s["rezultat_asteptat"],
            s["tip_test"],
            s["prioritate"],
            s["dependente"],
            s["observatii"],
        ])
        for col_idx in range(1, 13):
            ws.cell(row=i + 1, column=col_idx).alignment = wrap

    col_widths = [10, 25, 25, 35, 35, 30, 40, 35, 20, 12, 15, 20]
    for col_idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    ws.freeze_panes = "B2"

    fd, tmp_name = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    output_path = Path(tmp_name)
    wb.save(str(output_path))
    return output_path
