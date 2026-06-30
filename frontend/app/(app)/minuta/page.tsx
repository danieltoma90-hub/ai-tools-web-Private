"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import { postMinuta, pollMinutaJob, postMinutaFree } from "@/lib/api";

type State = "idle" | "processing" | "done" | "error";
type Mode = "ai" | "free";

export default function MinutaPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("ai");
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    previewHtml: string;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  async function handleGenerateAI() {
    if (!file) return;
    setState("processing");
    setError("");
    cancelledRef.current = false;

    try {
      const { job_id } = await postMinuta(file);

      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        const job = await pollMinutaJob(job_id);
        if (cancelledRef.current) return;

        if (job.status === "done") {
          setResult({
            filename: job.filename!,
            docxB64: job.docx_b64!,
            previewHtml: job.preview_html!,
          });
          setState("done");
          setHistoryKey((k) => k + 1);
          return;
        }

        if (job.status === "error") {
          throw new Error(job.error || "Eroare în procesarea minutei");
        }
      }
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  async function handleGenerateFree() {
    if (!file) return;
    setState("processing");
    setError("");
    cancelledRef.current = false;

    try {
      const res = await postMinutaFree(file);
      if (cancelledRef.current) return;
      setResult({
        filename: res.filename,
        docxB64: res.docx_b64,
        previewHtml: res.preview_html,
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

  return (
    <div className="flex h-screen">
      <div className="flex-1 p-6 overflow-auto">
        <ToolCard
          icon="📝"
          title="Minută Întâlnire"
          description="Transcript Teams (.vtt sau .docx) → Format F.05"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            {/* Toggle AI / Free */}
            <div className="flex rounded-lg border border-slate-200 overflow-hidden w-fit">
              <button
                onClick={() => setMode("ai")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  mode === "ai"
                    ? "bg-blue-600 text-white"
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
                ⚡ Free (Groq)
              </button>
            </div>

            {mode === "free" && (
              <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                Versiunea Free folosește Groq (Llama 3.3 70B) — aceeași calitate, fără costuri suplimentare. Generare în ~10-20 secunde.
              </p>
            )}

            <UploadZone
              accept=".vtt,.docx"
              label=".vtt sau .docx"
              onFile={setFile}
            />
            <button
              onClick={handleGenerate}
              disabled={!file}
              className={`w-full text-white py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                mode === "free"
                  ? "bg-emerald-600 hover:bg-emerald-700"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {mode === "free" ? "⚡ Generează Free" : "✨ Generează cu AI"}
            </button>
          </div>
        )}

        {state === "processing" && (
          <ProcessingSpinner
            label={
              mode === "free"
                ? "Generare cu Groq... (~10-20s)"
                : undefined
            }
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
            <button onClick={reset} className="text-sm text-blue-600 underline">
              Încearcă din nou
            </button>
          </div>
        )}
      </div>

      <HistoryPanel refreshKey={historyKey} />
    </div>
  );
}
