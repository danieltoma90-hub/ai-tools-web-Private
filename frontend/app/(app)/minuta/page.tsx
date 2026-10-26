"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import ContextStep from "@/components/ContextStep";
import OptiuniMinutaPanel, { OPTIUNI_IMPLICITE, type OptiuniMinuta } from "@/components/OptiuniMinuta";
import { uploadSourceFile, postMinuta, pollMinutaJob } from "@/lib/api";
import { isColdStartError, pollJob } from "@/lib/poll";
import { ETAPE_MINUTA_AI } from "@/lib/progres";

type State = "idle" | "processing" | "done" | "error";

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
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [contextPath, setContextPath] = useState("");
  const [contextLabel, setContextLabel] = useState("");
  const [aiLabel, setAiLabel] = useState("Se inițializează...");
  const [step, setStep] = useState<string | null>(null);
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    previewHtml: string;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const [optiuni, setOptiuni] = useState<OptiuniMinuta>(OPTIUNI_IMPLICITE);
  const cancelledRef = useRef(false);

  /** Urcă transcriptul direct în storage, cu o reîncercare dacă serverul dormea. */
  async function incarca(f: File): Promise<string> {
    try {
      const { storage_path } = await uploadSourceFile(f, "minuta");
      return storage_path;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (!isColdStartError(msg)) throw err;
      await new Promise((r) => setTimeout(r, 5000));
      const { storage_path } = await uploadSourceFile(f, "minuta");
      return storage_path;
    }
  }

  function adaugaFisier(f: File) {
    setFiles((fs) => (fs.length >= MAX_INREGISTRARI ? fs : [...fs, f]));
    setZonaKey((k) => k + 1);
  }

  function scoateFisier(index: number) {
    setFiles((fs) => fs.filter((_, i) => i !== index));
  }

  async function handleGenerate() {
    if (!files.length || notite.length > MAX_NOTITE) return;
    const [file, ...alte] = files;
    setState("processing");
    setAiLabel(files.length > 1 ? `Încarc cele ${files.length} înregistrări...` : "Încarc transcriptul...");
    setStep(null);
    setError("");
    cancelledRef.current = false;

    try {
      const storagePath = await incarca(file);
      const inregistrari: { storage_path: string; filename: string }[] = [];
      for (const f of alte) {
        if (cancelledRef.current) return;
        inregistrari.push({ storage_path: await incarca(f), filename: f.name });
      }
      if (cancelledRef.current) return;
      setAiLabel("Pornesc analiza...");
      const { job_id } = await postMinuta(storagePath, file.name, contextPath || undefined, optiuni, {
        inregistrari,
        notite,
      });

      const job = await pollJob(() => pollMinutaJob(job_id), {
        cancelled: () => cancelledRef.current,
        onStep: (s) => {
          setStep(s);
          setAiLabel(aiStepLabel(s));
        },
      });
      if (!job) return;

      setResult({
        filename: job.filename!,
        docxB64: job.docx_b64!,
        previewHtml: job.preview_html!,
      });
      setState("done");
      setHistoryKey((k) => k + 1);
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  function reset() {
    cancelledRef.current = true;
    setFiles([]);
    setNotite("");
    setResult(null);
    setState("idle");
    setError("");
  }

  /** Oprește doar urmărirea din pagină — jobul rulează mai departe pe server. */
  function renuntaLaAsteptare() {
    cancelledRef.current = true;
    setState("idle");
  }

  return (
    <div className="flex h-screen">
      <div className="flex-1 p-6 overflow-auto">
        <ToolCard
          icon="📝"
          title="Minută Întâlnire"
          description="Transcript Teams (.vtt sau .docx) → Format F.05, în română sau în engleză"
          tool="minuta"
        />

        {state === "idle" && (
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

            <button
              onClick={handleGenerate}
              disabled={!files.length || notite.length > MAX_NOTITE}
              className="w-full text-white py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors bg-[#18257f] hover:bg-[#131e66]"
            >
              {optiuni.limba === "en" ? "✨ Generează minuta în engleză" : "✨ Generează minuta"}
            </button>
          </div>
        )}

        {state === "processing" && (
          <ProcessingSpinner label={aiLabel} onCancel={renuntaLaAsteptare} etape={ETAPE_MINUTA_AI} step={step} />
        )}

        {state === "done" && result && (
          <ResultPanel
            filename={result.filename}
            docxB64={result.docxB64}
            previewHtml={result.previewHtml}
            onReset={reset}
            resetLabel="+ Generează altă minută"
          />
        )}

        {state === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
            <button onClick={reset} className="text-sm text-[#18257f] underline">
              Încearcă din nou
            </button>
          </div>
        )}
      </div>

      <HistoryPanel tool="minuta" refreshKey={historyKey} />
    </div>
  );
}
