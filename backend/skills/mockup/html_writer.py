from pathlib import Path
from .parser import ScreenSpec, Section


_STYLE = """
body{font-family:'Segoe UI',Arial,sans-serif;font-size:12px;background:#f0f0f0;margin:0;padding:12px}
.screen{border:1px solid #aaa;max-width:1100px}
.titlebar{background:#1a3a5c;color:white;padding:4px 10px;font-weight:bold;display:flex;justify-content:space-between}
.toolbar{background:#e8e8e8;border-bottom:2px solid #9ab8d4;padding:4px 8px;display:flex;gap:3px;flex-wrap:wrap;align-items:center}
.btn-direct{background:#0078d4;color:white;border:none;padding:3px 10px;border-radius:2px;font-size:11px}
.btn-action{background:#5c7a9e;color:white;border:none;padding:3px 10px;border-radius:2px;font-size:11px}
.btn-generate{background:#2e6b2e;color:white;border:none;padding:3px 10px;border-radius:2px;font-size:11px;font-weight:bold}
.actiuni-label{font-size:11px;font-weight:bold;color:#1a3a5c;margin:0 4px}
.main-area{display:flex;border-bottom:2px solid #aaa}
.filter-panel{width:160px;min-width:160px;background:#dce6f1;border-right:2px solid #b8cfe4;padding:8px 10px}
.filter-title{font-weight:bold;color:#1a3a5c;font-size:11px;margin-bottom:8px;border-bottom:1px solid #9ab8d4;padding-bottom:4px}
.filter-field{margin-bottom:6px}
.filter-label{font-size:10px;color:#444;margin-bottom:2px}
.filter-label-mand{font-size:10px;font-weight:bold;color:#c0392b;margin-bottom:2px}
.filter-input{width:100%;box-sizing:border-box;padding:2px 4px;border:1px solid #aaa;font-size:10px}
.filter-input-mand{width:100%;box-sizing:border-box;padding:2px 4px;border:1px solid #c0392b;font-size:10px;background:#fff5f5}
.filter-note{font-size:9px;color:#666;margin-top:1px;font-style:italic}
.filter-sep{border-top:1px dashed #9ab8d4;padding-top:6px;margin-top:4px}
.filter-opt-label{font-size:9px;color:#888;margin-bottom:4px;font-style:italic}
.grid-wrap{flex:1;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:11px}
thead tr{background:#1a3a5c;color:white}
thead th{padding:4px 5px;border:1px solid #2d5a8e;white-space:nowrap}
tbody tr:nth-child(odd){background:white}
tbody tr:nth-child(even){background:#f5f8ff}
tbody td{padding:3px 5px;border:1px solid #ddd}
.sec-header{background:#e8f0e8;border-top:2px solid #5c8a5c;padding:4px 10px;font-weight:bold;color:#2d5a2d;font-size:11px}
thead.sec tr{background:#4a7a4a}
thead.sec th{border-color:#6a9a6a}
.footer{background:#f5f5f5;border-top:1px solid #ccc;padding:4px 10px;font-size:10px;color:#666;text-align:right}
"""


def _render_filter_panel(section: Section) -> str:
    mandatory = [f for f in section.filter_fields if f.mandatory]
    optional = [f for f in section.filter_fields if not f.mandatory]

    # Use example values from col B (stored during parsing)
    filter_values = section.filter_values

    parts = ['<div class="filter-panel">', '<div class="filter-title">Zona de filtrare</div>']

    for f in mandatory:
        note = ""
        if f.label == "Data":
            note = '<div class="filter-note">Completare bulk col. Data + filtru stoc ≤</div>'
        val = filter_values.get(f.label, "")
        parts.append(
            f'<div class="filter-field">'
            f'<div class="filter-label-mand">{f.label} <span style="color:#c0392b">*</span></div>'
            f'<input class="filter-input-mand" type="text" value="{val}"/>'
            f'{note}</div>'
        )

    if optional:
        parts.append('<div class="filter-sep"><div class="filter-opt-label">Filtre optionale:</div></div>')
        for f in optional:
            val = filter_values.get(f.label, "")
            parts.append(
                f'<div class="filter-field">'
                f'<div class="filter-label">{f.label}</div>'
                f'<input class="filter-input" type="text" value="{val}"/>'
                f'</div>'
            )

    if mandatory:
        parts.append('<div style="font-size:9px;color:#888;margin-top:4px">* câmp obligatoriu</div>')
    parts.append("</div>")
    return "".join(parts)


def _render_toolbar(section: Section) -> str:
    direct = [b for b in section.buttons if b.group == "direct"]
    actions = [b for b in section.buttons if b.group == "actiuni"]
    parts = ['<div class="toolbar">']
    for b in direct:
        parts.append(f'<button class="btn-direct">{b.label}</button>')
    if actions:
        parts.append('<span class="actiuni-label">Actiuni:</span>')
        for b in actions:
            cls = "btn-generate" if b.label == "Genereaza document" else "btn-action"
            parts.append(f'<button class="{cls}">{b.label}</button>')
    parts.append("</div>")
    return "".join(parts)


def _calc_total(sec: Section) -> float | None:
    """Calculate total of the numeric quantity column from actual data rows."""
    col_names = [c.name.lower() for c in sec.columns]
    qty_idx = next((i for i, n in enumerate(col_names) if "cantitate" in n or "cant" in n), None)
    if qty_idx is None or not sec.data_rows:
        return None
    total = 0.0
    for row in sec.data_rows:
        try:
            total += float(str(row[qty_idx]).replace(".", "").replace(",", "."))
        except (ValueError, IndexError):
            pass
    return total if total > 0 else None


def _render_grid(section: Section, is_secondary: bool = False, total: float | None = None) -> str:
    thead_class = ' class="sec"' if is_secondary else ""
    parts = ['<div class="grid-wrap"><table>', f"<thead{thead_class}><tr>"]
    if not is_secondary:
        parts.append("<th></th>")
    for col in section.columns:
        # Skip checkbox column from header — already shown as the implicit checkbox column
        if col.name.lower() in ("selectat", "selecteaza"):
            continue
        parts.append(f"<th>{col.name}</th>")
    parts.append("</tr></thead><tbody>")

    rows_to_render = section.data_rows if section.data_rows else [[""] * len(section.columns)] * 3
    for row_data in rows_to_render:
        parts.append("<tr>")
        if not is_secondary:
            parts.append('<td style="text-align:center"><input type="checkbox" checked/></td>')
        for col, val in zip(section.columns, row_data):
            # Skip checkbox column in data rows — implicit checkbox already handles it
            if col.name.lower() in ("selectat", "selecteaza"):
                continue
            parts.append(f"<td>{val if val else '&nbsp;'}</td>")
        parts.append("</tr>")

    # Total row for secondary sections
    if is_secondary and total is not None:
        col_names = [c.name.lower() for c in section.columns]
        qty_idx = next((i for i, n in enumerate(col_names) if "cantitate" in n or "cant" in n), None)
        parts.append('<tr style="border-top:2px solid #4a7a4a;font-weight:bold;background:#e8f0e8">')
        for i, col in enumerate(section.columns):
            if i == 0:
                parts.append(f'<td colspan="2" style="padding:3px 8px;border:1px solid #ddd;">TOTAL</td>')
            elif i == 1:
                continue
            elif qty_idx is not None and i == qty_idx:
                parts.append(f'<td style="padding:3px 8px;border:1px solid #ddd;text-align:right;color:#1a3a5c">{int(total):,}'.replace(",", ".") + "</td>")
            else:
                parts.append(f'<td style="padding:3px 8px;border:1px solid #ddd;">&nbsp;</td>')
        parts.append("</tr>")

    parts.append("</tbody></table></div>")
    return "".join(parts)


_STYLE_COMPACT = """
body{font-family:'Segoe UI',Arial,sans-serif;font-size:8px;background:#fff;margin:0;padding:4px}
.screen{border:1px solid #aaa;max-width:740px}
.titlebar{background:#1a3a5c;color:white;padding:2px 6px;font-weight:bold;font-size:9px;display:flex;justify-content:space-between}
.toolbar{background:#e8e8e8;border-bottom:1px solid #9ab8d4;padding:2px 4px;display:flex;gap:2px;flex-wrap:wrap;align-items:center}
.btn-direct{background:#0078d4;color:white;border:none;padding:1px 6px;border-radius:1px;font-size:8px}
.btn-action{background:#5c7a9e;color:white;border:none;padding:1px 6px;border-radius:1px;font-size:8px}
.btn-generate{background:#2e6b2e;color:white;border:none;padding:1px 6px;border-radius:1px;font-size:8px;font-weight:bold}
.actiuni-label{font-size:8px;font-weight:bold;color:#1a3a5c;margin:0 2px}
.main-area{display:flex;border-bottom:1px solid #aaa}
.filter-panel{width:100px;min-width:100px;background:#dce6f1;border-right:1px solid #b8cfe4;padding:4px 6px}
.filter-title{font-weight:bold;color:#1a3a5c;font-size:8px;margin-bottom:4px;border-bottom:1px solid #9ab8d4;padding-bottom:2px}
.filter-field{margin-bottom:3px}
.filter-label{font-size:7px;color:#444;margin-bottom:1px}
.filter-label-mand{font-size:7px;font-weight:bold;color:#c0392b;margin-bottom:1px}
.filter-input{width:100%;box-sizing:border-box;padding:1px 2px;border:1px solid #aaa;font-size:7px}
.filter-input-mand{width:100%;box-sizing:border-box;padding:1px 2px;border:1px solid #c0392b;font-size:7px;background:#fff5f5}
.filter-note{font-size:6px;color:#666;margin-top:1px;font-style:italic}
.filter-sep{border-top:1px dashed #9ab8d4;padding-top:3px;margin-top:2px}
.filter-opt-label{font-size:6px;color:#888;margin-bottom:2px;font-style:italic}
.grid-wrap{flex:1;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:7px}
thead tr{background:#1a3a5c;color:white}
thead th{padding:2px 3px;border:1px solid #2d5a8e;white-space:nowrap}
tbody tr:nth-child(odd){background:white}
tbody tr:nth-child(even){background:#f5f8ff}
tbody td{padding:1px 3px;border:1px solid #ddd;white-space:nowrap}
.sec-header{background:#e8f0e8;border-top:1px solid #5c8a5c;padding:2px 6px;font-weight:bold;color:#2d5a2d;font-size:8px}
thead.sec tr{background:#4a7a4a}
thead.sec th{border-color:#6a9a6a}
.footer{background:#f5f5f5;border-top:1px solid #ccc;padding:2px 6px;font-size:6px;color:#666;text-align:right}
"""


def _render_body(spec: ScreenSpec, compact: bool = False) -> str:
    """Shared body rendering for both normal and compact versions."""
    main_sec = spec.sections[0]
    secondary = spec.sections[1:]

    body_parts = [
        '<div class="screen">',
        f'<div class="titlebar"><span>{spec.screen_title}</span>'
        f'<span style="font-size:{"7" if compact else "10"}px;opacity:0.7">Charisma ERP</span></div>',
        _render_toolbar(main_sec),
        '<div class="main-area">',
        _render_filter_panel(main_sec),
        _render_grid(main_sec),
        "</div>",
    ]

    for sec in secondary:
        total = _calc_total(sec)
        total_label = (
            f'<span style="font-size:{"6" if compact else "10"}px;font-weight:normal;color:#555">'
            f'Intrari ≤ data filtru &nbsp;|&nbsp; Total: '
            f'<strong style="color:#1a3a5c">{int(total):,}'.replace(",", ".") + "</strong></span>"
        ) if total is not None else ""
        body_parts.append(
            f'<div class="sec-header" style="display:flex;justify-content:space-between;align-items:center">'
            f'<span>{sec.title}</span>{total_label}</div>'
        )
        body_parts.append(_render_grid(sec, is_secondary=True, total=total))

    body_parts.append(f'<div class="footer">Generat din: {spec.source_file}</div>')
    body_parts.append("</div>")
    return "".join(body_parts)


def _render_overview(overview: dict) -> str:
    flux = "".join(f"<li>{s}</li>" for s in overview.get("flux", []))
    legaturi = overview.get("legaturi", "")
    return (
        '<div style="max-width:1100px;background:#eef4fb;border:1px solid #b8cfe4;'
        'border-radius:4px;padding:10px 14px;margin-bottom:10px;font-size:12px">'
        f'<div style="font-weight:bold;color:#1a3a5c;margin-bottom:6px">Prezentare generală</div>'
        f'<p style="margin:0 0 6px 0">{overview.get("scop", "")}</p>'
        + (f"<ol style='margin:0 0 6px 18px;padding:0'>{flux}</ol>" if flux else "")
        + (f'<p style="margin:0;font-style:italic">{legaturi}</p>' if legaturi else "")
        + "</div>"
    )


def write_html(spec: ScreenSpec, output_path: Path, overview: dict | None = None):
    if not spec.sections:
        return
    overview_html = _render_overview(overview) if overview else ""
    html = (
        f'<!DOCTYPE html>\n<html lang="ro">\n<head>\n'
        f'<meta charset="UTF-8"/>\n'
        f"<title>{spec.screen_title} — Charisma ERP Mockup</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n"
        + overview_html
        + _render_body(spec, compact=False)
        + "\n</body>\n</html>"
    )
    output_path.write_text(html, encoding="utf-8")


def write_html_compact(spec: ScreenSpec, output_path: Path):
    """Compact version — smaller fonts and dimensions, fits in a Word document page."""
    if not spec.sections:
        return
    html = (
        f'<!DOCTYPE html>\n<html lang="ro">\n<head>\n'
        f'<meta charset="UTF-8"/>\n'
        f"<title>{spec.screen_title} — Charisma ERP Mockup (compact)</title>\n"
        f"<style>{_STYLE_COMPACT}</style>\n</head>\n<body>\n"
        + _render_body(spec, compact=True)
        + "\n</body>\n</html>"
    )
    output_path.write_text(html, encoding="utf-8")
