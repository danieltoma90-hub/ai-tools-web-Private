"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import ContextStep from "@/components/ContextStep";
import {
  uploadSourceFile,
  postMinuta,
  pollMinutaJob,
  postMinutaFree,
} from "@/lib/api";
import { isColdStartError, pollJob } from "@/lib/poll";

type State = "idle" | "processing" | "done" | "error";
type Mode = "ai" | "free";

function freeStepLabel(step: string): string {
  if (step === "metadata") return "Extrag metadatele întâlnirii...";
  const chunk = step.match(/^chunk:(\d+)\/(\d+)$/);
  if (chunk) return `Procesez partea ${chunk[1]} din ${chunk[2]} a transcriptului...`;
  if (step === "synthesis") return "Combin totul în minuta finală...";
  if (step === "building") return "Se generează documentul Word...";
  return "Se procesează...";
}

export default function MinutaPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("ai");
  const [contextPath, setContextPath] = useState("");
  const [contextLabel, setContextLabel] = useState("");
  const [freeLabel, setFreeLabel] = useState("Se inițializează...");
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    previewHtml: string;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
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

  async function handleGenerateAI() {
    if (!file) return;
    setState("processing");
    setError("");
    cancelledRef.current = false;

    try {
      const storagePath = await incarca(file);
      if (cancelledRef.current) return;
      const { job_id } = await postMinuta(
        storagePath,
        file.name,
        contextPath || undefined
      );

      const job = await pollJob(() => pollMinutaJob(job_id), {
        cancelled: () => cancelledRef.current,
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

  async function handleGenerateFree() {
    if (!file) return;
    setState("processing");
    setFreeLabel("Se inițializează...");
    setError("");
    cancelledRef.current = false;

    try {
      setFreeLabel("Încarc transcriptul...");
      const storagePath = await incarca(file);
      if (cancelledRef.current) return;

      let job_id: string;
      let est_minutes: number | undefined;
      try {
        ({ job_id, est_minutes } = await postMinutaFree(storagePath, file.name));
      } catch (initErr) {
        // Render free tier se adoarme dupa inactivitate — retry automat dupa 5s
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          setFreeLabel("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          ({ job_id, est_minutes } = await postMinutaFree(storagePath, file.name));
        } else {
          throw initErr;
        }
      }
      if (est_minutes) {
        setFreeLabel(`Procesare pornită — durează aproximativ ${est_minutes} minute...`);
      }

      const job = await pollJob(() => pollMinutaJob(job_id), {
        cancelled: () => cancelledRef.current,
        onStep: (step) => setFreeLabel(freeStepLabel(step)),
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

  function handleGenerate() {
    return mode === "free" ? handleGenerateFree() : handleGenerateAI();
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
          description="Transcript Teams (.vtt sau .docx) → Format F.05"
          tool="minuta"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <div className="flex rounded-lg border border-slate-200 overflow-hidden w-fit">
              <button
                onClick={() => setMode("ai")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  mode === "ai"
                    ? "bg-[#18257f] text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                ✨ Cu AI (Claude)
              </button>
              <button
                onClick={() => setMode("free")}
                className={`px-4 py-2 text-sm font-medium transition-colors border-l border-slate-200 ${
                  mode === "free"
                    ? "bg-emerald-600 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                ⚡ Free (Llama)
              </button>
            </div>

            {mode === "free" && (
              <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                Versiunea Free procesează întregul transcript, bucată cu bucată, pe API-ul gratuit Groq. O întâlnire de 1 oră durează ~7-8 minute (limitele gratuite permit 1 apel/minut) — durata estimată și progresul sunt afișate la pornire. Fișierele foarte mari (4+ ore) necesită versiunea Cu AI.
              </p>
            )}

            {mode === "ai" && (
              <ContextStep
                value={contextPath}
                onChange={(path, label) => {
                  setContextPath(path);
                  setContextLabel(label);
                }}
              />
            )}

            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
              <h3 className="text-sm font-bold text-[#18257f]">
                {mode === "ai" ? "Pasul 2 · Transcript ședință" : "Transcript ședință"}
              </h3>
              <UploadZone
                accept=".vtt,.docx"
                label=".vtt sau .docx"
                onFile={setFile}
              />
              {mode === "ai" && contextPath && (
                <p className="text-xs text-slate-500">
                  Se va genera folosind contextul{" "}
                  <span className="font-semibold text-[#18257f]">{contextLabel}</span>.
                </p>
              )}
            </div>
            <button
              onClick={handleGenerate}
              disabled={!file}
              className={`w-full text-white py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                mode === "free"
                  ? "bg-emerald-600 hover:bg-emerald-700"
                  : "bg-[#18257f] hover:bg-[#131e66]"
              }`}
            >
              {mode === "free" ? "⚡ Generează Free" : "✨ Generează cu AI"}
            </button>
          </div>
        )}

        {state === "processing" && (
          <ProcessingSpinner
            label={mode === "free" ? freeLabel : undefined}
            onCancel={renuntaLaAsteptare}
          />
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
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
            </div>
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
