from __future__ import annotations
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from parser import ScreenSpec, Section

# Color palette — matches HTML stylesheet
_C_TITLE_BG     = (26, 58, 92)
_C_TITLE_FG     = (255, 255, 255)
_C_TOOLBAR_BG   = (232, 232, 232)
_C_TOOLBAR_LINE = (154, 184, 212)
_C_BTN_DIRECT   = (0, 120, 212)
_C_BTN_ACTION   = (92, 122, 158)
_C_BTN_GENERATE = (46, 107, 46)
_C_FILTER_BG    = (220, 230, 241)
_C_FILTER_LINE  = (184, 207, 228)
_C_FILTER_MAND  = (192, 57, 43)
_C_GRID_HDR     = (26, 58, 92)
_C_GRID_HDR_LINE= (45, 90, 142)
_C_ROW_ODD      = (255, 255, 255)
_C_ROW_EVEN     = (245, 248, 255)
_C_ROW_LINE     = (221, 221, 221)
_C_SEC_HDR_BG   = (232, 240, 232)
_C_SEC_HDR_FG   = (45, 90, 45)
_C_SEC_GRID_HDR = (74, 122, 74)
_C_SEC_GRID_LINE= (106, 154, 106)
_C_BORDER       = (170, 170, 170)
_C_WHITE        = (255, 255, 255)
_C_DARK         = (30, 30, 30)
_C_GRAY         = (136, 136, 136)

_FONT_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (_FONT_BOLD if bold else _FONT_REGULAR):
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    return int(draw.textlength(text, font=font))


def _trunc(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> str:
    if _text_w(draw, text, font) <= max_w:
        return text
    while text and _text_w(draw, text + "…", font) > max_w:
        text = text[:-1]
    return text + "…"


def _rect(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, fill, outline=None, width=1):
    draw.rectangle([x1, y1, x2, y2], fill=fill, outline=outline, width=width)


def _centered_text(draw, x, y, w, h, text, font, color):
    bb = font.getbbox(text)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((x + (w - tw) // 2, y + (h - th) // 2 - bb[1]), text, fill=color, font=font)


def write_mockup_image(spec: ScreenSpec) -> bytes:
    if not spec.sections:
        img = Image.new("RGB", (900, 80), _C_WHITE)
        return _img_bytes(img)

    main_sec = spec.sections[0]
    secondary = spec.sections[1:]

    W          = 900
    TITLE_H    = 30
    TOOLBAR_H  = 36
    FILTER_W   = 168
    ROW_H      = 21
    HDR_H      = 26
    PAD        = 6
    MAX_ROWS   = 6   # max data rows to show in main grid

    f8  = _font(8)
    f9  = _font(9)
    f9b = _font(9, bold=True)
    f10b= _font(10, bold=True)
    f11b= _font(11, bold=True)

    # Pre-compute heights
    filter_count = len(main_sec.filter_fields)
    mand_count   = sum(1 for f in main_sec.filter_fields if f.mandatory)
    opt_count    = filter_count - mand_count
    filter_panel_h = 28 + mand_count * 30 + (18 if opt_count else 0) + opt_count * 30 + 8

    grid_rows  = min(len(main_sec.data_rows), MAX_ROWS) if main_sec.data_rows else 3
    grid_h     = HDR_H + grid_rows * ROW_H

    main_h = max(filter_panel_h, grid_h, 80)

    sec_heights = []
    for sec in secondary:
        sec_data_rows = min(len(sec.data_rows), 4) if sec.data_rows else 2
        sec_heights.append(28 + HDR_H + sec_data_rows * ROW_H)

    total_h = TITLE_H + TOOLBAR_H + main_h + sum(sec_heights) + 6
    img = Image.new("RGB", (W, total_h), _C_WHITE)
    draw = ImageDraw.Draw(img)

    y = 0

    # ── Title bar ────────────────────────────────────────────────────────
    _rect(draw, 0, y, W, y + TITLE_H, _C_TITLE_BG)
    title = _trunc(spec.screen_title, f11b, W - 110, draw)
    draw.text((10, y + 7), title, fill=_C_WHITE, font=f11b)
    draw.text((W - 85, y + 9), "Charisma ERP", fill=(180, 200, 220), font=f8)
    y += TITLE_H

    # ── Toolbar ──────────────────────────────────────────────────────────
    _rect(draw, 0, y, W, y + TOOLBAR_H, _C_TOOLBAR_BG)
    draw.line([(0, y + TOOLBAR_H - 2), (W, y + TOOLBAR_H - 2)], fill=_C_TOOLBAR_LINE, width=2)

    direct_btns = [b for b in main_sec.buttons if b.group == "direct"]
    action_btns = [b for b in main_sec.buttons if b.group == "actiuni"]

    bx = PAD + 2
    for b in direct_btns:
        tw = _text_w(draw, b.label, f9) + 18
        _rect(draw, bx, y + 7, bx + tw, y + TOOLBAR_H - 7, _C_BTN_DIRECT)
        draw.text((bx + 9, y + 12), b.label, fill=_C_WHITE, font=f9)
        bx += tw + 5

    if action_btns:
        bx += 8
        draw.text((bx, y + 13), "Acțiuni:", fill=(26, 58, 92), font=f9b)
        bx += _text_w(draw, "Acțiuni:", f9b) + 8
        for b in action_btns:
            label = b.label
            tw = min(_text_w(draw, label, f9) + 18, 160)
            if bx + tw > W - 4:
                break
            color = _C_BTN_GENERATE if "genereaza" in label.lower() else _C_BTN_ACTION
            _rect(draw, bx, y + 7, bx + tw, y + TOOLBAR_H - 7, color)
            label_t = _trunc(label, f9, tw - 12, draw)
            draw.text((bx + 9, y + 12), label_t, fill=_C_WHITE, font=f9)
            bx += tw + 5
    y += TOOLBAR_H

    # ── Main area (filter + grid side by side) ───────────────────────────
    draw.rectangle([0, y, W - 1, y + main_h - 1], outline=_C_BORDER)

    # Filter panel
    _rect(draw, 0, y, FILTER_W, y + main_h, _C_FILTER_BG)
    draw.line([(FILTER_W, y), (FILTER_W, y + main_h)], fill=_C_FILTER_LINE, width=2)
    draw.text((PAD, y + PAD), "Zona de filtrare", fill=(26, 58, 92), font=f9b)
    draw.line([(PAD, y + 22), (FILTER_W - PAD, y + 22)], fill=_C_FILTER_LINE)

    fy = y + 28
    mand = [f for f in main_sec.filter_fields if f.mandatory]
    opt  = [f for f in main_sec.filter_fields if not f.mandatory]

    for f in mand:
        lbl = _trunc(f"{f.label} *", f9, FILTER_W - 12, draw)
        draw.text((PAD, fy), lbl, fill=_C_FILTER_MAND, font=f9)
        _rect(draw, PAD, fy + 13, FILTER_W - PAD, fy + 25, _C_WHITE, _C_FILTER_MAND)
        fy += 30

    if opt:
        draw.line([(PAD, fy + 3), (FILTER_W - PAD, fy + 3)], fill=_C_TOOLBAR_LINE)
        draw.text((PAD, fy + 6), "Filtre opționale:", fill=_C_GRAY, font=f8)
        fy += 18
        for f in opt:
            lbl = _trunc(f.label, f9, FILTER_W - 12, draw)
            draw.text((PAD, fy), lbl, fill=(68, 68, 68), font=f9)
            _rect(draw, PAD, fy + 13, FILTER_W - PAD, fy + 25, _C_WHITE, _C_BORDER)
            fy += 30

    # Grid
    GRID_X = FILTER_W + 1
    GRID_W = W - GRID_X

    visible_cols = [c for c in main_sec.columns if c.name.lower() not in ("selectat", "selecteaza")]
    CB_W = 22
    col_w = (GRID_W - CB_W) // max(len(visible_cols), 1) if visible_cols else GRID_W
    all_names = ["✓"] + [c.name for c in visible_cols]
    all_widths = [CB_W] + [col_w] * len(visible_cols)

    gy = y
    # Header
    _rect(draw, GRID_X, gy, W, gy + HDR_H, _C_GRID_HDR)
    cx = GRID_X
    for name, cw in zip(all_names, all_widths):
        nt = _trunc(name, f9, cw - 4, draw)
        _centered_text(draw, cx, gy, cw, HDR_H, nt, f9, _C_WHITE)
        draw.line([(cx + cw, gy), (cx + cw, gy + HDR_H)], fill=_C_GRID_HDR_LINE)
        cx += cw
    gy += HDR_H

    rows_to_show = main_sec.data_rows[:MAX_ROWS] if main_sec.data_rows else [[] for _ in range(3)]
    for r_idx, row_data in enumerate(rows_to_show):
        bg = _C_ROW_ODD if r_idx % 2 == 0 else _C_ROW_EVEN
        _rect(draw, GRID_X, gy, W, gy + ROW_H, bg)
        cx = GRID_X
        # Checkbox
        _rect(draw, cx + 5, gy + 4, cx + CB_W - 5, gy + ROW_H - 4, _C_WHITE, _C_BORDER)
        cx += CB_W
        for val, cw in zip(row_data, all_widths[1:]):
            vt = _trunc(str(val) if val else "", f9, cw - 6, draw)
            draw.text((cx + 3, gy + 5), vt, fill=_C_DARK, font=f9)
            draw.line([(cx + cw, gy), (cx + cw, gy + ROW_H)], fill=_C_ROW_LINE)
            cx += cw
        draw.line([(GRID_X, gy + ROW_H), (W, gy + ROW_H)], fill=_C_ROW_LINE)
        gy += ROW_H

    y += main_h

    # ── Secondary sections ───────────────────────────────────────────────
    for sec, sec_h in zip(secondary, sec_heights):
        draw.line([(0, y), (W, y)], fill=(92, 138, 92), width=2)
        _rect(draw, 0, y, W, y + 28, _C_SEC_HDR_BG)
        title_t = _trunc(sec.title, f10b, W - 20, draw)
        draw.text((10, y + 7), title_t, fill=_C_SEC_HDR_FG, font=f10b)
        gy = y + 28

        sc_w = W // max(len(sec.columns), 1) if sec.columns else W
        _rect(draw, 0, gy, W, gy + HDR_H, _C_SEC_GRID_HDR)
        cx = 0
        for col in sec.columns:
            nt = _trunc(col.name, f9, sc_w - 4, draw)
            _centered_text(draw, cx, gy, sc_w, HDR_H, nt, f9, _C_WHITE)
            draw.line([(cx + sc_w, gy), (cx + sc_w, gy + HDR_H)], fill=_C_SEC_GRID_LINE)
            cx += sc_w
        gy += HDR_H

        rows_to_show = sec.data_rows[:4] if sec.data_rows else [[] for _ in range(2)]
        for r_idx, row_data in enumerate(rows_to_show):
            bg = _C_ROW_ODD if r_idx % 2 == 0 else _C_ROW_EVEN
            _rect(draw, 0, gy, W, gy + ROW_H, bg)
            cx = 0
            for val, col in zip(row_data, sec.columns):
                vt = _trunc(str(val) if val else "", f9, sc_w - 6, draw)
                draw.text((cx + 3, gy + 5), vt, fill=_C_DARK, font=f9)
                draw.line([(cx + sc_w, gy), (cx + sc_w, gy + ROW_H)], fill=_C_ROW_LINE)
                cx += sc_w
            draw.line([(0, gy + ROW_H), (W, gy + ROW_H)], fill=_C_ROW_LINE)
            gy += ROW_H

        y += sec_h

    return _img_bytes(img)


def _img_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
