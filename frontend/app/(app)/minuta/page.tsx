"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import { postMinuta, pollMinutaJob } from "@/lib/api";

type State = "idle" | "processing" | "done" | "error";

export default function MinutaPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    previewHtml: string;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  async function handleGenerate() {
    if (!file) return;
    setState("processing");
    setError("");
    cancelledRef.current = false;

    try {
      const { job_id } = await postMinuta(file);

      // Polling la fiecare 2 secunde până la finalizare
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
        // status === "processing" → continuăm polling
      }
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
            <UploadZone
              accept=".vtt,.docx"
              label=".vtt sau .docx"
              onFile={setFile}
            />
            <button
              onClick={handleGenerate}
              disabled={!file}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Generează Minuta
            </button>
          </div>
        )}

        {state === "processing" && <ProcessingSpinner />}

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
