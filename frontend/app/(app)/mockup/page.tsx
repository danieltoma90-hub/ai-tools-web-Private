"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import Etape from "@/components/Etape";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import EroareGenerare from "@/components/EroareGenerare";
import { postMockupGenerate, getMockupJob, type MockupJob } from "@/lib/api";
import { useGenerare } from "@/lib/generare";
import { ETAPE_MOCKUP } from "@/lib/progres";

function stepLabel(step: string): string {
  if (step === "parsing") return "Analizez fișierul...";
  if (step === "ai") return "Îmbogățesc descrierile cu AI...";
  if (step === "building") return "Generez documentul Word...";
  return "Se procesează...";
}

export default function MockupPage() {
  const [file, setFile] = useState<File | null>(null);
  const g = useGenerare<MockupJob>({ modul: "Mockup", etichetaPas: stepLabel });

  function genereaza() {
    if (!file) return;
    g.porneste(async ({ incarca, eticheta }) => {
      eticheta("Se încarcă fișierul... (fișierele mari pot dura ~1 minut)");
      const storagePath = await incarca(file, "mockup");
      eticheta("Citesc ecranul...");
      return (await postMockupGenerate(storagePath, file.name)).job_id;
    }, getMockupJob);
  }

  function reset() {
    setFile(null);
    g.reset();
  }

  const r = g.rezultat;

  return (
    <div className="p-6 max-w-5xl">
      <ToolCard
        icon="🎨"
        title="Mockup Ecran"
        description="Fișier Excel (.xlsx) sau Word (.docx) → documentația ecranului, în Word și HTML"
        tool="mockup"
        recentKey={g.recentKey}
      />
      <Etape faza={g.faza} intrare="Fișierul ecranului" rezultat="Documentația" />

      {g.faza === "idle" && (
        <div className="flex flex-col gap-4">
          <UploadZone accept=".xlsx,.docx" label=".xlsx sau .docx" onFile={setFile} />
          <p className="text-xs text-slate-500">
            Structura ecranului se citește din fișier, iar Claude scrie prezentarea generală și
            completează descrierile câmpurilor. Durează în jur de un minut.
          </p>
          <button
            onClick={genereaza}
            disabled={!file}
            className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ✨ Generează documentația
          </button>
        </div>
      )}

      {g.faza === "processing" && (
        <ProcessingSpinner label={g.eticheta} onCancel={g.renunta} etape={ETAPE_MOCKUP} step={g.step} />
      )}

      {g.faza === "done" && r && (
        <div className="flex flex-col gap-4">
          {!r.ai_used && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              Documentația a fost generată fără AI — descrierile provin direct din fișierul sursă.
              {r.motiv_fara_ai && (
                <>
                  {" "}
                  <strong>Motiv:</strong> {r.motiv_fara_ai}
                </>
              )}
            </p>
          )}
          <ResultPanel
            filename={r.filename!}
            docxB64={r.docx_b64!}
            previewHtml={r.html ?? ""}
            onReset={reset}
            resetLabel="+ Generează alt mockup"
          />
        </div>
      )}

      {g.faza === "error" && <EroareGenerare eroare={g.eroare} onReset={reset} />}
    </div>
  );
}
