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

function aiStepLabel(step: string): string {
  const e = step.match(/^extrageri:(\d+)\/(\d+)$/);
  if (e) return `Analizez transcriptul — ${e[1]} din ${e[2]} extrageri gata...`;
  if (step === "building") return "Se generează documentul Word...";
  return "Se procesează...";
}

export default function MinutaPage() {
  const [file, setFile] = useState<File | null>(null);
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

  async function handleGenerate() {
    if (!file) return;
    setState("processing");
    setAiLabel("Încarc transcriptul...");
    setStep(null);
    setError("");
    cancelledRef.current = false;

    try {
      const storagePath = await incarca(file);
      if (cancelledRef.current) return;
      setAiLabel("Pornesc analiza...");
      const { job_id } = await postMinuta(storagePath, file.name, contextPath || undefined, optiuni);

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
    setFile(null);
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
              <UploadZone accept=".vtt,.docx" label=".vtt sau .docx" onFile={setFile} />
              {contextPath && (
                <p className="text-xs text-slate-500">
                  Se va genera folosind contextul{" "}
                  <span className="font-semibold text-[#18257f]">{contextLabel}</span>.
                </p>
              )}
            </div>

            <OptiuniMinutaPanel value={optiuni} onChange={setOptiuni} titlu="Pasul 3 · Opțiuni minută" />

            <button
              onClick={handleGenerate}
              disabled={!file}
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
