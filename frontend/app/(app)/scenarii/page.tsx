"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import Etape from "@/components/Etape";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import EroareGenerare from "@/components/EroareGenerare";
import { postScenariiGenerate, getScenariiJob, type ScenariiJob } from "@/lib/api";
import { useGenerare } from "@/lib/generare";
import { ETAPE_SCENARII } from "@/lib/progres";

function stepLabel(step: string): string {
  if (step === "parsing") return "Analizez specificația și cerințele specifice...";
  const m = step.match(/^gen:(\d+)\/(\d+)$/);
  if (m) return `Generez scenariile specifice — lotul ${m[1]} din ${m[2]}...`;
  if (step === "deps") return "Stabilesc dependențele și planul de execuție...";
  if (step === "building") return "Generez documentul Excel...";
  return "Se procesează...";
}

export default function ScenariPage() {
  const [file, setFile] = useState<File | null>(null);
  const g = useGenerare<ScenariiJob>({ modul: "Scenarii", etichetaPas: stepLabel });

  function genereaza() {
    if (!file) return;
    g.porneste(async ({ incarca, eticheta }) => {
      eticheta("Se încarcă specificația... (fișierele mari pot dura ~1 minut)");
      const storagePath = await incarca(file, "scenarii");
      eticheta("Citesc specificația...");
      return (await postScenariiGenerate(storagePath, file.name)).job_id;
    }, getScenariiJob);
  }

  function reset() {
    setFile(null);
    g.reset();
  }

  const r = g.rezultat;

  return (
    <div className="p-6 max-w-5xl">
      <ToolCard
        icon="🧪"
        title="Scenarii Testare"
        description="Specificație (.docx) → Excel: catalog standard + cerințe specifice client"
        tool="scenarii"
        recentKey={g.recentKey}
      />
      <Etape faza={g.faza} intrare="Specificația" rezultat="Scenariile" />

      {g.faza === "idle" && (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
            Fișierul generat pornește de la catalogul standard (170 scenarii CORE validate),
            adaugă scenarii pentru „Cerințele specifice identificate în urma Analizei” (marcate galben)
            și listează la final ce s-a exclus față de formatul standard.
          </p>
          <UploadZone accept=".docx" label=".docx" onFile={setFile} />
          <button
            onClick={genereaza}
            disabled={!file}
            className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ✨ Generează scenariile
          </button>
        </div>
      )}

      {g.faza === "processing" && (
        <ProcessingSpinner label={g.eticheta} onCancel={g.renunta} etape={ETAPE_SCENARII} step={g.step} />
      )}

      {g.faza === "done" && r && (
        <div className="flex flex-col gap-4">
          {r.summary && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-[#18257f]">{r.summary.core_count}</p>
                <p className="text-[11px] text-slate-500">scenarii standard incluse</p>
              </div>
              <div className="bg-[#fff9c4] border border-amber-200 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-amber-700">{r.summary.specific_count}</p>
                <p className="text-[11px] text-amber-700">
                  specifice client (din {r.summary.requirements} cerințe găsite)
                </p>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-red-600">{r.summary.excluded_count}</p>
                <p className="text-[11px] text-red-600">excluse vs standard</p>
              </div>
            </div>
          )}
          <ResultPanel
            filename={r.filename!}
            docxB64={r.xlsx_b64!}
            previewHtml=""
            onReset={reset}
            downloadLabel="↓ Descarcă .xlsx"
            resetLabel="+ Generează alte scenarii"
          />
        </div>
      )}

      {g.faza === "error" && <EroareGenerare eroare={g.eroare} onReset={reset} />}
    </div>
  );
}
