"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import { postMockup } from "@/lib/api";

type State = "idle" | "processing" | "done" | "error";

export default function MockupPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    previewHtml: string;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  async function handleGenerate() {
    if (!file) return;
    setState("processing");
    setError("");
    try {
      const res = await postMockup(file);
      setResult({
        filename: res.filename,
        docxB64: res.docx_b64,
        previewHtml: res.html,
      });
      setState("done");
      setHistoryKey((k) => k + 1);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  function reset() {
    setFile(null);
    setResult(null);
    setState("idle");
    setError("");
  }

  return (
    <div className="flex h-screen">
      <div className="flex-1 p-6 overflow-auto">
        <ToolCard
          icon="🎨"
          title="Mockup Ecran"
          description="Excel Charisma (.xlsx) → Word + HTML mockup"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <UploadZone accept=".xlsx" label=".xlsx" onFile={setFile} />
            <button
              onClick={handleGenerate}
              disabled={!file}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Generează Mockup
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
            resetLabel="+ Generează alt mockup"
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
