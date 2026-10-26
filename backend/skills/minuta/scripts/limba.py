# -*- coding: utf-8 -*-
"""Textele fixe ale minutei, în română și în engleză.

Legenda marcajelor, titlurile secțiunilor adăugate de aplicație și etichetele formularului F.05. Pentru
minuta în engleză, conținutul îl scrie modelul în engleză, iar etichetele din șablon se rescriu după
generare (`docx_to_en`) — aceeași listă cu care s-au convertit local minutele VEDAŞ.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

LANGS = ("ro", "en")

LEGEND = {
    "ro": "**Legenda marcajelor:** **[DEDUCȚIE]** = concluzie, legătură sau atribuire a redactorului, care nu a "
          "fost spusă explicit; **[COMPLETARE]** = cuvinte adăugate ca fraza să aibă sens; "
          "**[CLARIFICARE NEEDED]** = neclar în transcriere, de confirmat.",
    "en": "**Marker legend:** **[INFERENCE]** = a conclusion, link or attribution by the editor that was not "
          "stated explicitly; **[ADDED]** = words added so the sentence makes sense; "
          "**[CLARIFICATION NEEDED]** = unclear in the transcript, to be confirmed.",
}

# marcajul pentru ce vine din notițele echipei, adăugat la legendă doar când minuta le-a folosit
LEGEND_NOTITE = {
    "ro": " **[NOTIȚE]** = confirmat, corectat sau completat din notițele luate de echipa TotalSoft în "
          "ședință; unde transcrierea spune altceva, forma ei este dată în marcaj.",
    "en": " **[NOTES]** = confirmed, corrected or completed from the notes taken by the TotalSoft team in "
          "the meeting; where the transcript says otherwise, its form is given in the marker.",
}


def legenda(limba: str = "ro", notite: bool = False) -> str:
    """Legenda marcajelor din „Context și scop”; cu notițe, și marcajul lor."""
    return LEGEND[limba] + (LEGEND_NOTITE[limba] if notite else "")


# titlurile și antetele secțiunilor pe care le construiește aplicația (nu modelul)
TEXT = {
    "ro": {
        "profil": "Profilul beneficiarului", "profil_header": ["Aspect", "Detaliu"],
        "cerinte": "Cerințe și așteptări exprimate de beneficiar", "cerinte_header": ["Zonă", "Cerință exprimată"],
        "deschise": "Puncte rămase deschise",
        "followup": "Stadiul acțiunilor anterioare",
        "followup_header": ["Acțiune", "Responsabil", "Stare", "Detaliu"], "nediscutata": "Nediscutată",
    },
    "en": {
        "profil": "Client Profile", "profil_header": ["Aspect", "Detail"],
        "cerinte": "Requirements and Expectations Expressed by the Client",
        "cerinte_header": ["Area", "Stated Requirement"],
        "deschise": "Open Points",
        "followup": "Status of Previous Actions",
        "followup_header": ["Action", "Responsible", "Status", "Detail"], "nediscutata": "Not discussed",
    },
}

PREVIEW = {
    "ro": {"titlu": "MINUTA INTALNIRII", "data": "Data", "client": "Client", "subiect": "Subiect",
           "initiator": "Inițiator", "locatia": "Locație", "durata": "Durată",
           "context": "Context și scop", "pasi": "Pași următori"},
    "en": {"titlu": "MEETING MINUTES", "data": "Date", "client": "Client", "subiect": "Subject",
           "initiator": "Initiator", "locatia": "Location", "durata": "Duration",
           "context": "Context and Purpose", "pasi": "Next Steps"},
}

# Etichetele șablonului F05 și textele fixe din build_minuta. Ordinea contează: majusculele înaintea
# formei mici, „>Pag. <” (numărul de pagină) înaintea lui „Pag.”.
DOCX_EN = [
    ("MINUTA INTALNIRII", "MEETING MINUTES"), ("Numar Contract / Data", "Contract No. / Date"),
    ("Cod Proiect", "Project Code"), ("Nume Client", "Client Name"), ("Subiect", "Subject"),
    ("Participanti", "Participants"), ("Distribuit catre", "Distributed to"), ("Locatia", "Location"),
    ("Data intalnirii", "Meeting Date"), ("Durata", "Duration"), ("Context și scop", "Context and Purpose"),
    ("Pași următori", "Next Steps"), ("Minuta Intalnirii", "Meeting Minutes"), (">Pag. <", ">Page <"),
    ("Pag.", "Page"), ('w:val="ro-RO"', 'w:val="en-GB"'),
]


def docx_to_en(path: Path) -> None:
    """Rescrie pe loc, în engleză, etichetele românești ale documentului generat."""
    tmp = path.with_name(path.name + ".en")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                for ro, en in DOCX_EN:
                    text = text.replace(ro, en)
                data = text.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(path)
