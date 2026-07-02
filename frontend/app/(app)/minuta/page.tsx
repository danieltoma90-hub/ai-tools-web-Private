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
  const [freeLabel, setFreeLabel] = useState("Se inițializează...");
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
    setFreeLabel("Se inițializează...");
    setError("");
    cancelledRef.current = false;

    try {
      let job_id: string;
      try {
        ({ job_id } = await postMinutaFree(file));
      } catch (initErr) {
        // Render free tier se adoarme dupa inactivitate — retry automat dupa 5s
        const msg = initErr instanceof Error ? initErr.message : "";
        if (msg.includes("timp util") || msg.includes("unreachable") || msg.includes("502") || msg.includes("504")) {
          setFreeLabel("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          ({ job_id } = await postMinutaFree(file));
        } else {
          throw initErr;
        }
      }

      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        const job = await pollMinutaJob(job_id);
        if (cancelledRef.current) return;

        if (job.step) {
          setFreeLabel(freeStepLabel(job.step));
        }

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
          throw new Error(job.error || "Eroare în procesarea minutei Free");
        }
      }
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
                ⚡ Free (Llama)
              </button>
            </div>

            {mode === "free" && (
              <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                Versiunea Free procesează întregul transcript, bucată cu bucată, pe API-ul gratuit Groq. O întâlnire de 1 oră durează ~10-15 minute (limitele gratuite permit 1 apel/minut) — progresul e afișat pe părți. Limita zilnică: ~2 întâlniri lungi.
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
            label={mode === "free" ? freeLabel : undefined}
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
