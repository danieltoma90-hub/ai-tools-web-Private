"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import EstimateCard from "@/components/EstimateCard";
import {
  uploadSourceFile,
  postMockupEstimate,
  postMockupGenerate,
  getMockupJob,
  type EstimateResponse,
} from "@/lib/api";

type State = "idle" | "uploading" | "estimating" | "ready" | "processing" | "done" | "error";

// Limita bucket-ului Supabase (plan free)
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

function stepLabel(step: string): string {
  if (step === "parsing") return "Analizez fișierul...";
  if (step === "ai") return "Îmbogățesc descrierile cu AI...";
  if (step === "building") return "Generez documentul Word...";
  return "Se procesează...";
}

function isColdStartError(msg: string): boolean {
  return (
    msg.includes("timp util") ||
    msg.includes("unreachable") ||
    msg.includes("502") ||
    msg.includes("504")
  );
}

export default function MockupPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [progressLabel, setProgressLabel] = useState("Se inițializează...");
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    html: string;
    aiUsed: boolean;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  async function handleEstimate() {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(
        `Fișierul are ${(file.size / 1024 / 1024).toFixed(1)}MB — peste limita de 50MB a storage-ului. ` +
          "Reduceți dimensiunea (de ex. eliminați imaginile din document) și reîncercați."
      );
      setState("error");
      return;
    }
    setState("uploading");
    setError("");
    cancelledRef.current = false;
    try {
      let uploaded: { storage_path: string };
      try {
        uploaded = await uploadSourceFile(file, "mockup");
      } catch (initErr) {
        // Render free tier adoarme — retry automat după 5s (sign-ul trece prin proxy)
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          uploaded = await uploadSourceFile(file, "mockup");
        } else {
          throw initErr;
        }
      }
      if (cancelledRef.current) return;

      setState("estimating");
      const est = await postMockupEstimate(uploaded.storage_path, file.name);
      if (cancelledRef.current) return;
      setEstimate(est);
      setState("ready");
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  async function handleGenerate(useAi: boolean) {
    if (!estimate) return;
    setState("processing");
    setProgressLabel(useAi ? "Pornesc generarea cu AI..." : "Generez documentația...");
    setError("");
    cancelledRef.current = false;
    try {
      const { job_id } = await postMockupGenerate(estimate.estimate_id, useAi);

      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        const job = await getMockupJob(job_id);
        if (cancelledRef.current) return;

        if (job.step) setProgressLabel(stepLabel(job.step));

        if (job.status === "done") {
          setResult({
            filename: job.filename!,
            docxB64: job.docx_b64!,
            html: job.html ?? "",
            aiUsed: job.ai_used ?? false,
          });
          setState("done");
          setHistoryKey((k) => k + 1);
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error || "Eroare în generarea mockup-ului");
        }
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
    setEstimate(null);
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
          description="Fișier Excel (.xlsx) sau Word (.docx) → HTML mockup"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <UploadZone accept=".xlsx,.docx" label=".xlsx sau .docx" onFile={setFile} />
            <button
              onClick={handleEstimate}
              disabled={!file}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continuă → Estimare
            </button>
          </div>
        )}

        {state === "uploading" && (
          <ProcessingSpinner label="Se încarcă fișierul... (fișierele mari pot dura ~1 minut)" />
        )}

        {state === "estimating" && <ProcessingSpinner label="Analizez fișierul..." />}

        {state === "ready" && estimate && (
          <EstimateCard
            estimate={estimate}
            toolLabel="documentația"
            onAi={() => handleGenerate(true)}
            onNoAi={() => handleGenerate(false)}
            onCancel={reset}
          />
        )}

        {state === "processing" && <ProcessingSpinner label={progressLabel} />}

        {state === "done" && result && (
          <div className="flex flex-col gap-4">
            {!result.aiUsed && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Documentația a fost generată fără AI — descrierile provin direct
                din fișierul sursă.
              </p>
            )}
            <ResultPanel
              filename={result.filename}
              docxB64={result.docxB64}
              previewHtml={result.html}
              onReset={reset}
              resetLabel="+ Generează alt mockup"
            />
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col gap-3">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
              {error.includes("expirat") && (
                <p className="mt-2 text-xs">
                  Serverul a fost repornit între timp — reîncarcă fișierul și reia.
                </p>
              )}
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
