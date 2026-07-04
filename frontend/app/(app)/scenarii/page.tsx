"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import EstimateCard from "@/components/EstimateCard";
import ScenariiPreviewTable from "@/components/ScenariiPreviewTable";
import {
  postScenariiEstimate,
  postScenariiGenerate,
  getScenariiJob,
  type EstimateResponse,
  type Scenariu,
} from "@/lib/api";

type State = "idle" | "estimating" | "ready" | "processing" | "done" | "error";

// Sincronizat cu experimental.proxyClientMaxBodySize din next.config.ts
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

function stepLabel(step: string): string {
  const m = step.match(/^module:(\d+)\/(\d+):(.*)$/);
  if (m) return `Analizez modulul ${m[1]} din ${m[2]}: ${m[3]}...`;
  if (step === "building") return "Generez documentul Excel...";
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

export default function ScenariPage() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [progressLabel, setProgressLabel] = useState("Se inițializează...");
  const [result, setResult] = useState<{
    filename: string;
    xlsxB64: string;
    scenarios: Scenariu[];
    aiUsed: boolean;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  async function handleEstimate() {
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(
        `Fișierul are ${(file.size / 1024 / 1024).toFixed(1)}MB — peste limita de 25MB. ` +
          "Reduceți dimensiunea (de ex. eliminați imaginile din document) și reîncercați."
      );
      setState("error");
      return;
    }
    setState("estimating");
    setError("");
    cancelledRef.current = false;
    try {
      let est: EstimateResponse;
      try {
        est = await postScenariiEstimate(file);
      } catch (initErr) {
        // Render free tier adoarme — retry automat dupa 5s
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          setProgressLabel("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          est = await postScenariiEstimate(file);
        } else {
          throw initErr;
        }
      }
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
    setProgressLabel(useAi ? "Pornesc generarea cu AI..." : "Generez scenariile...");
    setError("");
    cancelledRef.current = false;
    try {
      const { job_id } = await postScenariiGenerate(estimate.estimate_id, useAi);

      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        const job = await getScenariiJob(job_id);
        if (cancelledRef.current) return;

        if (job.step) setProgressLabel(stepLabel(job.step));

        if (job.status === "done") {
          setResult({
            filename: job.filename!,
            xlsxB64: job.xlsx_b64!,
            scenarios: job.scenarios ?? [],
            aiUsed: job.ai_used ?? false,
          });
          setState("done");
          setHistoryKey((k) => k + 1);
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error || "Eroare în generarea scenariilor");
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
          icon="🧪"
          title="Scenarii Testare"
          description="Specificație (.docx) → Excel cu scenarii QA generate cu AI"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <UploadZone accept=".docx" label=".docx" onFile={setFile} />
            <button
              onClick={handleEstimate}
              disabled={!file}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continuă → Estimare
            </button>
          </div>
        )}

        {state === "estimating" && <ProcessingSpinner label="Analizez specificația..." />}

        {state === "ready" && estimate && (
          <EstimateCard
            estimate={estimate}
            toolLabel="scenariile"
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
                Scenariile au fost generate fără AI — conțin structura capitolelor
                cu pași generici.
              </p>
            )}
            <ScenariiPreviewTable scenarios={result.scenarios} />
            <ResultPanel
              filename={result.filename}
              docxB64={result.xlsxB64}
              previewHtml=""
              onReset={reset}
              downloadLabel="↓ Descarcă .xlsx"
              resetLabel="+ Generează alte scenarii"
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
