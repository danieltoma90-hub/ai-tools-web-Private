"use client";
import { useState } from "react";
import UploadZone from "@/components/UploadZone";
import {
  uploadSourceFile,
  postScopCoreMinute,
  type MinutaPunct,
  type MinutaRaspuns,
} from "@/lib/api";
import { isColdStartError } from "@/lib/poll";

type State = "idle" | "processing" | "done" | "error";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

// Ordinea în care se citește raportul: întâi ce cere acțiune, la urmă ce e deja în regulă.
const ORDINE = [
  "de_scos",
  "de_adaugat",
  "de_rescris",
  "de_confirmat",
  "acoperit",
  "rezolvat",
] as const;

const CULORI: Record<string, string> = {
  de_scos: "border-red-200 bg-red-50",
  de_adaugat: "border-amber-200 bg-amber-50",
  de_rescris: "border-sky-200 bg-sky-50",
  de_confirmat: "border-violet-200 bg-violet-50",
  acoperit: "border-slate-200 bg-slate-50",
  rezolvat: "border-emerald-200 bg-emerald-50",
};

export default function MinuteModeForm() {
  // Fișierele stau în browser până la confruntare și se urcă abia atunci: storage-ul
  // e releu (obiectul dispare la prima citire), deci un fișier urcat la adăugare n-ar
  // mai exista la o a doua încercare, după o confruntare eșuată.
  const [minute, setMinute] = useState<File[]>([]);
  const [scop, setScop] = useState<File | null>(null);
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  const [rezultat, setRezultat] = useState<MinutaRaspuns | null>(null);
  const [arataTot, setArataTot] = useState(false);

  /** Urcă un fișier în storage, cu o reîncercare dacă serverul dormea (Render free tier). */
  async function incarca(file: File): Promise<string> {
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

  function adaugaMinuta(file: File) {
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(`„${file.name}” depășește 50 MB.`);
      return;
    }
    setError("");
    setMinute((m) => [...m, file]);
  }

  function alegeScop(file: File) {
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(`„${file.name}” depășește 50 MB.`);
      return;
    }
    setError("");
    setScop(file);
  }

  async function confrunta() {
    if (minute.length === 0) {
      setError("Încarcă cel puțin o minută.");
      return;
    }
    setState("processing");
    setError("");
    try {
      // Urcăm la fiecare confruntare: lista din pagină rămâne valabilă și după un eșec.
      const urcate = await Promise.all(minute.map((f) => incarca(f)));
      const scopUrcat = scop ? await incarca(scop) : undefined;
      const raspuns = await postScopCoreMinute({
        minute: minute.map((f, i) => ({ storage_path: urcate[i], filename: f.name })),
        scopStoragePath: scopUrcat,
        scopFilename: scop?.name,
      });
      setRezultat(raspuns);
      setState("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("error");
    }
  }

  const grupe = ORDINE.map((v) => ({
    verdict: v,
    puncte: (rezultat?.raport ?? []).filter((p) => p.verdict === v),
  })).filter((g) => g.puncte.length > 0);
  const deActiune = new Set(["de_scos", "de_adaugat", "de_rescris", "de_confirmat"]);

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Minutele ședințelor</h3>
        <p className="text-xs text-slate-500 mb-3">
          JSON-ul din care s-a construit minuta (sau FitGap-ul) ori minuta ca .docx. Poți
          încărca mai multe — ședințele aceluiași client se citesc împreună.
        </p>
        <UploadZone
          accept=".json,.docx"
          label="Trage minuta aici sau alege fișierul"
          onFile={adaugaMinuta}
        />
        {minute.length > 0 && (
          <ul className="mt-3 space-y-1">
            {minute.map((m, i) => (
              <li key={i} className="flex items-center justify-between text-xs text-slate-600">
                <span>📝 {m.name}</span>
                <button
                  onClick={() => setMinute((lista) => lista.filter((_, j) => j !== i))}
                  className="text-slate-400 hover:text-red-600"
                >
                  scoate
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-1">
          Documentul de scop <span className="font-normal text-slate-400">(opțional)</span>
        </h3>
        <p className="text-xs text-slate-500 mb-3">
          Cu el, răspunsul spune ce s-a cerut să se scoată și încă e în document, ce s-a discutat
          și lipsește, ce trebuie reformulat. Fără el, primești doar punctele discutate.
        </p>
        <UploadZone
          accept=".docx"
          label="Trage documentul de scop aici"
          onFile={alegeScop}
        />
        {scop && (
          <p className="mt-3 flex items-center justify-between text-xs text-slate-600">
            <span>📄 {scop.name}</span>
            <button onClick={() => setScop(null)} className="text-slate-400 hover:text-red-600">
              scoate
            </button>
          </p>
        )}
      </div>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <button
        onClick={confrunta}
        disabled={state === "processing" || minute.length === 0}
        className="rounded-lg bg-[#18257f] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-40"
      >
        {state === "processing" ? "Se citește…" : "Confruntă cu scopul"}
      </button>

      {rezultat && (
        <div className="space-y-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            {rezultat.sumar.puncte} puncte citite din minute · {rezultat.sumar.cu_semnal} cu
            semnal de excludere, promisiune sau modificare · {rezultat.sumar.neconfirmate}{" "}
            neconfirmate (deducție sau clarificare)
            {rezultat.raport.length === 0 && (
              <>
                {" "}
                · fără document de scop încărcat, deci fără confruntare
              </>
            )}
          </div>

          {grupe
            .filter((g) => arataTot || deActiune.has(g.verdict))
            .map((g) => (
              <section key={g.verdict}>
                <h4 className="mb-2 text-sm font-semibold text-slate-700">
                  {g.puncte[0].eticheta} — {g.puncte.length}
                </h4>
                <ul className="space-y-2">
                  {g.puncte.map((p, i) => (
                    <PunctCard key={i} punct={p} />
                  ))}
                </ul>
              </section>
            ))}

          {grupe.some((g) => !deActiune.has(g.verdict)) && (
            <button
              onClick={() => setArataTot((v) => !v)}
              className="text-xs text-slate-500 underline hover:text-slate-700"
            >
              {arataTot
                ? "ascunde ce e deja acoperit sau rezolvat"
                : "arată și ce e deja acoperit sau rezolvat"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function PunctCard({ punct }: { punct: MinutaPunct }) {
  return (
    <li className={`rounded-lg border px-3 py-2 ${CULORI[punct.verdict] ?? "border-slate-200"}`}>
      <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <span>
          {punct.sursa} / {punct.sectiune}
        </span>
        {punct.marcaje.map((m) => (
          <span key={m} className="rounded bg-white/70 px-1.5 py-0.5 font-medium">
            {m}
          </span>
        ))}
        {punct.incredere === "slaba" && <span>potrivire slabă</span>}
      </div>
      <p className="text-sm text-slate-800">{punct.text}</p>
      {punct.termeni.length > 0 && (
        <p className="mt-1 text-[11px] text-slate-500">
          termeni: {punct.termeni.join(", ")}
        </p>
      )}
      {punct.locuri.slice(0, 2).map((loc, i) => (
        <p key={i} className="mt-0.5 text-[11px] text-slate-500">
          în document: {loc}
        </p>
      ))}
    </li>
  );
}
