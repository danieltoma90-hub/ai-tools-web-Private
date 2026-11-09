import logging
import os
import tempfile
from pathlib import Path

from ai_errors import mesaj_eroare_ai
from skills.mockup import ai_enricher
from skills.mockup.parser import parse_excel
from skills.mockup.word_parser import parse_word
from skills.mockup.word_writer import write_word
from skills.mockup.html_writer import write_html
from skills.mockup.descriptions_builder import build_descriptions


logger = logging.getLogger(__name__)

def _mktemp_path(suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return Path(name)


def _load_spec(input_path: Path):
    """Parseaza fisierul de intrare in (spec, descriptions). Accepta .xlsx sau .docx."""
    ext = input_path.suffix.lower()
    if ext == ".xlsx":
        spec = parse_excel(input_path)
        return spec, build_descriptions(spec)
    if ext == ".docx":
        return parse_word(input_path)
    raise ValueError(f"Format nesuportat: {ext}. Folosiți .xlsx sau .docx.")


def estimate_mockup_job(input_path: Path) -> dict:
    """Pre-check: tokeni necesari pentru imbogatirea AI a acestui ecran."""
    spec, descriptions = _load_spec(input_path)
    has_content = any(
        s.filter_fields or s.buttons or s.columns for s in spec.sections
    )
    if not has_content:
        raise ValueError(
            "Nu am recunoscut structura ecranului în fișier. Sheet-ul „Ecran” trebuie "
            "să conțină fie o zonă de filtrare („Zona de filtrare”/„Filtre” pe coloana A), "
            "fie titlul ecranului urmat de butoane și de antetul grid-ului."
        )
    est_tokens = ai_enricher.estimate_enrich_tokens(spec, descriptions)
    return {
        "est_tokens": est_tokens,
        "est_minutes": 1,
        "fits_budget": True,
    }


async def run_mockup_pipeline(
    input_path: Path,
    on_step=None,
) -> tuple[Path, str, bool, str]:
    """Returns (docx_path, html_content, ai_used, motiv_fara_ai). Accepts .xlsx or .docx.

    Imbogatirea cu Claude se incearca mereu. Daca pica, documentul iese oricum, cu
    descrierile deterministe — dar motivul urca pana in pagina: fara el, o cheie
    revocata ar degrada fiecare mockup fara ca nimeni sa afle de ce.
    """
    if on_step:
        on_step("parsing")
    spec, descriptions = _load_spec(input_path)

    ai_used, motiv = False, ""
    if on_step:
        on_step("ai")
    try:
        descriptions = await ai_enricher.enrich(spec, descriptions)
        ai_used = True
    except Exception as e:
        motiv = mesaj_eroare_ai(e)
        logger.warning("mockup: imbogatirea AI a esuat, raman descrierile deterministe: %s", e)

    if on_step:
        on_step("building")
    overview = descriptions.get("prezentare_generala")

    html_path = _mktemp_path(".html")
    write_html(spec, html_path, overview=overview)
    html = html_path.read_text(encoding="utf-8") if html_path.stat().st_size else ""
    html_path.unlink()

    docx_path = _mktemp_path(".docx")
    write_word(spec, descriptions, docx_path)
    return docx_path, html, ai_used, motiv
