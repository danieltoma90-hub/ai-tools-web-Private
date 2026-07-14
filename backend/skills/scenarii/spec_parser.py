# -*- coding: utf-8 -*-
"""Parser pentru specificatia de client (docx derivat din Model Company).

Extrage:
- titlurile de capitole normalizate (pt. excluderea scenariilor standard)
- numerotarea capitolelor (pt. coloanele Capitol/Subcapitol la scenariile noi)
- sectiunile "Cerinte specifice identificate in urma Analizei": fiecare H4
  devine o cerinta cu cod de trasabilitate (CR.xx/OF.xx) si textul aferent
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document

SPECIFIC_MARKER = "cerinte specifice identificate in urma analizei"
# coduri de trasabilitate din titlurile H4: CR.00.01 / CR01.02 / OF08.02 etc.
_CODE_RE = re.compile(r"\(?\b((?:CR|OF)[\s.]?\d{1,2}[.]\d{1,2})\)?", re.I)


def norm_txt(t: str) -> str:
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("–", "-").replace("—", "-").lower()
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class SpecificRequirement:
    code: str            # CR.00.01 / OF08.02 / "" daca nu are cod
    title: str           # titlul H4 (fara cod)
    text: str            # corpul cerintei
    module_h2: str       # capitolul H2 parinte (ex: Articole, Modul Achizitii)
    module_no: str       # numarul capitolului H2 (ex: 5.1)
    chapter_no: str      # numarul sectiunii de cerinte (ex: 4.1.15)
    item_no: str         # numarul cerintei (ex: 4.1.15.1)


@dataclass
class ClientSpec:
    titles: set[str] = field(default_factory=set)     # titluri normalizate
    numbers: dict[str, str] = field(default_factory=dict)  # cale normalizata -> "5.1.2"
    requirements: list[SpecificRequirement] = field(default_factory=list)


def parse_client_spec(docx_path: Path) -> ClientSpec:
    doc = Document(str(docx_path))
    spec = ClientSpec()

    counters = [0, 0, 0, 0]
    stack: dict[int, str] = {}
    in_specific: bool = False
    specific_no = ""
    current_req: SpecificRequirement | None = None

    for p in doc.paragraphs:
        style = p.style.name if p.style else ""
        text = p.text.strip()
        if not text:
            continue
        m = re.match(r"Heading ([1-4])$", style, re.I)
        if not m:
            # corp de text — se ataseaza cerintei curente
            if current_req is not None:
                current_req.text += ("\n" if current_req.text else "") + text
            continue

        lvl = int(m.group(1))
        counters[lvl - 1] += 1
        for l in range(lvl, 4):
            counters[l] = 0
        stack[lvl] = text
        for l in range(lvl + 1, 5):
            stack.pop(l, None)

        num = ".".join(str(c) for c in counters[:lvl])
        path = " > ".join(stack[l] for l in range(1, lvl + 1) if l in stack)
        spec.titles.add(norm_txt(text))
        spec.numbers[norm_txt(path)] = num

        if lvl <= 3:
            current_req = None
            in_specific = lvl == 3 and norm_txt(text) == SPECIFIC_MARKER
            if in_specific:
                specific_no = num
            continue

        # H4
        if in_specific:
            code_m = _CODE_RE.search(text)
            code = code_m.group(1).replace(" ", "") if code_m else ""
            title = _CODE_RE.sub("", text).strip(" -–—()")
            current_req = SpecificRequirement(
                code=code, title=title, text="",
                module_h2=stack.get(2, ""),
                module_no=".".join(str(c) for c in counters[:2]),
                chapter_no=specific_no, item_no=num,
            )
            spec.requirements.append(current_req)
        else:
            current_req = None

    return spec
