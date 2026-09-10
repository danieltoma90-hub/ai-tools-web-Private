"use client";
import { useRef, useState } from "react";
import ToolCard from "@/components/ToolCard";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import HistoryPanel from "@/components/HistoryPanel";
import {
  uploadSourceFile,
  postTrainingGenerate,
  getTrainingJob,
  type TrainingSummary,
} from "@/lib/api";
import { isColdStartError, pollJob } from "@/lib/poll";

type State = "idle" | "processing" | "done" | "error";
type Tip = "core" | "productie";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const ORE_PE_ZI = 6;

function stepLabel(step: string): string {
  if (step === "catalog") return "Pregătesc programul standard...";
  if (step === "specificatie") return "Citesc specificația clientului...";
  if (step === "planificare") return "Distribui modulele pe zile...";
  if (step === "documente") return "Generez documentele...";
  return "Se procesează...";
}

function descarca(b64: string, filename: string) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes]));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function TrainingPage() {
  const [tip, setTip] = useState<Tip>("core");
  const [zile, setZile] = useState(3);
  const [client, setClient] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("Se inițializează...");
  const [result, setResult] = useState<{
    docxName: string;
    docxB64: string;
    xlsxName: string;
    xlsxB64: string;
    summary: TrainingSummary | null;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const cancelledRef = useRef(false);

  const specNecesara = tip === "productie";
  const potGenera = !specNecesara || file !== null;

  async function handleGenerate() {
    if (file && file.size > MAX_UPLOAD_BYTES) {
      setError(
        `Fișierul are ${(file.size / 1024 / 1024).toFixed(1)}MB — peste limita de 50MB.`
      );
      setState("error");
      return;
    }
    setState("processing");
    setProgress(file ? "Încarc specificația..." : "Generez programul standard...");
    setError("");
    cancelledRef.current = false;

    try {
      let storagePath: string | undefined;
      if (file) {
        try {
          ({ storage_path: storagePath } = await uploadSourceFile(file, "training"));
        } catch (initErr) {
          // Render free tier adoarme — retry automat după 5s
          const msg = initErr instanceof Error ? initErr.message : "";
          if (!isColdStartError(msg)) throw initErr;
          setProgress("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          ({ storage_path: storagePath } = await uploadSourceFile(file, "training"));
        }
        if (cancelledRef.current) return;
        setProgress("Pornesc generarea...");
      }

      const { job_id } = await postTrainingGenerate({ tip, zile, client, storagePath });

      const job = await pollJob(() => getTrainingJob(job_id), {
        cancelled: () => cancelledRef.current,
        onStep: (step) => setProgress(stepLabel(step)),
      });
      if (!job) return;

      setResult({
        docxName: job.filename!,
        docxB64: job.docx_b64!,
        xlsxName: job.xlsx_filename!,
        xlsxB64: job.xlsx_b64!,
        summary: job.summary ?? null,
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
          icon="🎓"
          title="Agenda Training"
          description="Program de școlarizare utilizatori → agendă Word + plan Excel cu participanți"
          tool="training"
        />

        {state === "idle" && (
          <div className="flex flex-col gap-4">
            {/* Tip training */}
            <div className="flex rounded-lg border border-slate-200 overflow-hidden w-fit">
              <button
                onClick={() => setTip("core")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  tip === "core"
                    ? "bg-[#18257f] text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                📘 CORE
              </button>
              <button
                onClick={() => setTip("productie")}
                className={`px-4 py-2 text-sm font-medium transition-colors border-l border-slate-200 ${
                  tip === "productie"
                    ? "bg-[#18257f] text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                🏭 Producție
              </button>
            </div>

            <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 leading-relaxed">
              {tip === "core"
                ? "Există un program standard Charisma CORE: General, Depozit, Achiziții, Vânzări, Financiar, Mijloace Fixe, Contabilitate. Fără specificație se generează standardul comprimat pe numărul de zile ales; cu specificație, peste standard se adaugă particularitățile clientului."
                : "Nu există un program standard de producție — fiecare implementare are alte entități tehnologice, alte rețete, alt mod de raportare. Agenda se construiește integral din specificația încărcată: intră doar ce scrie în document, nimic altceva."}
            </p>

            {/* Perioada + client */}
            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-4">
              <div>
                <label className="block text-sm font-semibold text-[#18257f] mb-1">
                  Perioada de training
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={zile}
                    onChange={(e) =>
                      setZile(Math.min(10, Math.max(1, Number(e.target.value) || 1)))
                    }
                    className="w-20 border border-slate-300 rounded-lg px-3 py-2 text-sm text-center font-semibold focus:outline-none focus:ring-2 focus:ring-[#18257f]"
                  />
                  <span className="text-sm text-slate-600">
                    {zile === 1 ? "zi" : "zile"} × {ORE_PE_ZI}h ={" "}
                    <strong className="text-[#18257f]">{zile * ORE_PE_ZI}h</strong> efectiv
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1.5">
                  Modulele se distribuie automat pe zilele alese, cu efortul ajustat
                  proporțional. Ce nu încape este raportat explicit.
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-[#18257f] mb-1">
                  Client <span className="font-normal text-slate-400">(opțional)</span>
                </label>
                <input
                  type="text"
                  value={client}
                  onChange={(e) => setClient(e.target.value)}
                  placeholder="Denumirea clientului, apare în antetul agendei"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
                />
              </div>
            </div>

            {/* Specificatie */}
            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-[#18257f]">
                Specificația clientului{" "}
                <span className="font-normal text-slate-400">
                  {specNecesara ? "(obligatorie)" : "(opțională)"}
                </span>
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                {specNecesara
                  ? "Din ea se ridică modulele, conținutul și efortul — inclusiv căile din meniu și detaliile clientului (entități tehnologice, gestiuni, procente de pierderi), acolo unde documentul le dă."
                  : "Dacă o încarci, particularitățile clientului se adaugă la programul standard, marcate distinct în agendă."}
              </p>
              <UploadZone accept=".docx" label=".docx" onFile={setFile} />
            </div>

            <button
              onClick={handleGenerate}
              disabled={!potGenera}
              className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Generează agenda
            </button>
            {!potGenera && (
              <p className="text-xs text-amber-700 -mt-2">
                Încarcă specificația de producție pentru a continua.
              </p>
            )}
          </div>
        )}

        {state === "processing" && (
          <ProcessingSpinner label={progress} onCancel={renuntaLaAsteptare} />
        )}

        {state === "done" && result && (
          <div className="flex flex-col gap-4">
            {result.summary && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-[#18257f]">
                      {result.summary.zile}
                    </p>
                    <p className="text-[11px] text-slate-500">zile</p>
                  </div>
                  <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-[#18257f]">
                      {String(result.summary.total_ore).replace(".", ",")}h
                    </p>
                    <p className="text-[11px] text-slate-500">efort total</p>
                  </div>
                  <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-[#18257f]">
                      {result.summary.module}
                    </p>
                    <p className="text-[11px] text-slate-500">module</p>
                  </div>
                  {result.summary.tip === "productie" ? (
                    <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                      <p className="text-xl font-bold text-[#18257f]">
                        {String(result.summary.ore_referinta ?? 0).replace(".", ",")}h
                      </p>
                      <p className="text-[11px] text-slate-500">
                        cerute de specificație
                      </p>
                    </div>
                  ) : (
                    <div
                      className={`border rounded-lg p-3 text-center ${
                        result.summary.particularitati > 0
                          ? "bg-[#fff9c4] border-amber-200"
                          : "bg-white border-[#e2e5f0]"
                      }`}
                    >
                      <p
                        className={`text-xl font-bold ${
                          result.summary.particularitati > 0
                            ? "text-amber-700"
                            : "text-slate-300"
                        }`}
                      >
                        {result.summary.particularitati}
                      </p>
                      <p className="text-[11px] text-slate-500">particularități client</p>
                    </div>
                  )}
                </div>

                {result.summary.tip === "productie" &&
                  result.summary.ore_referinta != null &&
                  Math.abs(result.summary.ore_referinta - result.summary.total_ore) >
                    0.01 && (
                    <p className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                      Specificația cere{" "}
                      <strong>
                        {String(result.summary.ore_referinta).replace(".", ",")}h
                      </strong>
                      , iar {result.summary.zile}{" "}
                      {result.summary.zile === 1 ? "zi oferă" : "zile oferă"}{" "}
                      <strong>
                        {String(result.summary.total_ore).replace(".", ",")}h
                      </strong>
                      . Conținutul a fost{" "}
                      {result.summary.ore_referinta > result.summary.total_ore
                        ? "comprimat"
                        : "lărgit"}{" "}
                      proporțional — ajustează durata dacă vrei alt ritm.
                    </p>
                  )}

                {result.summary.avertisment && (
                  <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    <strong>Agenda conține doar programul standard.</strong>{" "}
                    {result.summary.avertisment}
                  </p>
                )}

                {result.summary.excluse.length > 0 && (
                  <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                    <strong>Nu încape la această durată:</strong>{" "}
                    {result.summary.excluse.join(", ")}. Mărește numărul de zile
                    dacă modulele acestea sunt necesare.
                  </p>
                )}
              </>
            )}

            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
              <button
                onClick={() => descarca(result.docxB64, result.docxName)}
                className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66]"
              >
                ↓ Descarcă agenda (.docx)
              </button>
              <button
                onClick={() => descarca(result.xlsxB64, result.xlsxName)}
                className="w-full bg-white border border-[#18257f] text-[#18257f] py-2.5 rounded-lg text-sm font-semibold hover:bg-[#eef0f8]"
              >
                ↓ Descarcă planul cu participanți (.xlsx)
              </button>
              <button
                onClick={reset}
                className="text-sm text-[#18257f] underline mt-1"
              >
                + Generează altă agendă
              </button>
            </div>
          </div>
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

      <HistoryPanel tool="training" refreshKey={historyKey} />
    </div>
  );
}
