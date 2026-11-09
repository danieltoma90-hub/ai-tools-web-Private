"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import Etape from "@/components/Etape";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import EroareGenerare from "@/components/EroareGenerare";
import ContextStep from "@/components/ContextStep";
import OptiuniMinutaPanel, { OPTIUNI_IMPLICITE, type OptiuniMinuta } from "@/components/OptiuniMinuta";
import { postMinuta, pollMinutaJob } from "@/lib/api";
import { useAcces } from "@/lib/acces";
import { useGenerare } from "@/lib/generare";
import { ETAPE_MINUTA_AI } from "@/lib/progres";

// Teams împarte o zi de ședințe în mai multe înregistrări; serverul le reunește în aceeași minută.
const MAX_INREGISTRARI = 5;
// notițele echipei: câteva pagini, nu un al doilea transcript (aceeași limită ca pe server)
const MAX_NOTITE = 30000;

function aiStepLabel(step: string): string {
  const e = step.match(/^extrageri:(\d+)\/(\d+)$/);
  if (e) return `Analizez transcriptul — ${e[1]} din ${e[2]} extrageri gata...`;
  if (step === "building") return "Se generează documentul Word...";
  return "Se procesează...";
}

export default function MinutaPage() {
  const [files, setFiles] = useState<File[]>([]);
  // cheia zonei de încărcare: se schimbă după fiecare fișier ales, ca zona să revină goală
  const [zonaKey, setZonaKey] = useState(0);
  const [notite, setNotite] = useState("");
  const [contextPath, setContextPath] = useState("");
  const [contextLabel, setContextLabel] = useState("");
  const [optiuni, setOptiuni] = useState<OptiuniMinuta>(OPTIUNI_IMPLICITE);
  // testul de cost al administratorului: același transcript, alt efort
  const [efort, setEfort] = useState("");
  const { acces } = useAcces();
  const g = useGenerare<Awaited<ReturnType<typeof pollMinutaJob>>>({
    modul: "Minută",
    etichetaPas: aiStepLabel,
  });

  function adaugaFisier(f: File) {
    setFiles((fs) => (fs.length >= MAX_INREGISTRARI ? fs : [...fs, f]));
    setZonaKey((k) => k + 1);
  }

  function scoateFisier(index: number) {
    setFiles((fs) => fs.filter((_, i) => i !== index));
  }

  function genereaza() {
    if (!files.length || notite.length > MAX_NOTITE) return;
    const [file, ...alte] = files;
    g.porneste(async ({ incarca, eticheta }) => {
      eticheta(files.length > 1 ? `Încarc cele ${files.length} înregistrări...` : "Încarc transcriptul...");
      const storagePath = await incarca(file, "minuta");
      const inregistrari: { storage_path: string; filename: string }[] = [];
      for (const f of alte) {
        inregistrari.push({ storage_path: await incarca(f, "minuta"), filename: f.name });
      }
      eticheta("Pornesc analiza...");
      const { job_id } = await postMinuta(storagePath, file.name, contextPath || undefined, optiuni, {
        inregistrari,
        notite,
        efort: acces?.admin ? efort : undefined,
      });
      return job_id;
    }, pollMinutaJob);
  }

  function reset() {
    setFiles([]);
    setNotite("");
    g.reset();
  }

  const r = g.rezultat;

  return (
    <div className="p-6 max-w-5xl">
        <ToolCard
          icon="📝"
          title="Minută Întâlnire"
          description="Transcript Teams (.vtt sau .docx) → Format F.05, în română sau în engleză"
          tool="minuta"
          recentKey={g.recentKey}
        />
        <Etape faza={g.faza} intrare="Transcript și opțiuni" rezultat="Minuta" />

        {g.faza === "idle" && (
          <div className="flex flex-col gap-4">
            <ContextStep
              value={contextPath}
              onChange={(path, label) => {
                setContextPath(path);
                setContextLabel(label);
              }}
            />

            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
              <h3 className="text-sm font-bold text-[#18257f]">Pasul 2 · Transcript ședință</h3>
              {files.length > 0 && (
                <ul className="flex flex-col gap-1.5">
                  {files.map((f, i) => (
                    <li
                      key={`${f.name}-${i}`}
                      className="flex items-center justify-between gap-2 bg-[#eef0f8] rounded-lg px-3 py-2"
                    >
                      <span className="text-xs font-medium text-[#131e66] truncate">
                        {files.length > 1 ? `${i + 1}. ` : ""}
                        {f.name}
                      </span>
                      <button
                        type="button"
                        onClick={() => scoateFisier(i)}
                        className="text-xs text-slate-400 hover:text-red-600 shrink-0"
                      >
                        ✕ Elimină
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {files.length < MAX_INREGISTRARI && (
                <UploadZone
                  key={zonaKey}
                  accept=".vtt,.docx"
                  label={files.length ? "încă o înregistrare din aceeași zi" : ".vtt sau .docx"}
                  onFile={adaugaFisier}
                />
              )}
              <p className="text-xs text-slate-500">
                {files.length > 1
                  ? `Cele ${files.length} înregistrări se reunesc într-o singură minută, în ordinea de mai sus; ` +
                    "dacă sunt ședințe diferite cu aceeași companie, minuta le separă pe capitole."
                  : "Poți adăuga până la 5 înregistrări din aceeași zi (Teams împarte adesea o ședință în " +
                    "mai multe fișiere) — se reunesc într-o singură minută."}
              </p>
              {contextPath && (
                <p className="text-xs text-slate-500">
                  Se va genera folosind contextul{" "}
                  <span className="font-semibold text-[#18257f]">{contextLabel}</span>.
                </p>
              )}
            </div>

            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
              <h3 className="text-sm font-bold text-[#18257f]">
                Pasul 3 · Notițele echipei din ședință{" "}
                <span className="font-normal text-slate-400">(opțional)</span>
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Lipește notițele luate în ședință. Corectează ce deformează transcrierea automată — nume,
                funcții, cifre, sisteme — și spun cine ce a prezentat. Ce vine din ele e marcat{" "}
                <b>{optiuni.limba === "en" ? "[NOTES]" : "[NOTIȚE]"}</b> când marcajele sunt active.
              </p>
              <textarea
                value={notite}
                onChange={(e) => setNotite(e.target.value)}
                rows={5}
                placeholder={"Ex.\nAna Ionescu – directoare economică\nbugetul aprobat: 4,5 milioane"}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
              />
              {notite.length > MAX_NOTITE && (
                <p className="text-xs text-red-600">
                  Notițele au {notite.length} de caractere — cel mult {MAX_NOTITE}.
                </p>
              )}
            </div>

            <OptiuniMinutaPanel value={optiuni} onChange={setOptiuni} titlu="Pasul 4 · Opțiuni minută" />

            {acces?.admin && (
              <div className="bg-slate-50 border border-dashed border-slate-300 rounded-xl p-4 flex flex-col gap-2">
                <h3 className="text-sm font-bold text-[#18257f]">
                  Test de cost <span className="font-normal text-slate-400">(doar administratori)</span>
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Efortul spune cât gândește modelul înainte să scrie și dă cea mai mare parte din cost.
                  Generează aceeași ședință o dată pe <b>low</b> și o dată pe <b>medium</b>, apoi compară
                  minutele și costul din Utilizatori → Consum Claude.
                </p>
                <select
                  value={efort}
                  onChange={(e) => setEfort(e.target.value)}
                  className="w-fit border border-slate-300 rounded-lg px-3 py-1.5 text-xs bg-white"
                >
                  <option value="">Implicit (medium)</option>
                  <option value="low">low — mai ieftin</option>
                  <option value="medium">medium</option>
                  <option value="high">high — mai scump</option>
                </select>
              </div>
            )}

            <button
              onClick={genereaza}
              disabled={!files.length || notite.length > MAX_NOTITE}
              className="w-full text-white py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors bg-[#18257f] hover:bg-[#131e66]"
            >
              {optiuni.limba === "en" ? "✨ Generează minuta în engleză" : "✨ Generează minuta"}
            </button>
          </div>
        )}

        {g.faza === "processing" && (
          <ProcessingSpinner label={g.eticheta} onCancel={g.renunta} etape={ETAPE_MINUTA_AI} step={g.step} />
        )}

        {g.faza === "done" && r && (
          <ResultPanel
            filename={r.filename!}
            docxB64={r.docx_b64!}
            previewHtml={r.preview_html ?? ""}
            onReset={reset}
            resetLabel="+ Generează altă minută"
          />
        )}

        {g.faza === "error" && <EroareGenerare eroare={g.eroare} onReset={reset} />}
    </div>
  );
}
