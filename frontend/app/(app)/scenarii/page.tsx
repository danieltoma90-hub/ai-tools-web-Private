"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import ResultPanel from "@/components/ResultPanel";
import HistoryPanel from "@/components/HistoryPanel";
import {
  uploadSourceFile,
  postScenariiEstimate,
  postScenariiGenerate,
  getScenariiJob,
  type EstimateResponse,
  type ScenariiSummary,
} from "@/lib/api";

type State = "idle" | "uploading" | "estimating" | "ready" | "processing" | "done" | "error";

// Limita bucket-ului Supabase (plan free)
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

function stepLabel(step: string): string {
  if (step === "parsing") return "Analizez specificația și cerințele specifice...";
  const m = step.match(/^gen:(\d+)\/(\d+)$/);
  if (m) return `Generez scenariile specifice — lotul ${m[1]} din ${m[2]}...`;
  if (step === "deps") return "Stabilesc dependențele și planul de execuție...";
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
    summary: ScenariiSummary | null;
    engine: string;
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
        uploaded = await uploadSourceFile(file, "scenarii");
      } catch (initErr) {
        // Render free tier adoarme — retry automat după 5s
        const msg = initErr instanceof Error ? initErr.message : "";
        if (isColdStartError(msg)) {
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          uploaded = await uploadSourceFile(file, "scenarii");
        } else {
          throw initErr;
        }
      }
      if (cancelledRef.current) return;

      setState("estimating");
      const est = await postScenariiEstimate(uploaded.storage_path, file.name);
      if (cancelledRef.current) return;
      setEstimate(est);
      setState("ready");
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  async function handleGenerate(engine: "claude" | "groq") {
    if (!estimate) return;
    setState("processing");
    setProgressLabel(
      engine === "claude" ? "Pornesc generarea cu Claude..." : "Pornesc generarea Free (Groq)..."
    );
    setError("");
    cancelledRef.current = false;
    try {
      const { job_id } = await postScenariiGenerate(estimate.estimate_id, engine);

      let pollFailures = 0;
      while (true) {
        await new Promise((r) => setTimeout(r, 2000));
        if (cancelledRef.current) return;

        let job;
        try {
          job = await getScenariiJob(job_id);
          pollFailures = 0;
        } catch (pollErr) {
          // Jobul continuă pe server — tolerăm până la 3 eșecuri consecutive de polling
          pollFailures += 1;
          if (pollFailures >= 3) throw pollErr;
          continue;
        }
        if (cancelledRef.current) return;

        if (job.step) setProgressLabel(stepLabel(job.step));

        if (job.status === "done") {
          setResult({
            filename: job.filename!,
            xlsxB64: job.xlsx_b64!,
            summary: job.summary ?? null,
            engine: job.engine ?? engine,
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
          description="Specificație (.docx) → Excel: catalog standard + cerințe specifice client"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
              Fișierul generat pornește de la catalogul standard (170 scenarii CORE validate),
              adaugă scenarii pentru „Cerințele specifice identificate în urma Analizei” (marcate galben)
              și listează la final ce s-a exclus față de formatul standard.
            </p>
            <UploadZone accept=".docx" label=".docx" onFile={setFile} />
            <button
              onClick={handleEstimate}
              disabled={!file}
              className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continuă → Estimare
            </button>
          </div>
        )}

        {state === "uploading" && (
          <ProcessingSpinner label="Se încarcă fișierul... (fișierele mari pot dura ~1 minut)" />
        )}

        {state === "estimating" && <ProcessingSpinner label="Analizez specificația..." />}

        {state === "ready" && estimate && (
          <div className="bg-white border border-[#e2e5f0] rounded-xl p-5 flex flex-col gap-4">
            <div>
              <h3 className="text-sm font-bold text-[#18257f] mb-1">Specificație analizată</h3>
              <p className="text-xs text-slate-500">
                {estimate.requirements ?? 0} cerințe specifice găsite în{" "}
                {estimate.modules ?? 1} module · catalogul standard se filtrează după capitolele
                specificației
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                onClick={() => handleGenerate("claude")}
                className="border border-[#18257f] bg-[#18257f] text-white rounded-lg p-3 text-left hover:bg-[#131e66] transition-colors"
              >
                <span className="block text-sm font-bold">✨ Generează cu Claude</span>
                <span className="block text-xs mt-1 text-[#d5d8f5]">
                  Calitate maximă · ~{estimate.est_minutes} min · folosește credite API
                </span>
              </button>
              <button
                onClick={() => handleGenerate("groq")}
                className="border border-emerald-600 bg-emerald-600 text-white rounded-lg p-3 text-left hover:bg-emerald-700 transition-colors"
              >
                <span className="block text-sm font-bold">⚡ Generează Free (Groq)</span>
                <span className="block text-xs mt-1 text-emerald-100">
                  Gratuit · ~{estimate.est_minutes_free ?? "?"} min · limite zilnice partajate
                </span>
              </button>
            </div>
            <button onClick={reset} className="text-xs text-slate-400 hover:underline w-fit">
              Anulează
            </button>
          </div>
        )}

        {state === "processing" && <ProcessingSpinner label={progressLabel} />}

        {state === "done" && result && (
          <div className="flex flex-col gap-4">
            {result.summary && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                  <p className="text-xl font-bold text-[#18257f]">{result.summary.core_count}</p>
                  <p className="text-[11px] text-slate-500">scenarii standard incluse</p>
                </div>
                <div className="bg-[#fff9c4] border border-amber-200 rounded-lg p-3 text-center">
                  <p className="text-xl font-bold text-amber-700">{result.summary.specific_count}</p>
                  <p className="text-[11px] text-amber-700">
                    specifice client (din {result.summary.requirements} cerințe)
                  </p>
                </div>
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                  <p className="text-xl font-bold text-red-600">{result.summary.excluded_count}</p>
                  <p className="text-[11px] text-red-600">excluse vs standard</p>
                </div>
                <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                  <p className="text-xl font-bold text-[#18257f]">
                    {result.engine === "claude" ? "✨" : "⚡"}
                  </p>
                  <p className="text-[11px] text-slate-500">
                    {result.engine === "claude" ? "Claude" : "Groq (free)"}
                  </p>
                </div>
              </div>
            )}
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
            <button onClick={reset} className="text-sm text-[#18257f] underline">
              Încearcă din nou
            </button>
          </div>
        )}
      </div>

      <HistoryPanel refreshKey={historyKey} />
    </div>
  );
}
