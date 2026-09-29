"use client";
import { useRef, useState } from "react";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import {
  uploadSourceFile,
  postScopCorePropune,
  postScopCoreGenereaza,
  getScopCoreJob,
  type ScopCoreElement,
  type ScopCoreDelimitare,
  type ScopCoreSummary,
} from "@/lib/api";
import { isColdStartError, pollJob } from "@/lib/poll";
import ElementCard, { type ElementUI } from "./ElementCard";
import { SECTIUNI_CORE } from "./sectiuniCore";

type State = "idle" | "processing" | "done" | "error";
type AnalizaState = "none" | "loading" | "done" | "error";
type DelimitareUI = ScopCoreDelimitare & { id: string };

// Limita bucket-ului Supabase (plan free)
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

// Cele zece chei de secțiune CORE, plus "propriu" — singurele valori valide pentru `plasare`.
const PLASARI: { cheie: string; titlu: string }[] = [
  ...SECTIUNI_CORE,
  { cheie: "propriu", titlu: "Capitol propriu" },
];

function stepLabel(step: string): string {
  if (step === "parsing") return "Pregătesc secțiunile standard...";
  if (step === "building") return "Generez capitolul CORE...";
  if (step === "inserare") return "Inserez capitolul în documentul gazdă și renumerotez capitolele...";
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

function mesajFisierMarePrea(file: File): string {
  return `Fișierul are ${(file.size / 1024 / 1024).toFixed(1)}MB — peste limita de 50MB a storage-ului.`;
}

/**
 * Modul „Doar capitolul CORE, pentru inserare” — comportamentul original al ecranului, extras
 * neschimbat din pagină ca să poată sta alături de modul „document” fără să crească un singur
 * fișier peste orice limită de lizibilitate. Nicio logică de-aici nu s-a modificat.
 */
export default function CapitolModeForm({ onGenerated }: { onGenerated: () => void }) {
  const [client, setClient] = useState("");
  const [gazdaFile, setGazdaFile] = useState<File | null>(null);
  const [suplimentFile, setSuplimentFile] = useState<File | null>(null);
  const [analiza, setAnaliza] = useState<AnalizaState>("none");
  const [analizaError, setAnalizaError] = useState("");
  const [elemente, setElemente] = useState<ElementUI[]>([]);
  const [delimitari, setDelimitari] = useState<DelimitareUI[]>([]);
  const [insereaza, setInsereaza] = useState(false);
  const [curataAntetSubsol, setCurataAntetSubsol] = useState(false);

  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("Se inițializează...");
  const [step, setStep] = useState<string | null>(null);
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    gazdaFilename: string | null;
    gazdaB64: string | null;
    summary: ScopCoreSummary | null;
    cuprinsAvertisment: string | null;
  } | null>(null);
  const cancelledRef = useRef(false);
  const idRef = useRef(0);

  function idNou(): string {
    idRef.current += 1;
    return `el-${idRef.current}`;
  }

  /** Urcă un fișier direct în storage, cu o reîncercare dacă serverul dormea. */
  async function incarcaFisier(file: File): Promise<string> {
    try {
      const { storage_path } = await uploadSourceFile(file, "scop-core");
      return storage_path;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (!isColdStartError(msg)) throw err;
      await new Promise((r) => setTimeout(r, 5000));
      const { storage_path } = await uploadSourceFile(file, "scop-core");
      return storage_path;
    }
  }

  /** Urcă documentul suplimentar și cere segmentarea lui — pornește automat la alegerea fișierului. */
  async function analizeazaSupliment(file: File) {
    if (file.size > MAX_UPLOAD_BYTES) {
      setSuplimentFile(file);
      setAnalizaError(mesajFisierMarePrea(file));
      setAnaliza("error");
      return;
    }
    setSuplimentFile(file);
    setElemente([]);
    setAnalizaError("");
    setAnaliza("loading");
    try {
      const storagePath = await incarcaFisier(file);
      const { elemente: propuse } = await postScopCorePropune(storagePath, file.name);
      setElemente(propuse.map((el) => ({ ...el, id: idNou() })));
      setAnaliza("done");
    } catch (err) {
      setAnalizaError(err instanceof Error ? err.message : "Eroare necunoscută");
      setAnaliza("error");
    }
  }

  function stergeSupliment() {
    setSuplimentFile(null);
    setElemente([]);
    setAnaliza("none");
    setAnalizaError("");
  }

  function actualizeazaElement(id: string, patch: Partial<ElementUI>) {
    setElemente((els) => els.map((el) => (el.id === id ? { ...el, ...patch } : el)));
  }

  function stergeElement(id: string) {
    setElemente((els) => els.filter((el) => el.id !== id));
  }

  function adaugaDelimitare() {
    setDelimitari((ds) => [...ds, { id: idNou(), element: "", precizare: "" }]);
  }

  function actualizeazaDelimitare(id: string, patch: Partial<DelimitareUI>) {
    setDelimitari((ds) => ds.map((d) => (d.id === id ? { ...d, ...patch } : d)));
  }

  function stergeDelimitare(id: string) {
    setDelimitari((ds) => ds.filter((d) => d.id !== id));
  }

  const potGenera = gazdaFile !== null && analiza !== "loading";

  async function handleGenerate() {
    if (!gazdaFile) return;
    if (gazdaFile.size > MAX_UPLOAD_BYTES) {
      setError(mesajFisierMarePrea(gazdaFile));
      setState("error");
      return;
    }
    setState("processing");
    setProgress("Încarc documentul gazdă...");
    setStep(null);
    setError("");
    cancelledRef.current = false;

    try {
      let gazdaStoragePath: string;
      try {
        gazdaStoragePath = await incarcaFisier(gazdaFile);
      } catch (initErr) {
        // Render free tier adoarme — retry automat după 5s
        const msg = initErr instanceof Error ? initErr.message : "";
        if (!isColdStartError(msg)) throw initErr;
        setProgress("Server pornit, se retransmite automat...");
        await new Promise((r) => setTimeout(r, 5000));
        if (cancelledRef.current) return;
        gazdaStoragePath = await incarcaFisier(gazdaFile);
      }
      if (cancelledRef.current) return;
      setProgress("Pornesc generarea...");

      const payload: ScopCoreElement[] = elemente.map(({ titlu, text, plasare, fluxuri_legate }) => ({
        titlu,
        text,
        plasare,
        fluxuri_legate,
      }));
      const delimitariPayload: ScopCoreDelimitare[] = delimitari
        .map(({ element, precizare }) => ({ element: element.trim(), precizare: precizare.trim() }))
        .filter((d) => d.element && d.precizare);

      const { job_id } = await postScopCoreGenereaza({
        gazdaStoragePath,
        gazdaFilename: gazdaFile.name,
        client,
        elemente: payload,
        delimitari: delimitariPayload,
        insereaza,
        curataAntetSubsol,
      });

      const job = await pollJob(() => getScopCoreJob(job_id), {
        cancelled: () => cancelledRef.current,
        onStep: (s) => {
          setStep(s);
          setProgress(stepLabel(s));
        },
      });
      if (!job) return;

      setResult({
        filename: job.filename!,
        docxB64: job.docx_b64!,
        gazdaFilename: job.gazda_filename ?? null,
        gazdaB64: job.gazda_b64 ?? null,
        summary: (job.summary as ScopCoreSummary) ?? null,
        cuprinsAvertisment: job.cuprins_avertisment ?? null,
      });
      setState("done");
      onGenerated();
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  function reset() {
    cancelledRef.current = true;
    setClient("");
    setGazdaFile(null);
    stergeSupliment();
    setDelimitari([]);
    setInsereaza(false);
    setCurataAntetSubsol(false);
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
    <>
      {state === "idle" && (
        <div className="flex flex-col gap-4">
          <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-4">
            <div>
              <label className="block text-sm font-semibold text-[#18257f] mb-1">
                Nume client <span className="font-normal text-slate-400">(opțional)</span>
              </label>
              <input
                type="text"
                value={client}
                onChange={(e) => setClient(e.target.value)}
                placeholder="Denumirea clientului, apare în titlul capitolului"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
              />
            </div>
          </div>

          <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-[#18257f]">
              Document gazdă <span className="font-normal text-slate-400">(obligatoriu)</span>
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Documentul de scop existent al clientului (ex. Producție). Din el se clonează
              stilurile capitolului nou și, dacă alegi să inserezi, tot în el se adaugă capitolul
              CORE.
            </p>
            <UploadZone accept=".docx" label="documentul gazdă (.docx)" onFile={setGazdaFile} />

            <label className="flex items-start gap-2.5 pt-1 cursor-pointer">
              <input
                type="checkbox"
                checked={curataAntetSubsol}
                onChange={(e) => setCurataAntetSubsol(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-[#18257f]"
              />
              <span className="text-xs text-slate-600 leading-relaxed">
                <span className="font-semibold text-[#18257f]">
                  Curăță antetul și subsolul moștenite din gazdă
                </span>
                <span className="block text-slate-500 mt-0.5">
                  Bifează dacă documentul gazdă e doar un șablon de stil, de la alt client —
                  altfel antetul/subsolul lui (care poate numi acel client) ajunge neschimbat
                  în documentul generat. Nebifat implicit: cazul obișnuit e același client.
                </span>
              </span>
            </label>
          </div>

          <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-[#18257f]">
              Document suplimentar <span className="font-normal text-slate-400">(opțional)</span>
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Ce primește clientul peste standardul CORE. Se analizează automat la încărcare, iar
              elementele propuse apar mai jos, gata de corectat.
            </p>

            {analiza === "none" && (
              <UploadZone
                accept=".docx"
                label="documentul suplimentar (.docx)"
                onFile={analizeazaSupliment}
              />
            )}

            {analiza !== "none" && suplimentFile && (
              <div className="flex items-center justify-between gap-3 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                <span className="text-xs font-medium text-[#131e66] truncate">
                  {suplimentFile.name}
                </span>
                <button
                  onClick={stergeSupliment}
                  className="text-xs text-slate-400 hover:text-red-600 shrink-0"
                >
                  ✕ Elimină
                </button>
              </div>
            )}

            {analiza === "loading" && (
              <p className="text-xs text-slate-500 flex items-center gap-2 mt-1">
                <span className="w-3.5 h-3.5 border-2 border-[#c7ccf0] border-t-[#18257f] rounded-full animate-spin inline-block shrink-0" />
                Se analizează documentul suplimentar...
              </p>
            )}

            {analiza === "error" && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 flex flex-col gap-2">
                <p>{analizaError}</p>
                <div className="flex gap-3">
                  <button
                    onClick={() => suplimentFile && analizeazaSupliment(suplimentFile)}
                    className="text-[#18257f] underline font-medium"
                  >
                    Reîncearcă
                  </button>
                  <button onClick={stergeSupliment} className="text-slate-500 underline">
                    Continuă fără elemente suplimentare
                  </button>
                </div>
              </div>
            )}
          </div>

          {analiza === "done" && (
            <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
              <div>
                <h3 className="text-sm font-bold text-[#18257f]">
                  Elemente propuse ({elemente.length})
                </h3>
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-1.5 leading-relaxed">
                  Modelul care propune plasarea e mic și inconsecvent — poate plasa altfel aceleași
                  elemente la o rulare următoare. Verifică <strong>plasarea</strong> fiecărui element
                  înainte de generare: o plasare greșită înseamnă o cerință sub modulul greșit, într-o
                  ofertă comercială.
                </p>
              </div>

              {elemente.length === 0 && (
                <p className="text-xs text-slate-400">
                  Nicio listă de elemente — documentul suplimentar nu a produs niciunul, sau le-ai
                  șters pe toate. Poți genera în continuare doar cu standardul CORE.
                </p>
              )}

              {elemente.map((el) => (
                <ElementCard
                  key={el.id}
                  el={el}
                  plasari={PLASARI}
                  onActualizeaza={actualizeazaElement}
                  onSterge={stergeElement}
                />
              ))}
            </div>
          )}

          <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
            <div>
              <h3 className="text-sm font-semibold text-[#18257f]">
                Delimitări de scop <span className="font-normal text-slate-400">(opțional)</span>
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed mt-1">
                Ce anume NU intră în scopul ofertat — apare ca ultimul sub-capitol, sub formă de
                tabel. Fără nicio intrare, sub-capitolul nu apare deloc în document.
              </p>
            </div>

            {delimitari.map((d) => (
              <div key={d.id} className="border border-slate-200 rounded-lg p-3 flex flex-col gap-2">
                <div className="flex items-start gap-2">
                  <input
                    type="text"
                    value={d.element}
                    onChange={(e) => actualizeazaDelimitare(d.id, { element: e.target.value })}
                    placeholder="Element (ex. Migrarea datelor istorice)"
                    className="flex-1 border border-slate-300 rounded-lg px-2 py-1.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#18257f]"
                  />
                  <button
                    onClick={() => stergeDelimitare(d.id)}
                    className="shrink-0 text-xs text-slate-400 hover:text-red-600 px-2 py-1.5"
                    title="Șterge această delimitare"
                  >
                    ✕ Șterge
                  </button>
                </div>
                <textarea
                  value={d.precizare}
                  onChange={(e) => actualizeazaDelimitare(d.id, { precizare: e.target.value })}
                  rows={2}
                  placeholder="Precizare (ex. Nu face obiectul acestui scop; se estimează separat.)"
                  className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
                />
              </div>
            ))}

            <button
              onClick={adaugaDelimitare}
              className="self-start text-xs font-semibold text-[#18257f] underline"
            >
              + Adaugă o delimitare
            </button>
          </div>

          <label className="flex items-start gap-2.5 bg-white border border-[#e2e5f0] rounded-xl p-4 cursor-pointer">
            <input
              type="checkbox"
              checked={insereaza}
              onChange={(e) => setInsereaza(e.target.checked)}
              className="mt-0.5 w-4 h-4 accent-[#18257f]"
            />
            <span className="text-sm text-slate-700">
              <span className="font-semibold text-[#18257f]">
                Inserează în documentul gazdă și renumerotează capitolele
              </span>
              <span className="block text-xs text-slate-500 mt-0.5">
                Fără bifă primești doar capitolul CORE, separat, ca fișier nou.
              </span>
            </span>
          </label>

          <button
            onClick={handleGenerate}
            disabled={!potGenera}
            className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Generează
          </button>
          {!gazdaFile && (
            <p className="text-xs text-amber-700 -mt-2">
              Încarcă documentul gazdă pentru a continua.
            </p>
          )}
        </div>
      )}

      {state === "processing" && (
        <ProcessingSpinner label={progress} onCancel={renuntaLaAsteptare} step={step} />
      )}

      {state === "done" && result && (
        <div className="flex flex-col gap-4">
          {result.summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-[#18257f]">{result.summary.sectiuni}</p>
                <p className="text-[11px] text-slate-500">secțiuni standard</p>
              </div>
              <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-[#18257f]">{result.summary.fluxuri}</p>
                <p className="text-[11px] text-slate-500">fluxuri</p>
              </div>
              <div
                className={`border rounded-lg p-3 text-center ${
                  result.summary.elemente_plasate > 0
                    ? "bg-[#fff9c4] border-amber-200"
                    : "bg-white border-[#e2e5f0]"
                }`}
              >
                <p
                  className={`text-xl font-bold ${
                    result.summary.elemente_plasate > 0 ? "text-amber-700" : "text-slate-300"
                  }`}
                >
                  {result.summary.elemente_plasate}
                </p>
                <p className="text-[11px] text-slate-500">
                  elemente suplimentare ({result.summary.elemente_pe_sectiune} pe secțiune,{" "}
                  {result.summary.elemente_proprii} proprii)
                </p>
              </div>
              <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-[#18257f]">
                  {result.summary.gazda_inserata ? "✅" : "—"}
                </p>
                <p className="text-[11px] text-slate-500">
                  {result.summary.gazda_inserata ? "inserat în gazdă" : "fără inserare"}
                </p>
              </div>
            </div>
          )}

          {!!result.summary?.elemente_respinse && (
            <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {result.summary.elemente_respinse} element(e) suplimentar(e) nu au putut fi folosite
              (titlu sau text lipsă) și au fost ignorate.
            </p>
          )}

          {!!result.summary?.avertisment && (
            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              {result.summary.avertisment}
            </p>
          )}

          {result.cuprinsAvertisment && (
            <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 text-sm text-amber-900 flex gap-3">
              <span className="text-xl shrink-0">⚠️</span>
              <p className="leading-relaxed">{result.cuprinsAvertisment}</p>
            </div>
          )}

          {!!result.summary?.antet_subsol_avertisment && (
            <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 text-sm text-amber-900 flex gap-3">
              <span className="text-xl shrink-0">⚠️</span>
              <p className="leading-relaxed">{result.summary.antet_subsol_avertisment}</p>
            </div>
          )}

          <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
            <button
              onClick={() => descarca(result.docxB64, result.filename)}
              className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66]"
            >
              ↓ Descarcă capitolul CORE (.docx)
            </button>
            {result.gazdaB64 && result.gazdaFilename && (
              <button
                onClick={() => descarca(result.gazdaB64!, result.gazdaFilename!)}
                className="w-full bg-white border border-[#18257f] text-[#18257f] py-2.5 rounded-lg text-sm font-semibold hover:bg-[#eef0f8]"
              >
                ↓ Descarcă documentul gazdă cu capitolul inserat (.docx)
              </button>
            )}
            <button onClick={reset} className="text-sm text-[#18257f] underline mt-1">
              + Generează alt capitol
            </button>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="flex flex-col gap-3">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            {error}
          </div>
          <button
            onClick={() => {
              setState("idle");
              setError("");
            }}
            className="text-sm text-[#18257f] underline"
          >
            Încearcă din nou
          </button>
        </div>
      )}
    </>
  );
}
