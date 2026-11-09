"use client";
import { useEffect, useRef, useState } from "react";
import { uploadSourceFile } from "@/lib/api";
import { isColdStartError, pollJob, type JobStatus } from "@/lib/poll";

/** Limita bucket-ului Supabase (plan free). */
export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

type Tool = Parameters<typeof uploadSourceFile>[1];

/** Semnalul intern pentru o generare la care utilizatorul a renunțat. */
class Anulat extends Error {}

/**
 * Urcă fișierul direct în storage și întoarce calea lui.
 *
 * Verifică limita de 50MB înainte să trimită ceva, iar dacă serverul dormea
 * (Render free adoarme după 15 minute), reîncearcă o dată după 5 secunde.
 */
export async function incarcaFisier(
  file: File,
  tool: Tool,
  anulat: () => boolean = () => false
): Promise<string> {
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error(
      `Fișierul „${file.name}" are ${(file.size / 1024 / 1024).toFixed(1)}MB — peste limita de 50MB ` +
        "a storage-ului. Reduceți dimensiunea (de ex. eliminați imaginile din document) și reîncercați."
    );
  }
  try {
    return (await uploadSourceFile(file, tool)).storage_path;
  } catch (err) {
    if (!isColdStartError(err instanceof Error ? err.message : "")) throw err;
    await new Promise((r) => setTimeout(r, 5000));
    if (anulat()) throw new Anulat();
    return (await uploadSourceFile(file, tool)).storage_path;
  }
}

/**
 * Când generarea se termină cu tabul în fundal, titlul tabului spune asta
 * („✓ Gata — Minută") până revii pe el. Dacă utilizatorul a permis
 * notificările, apare și o notificare a browserului.
 */
export function anuntaTerminarea(modul: string, reusit: boolean) {
  if (typeof document === "undefined" || document.visibilityState === "visible") return;
  const titlu = document.title;
  document.title = `${reusit ? "✓ Gata" : "✕ Eroare"} — ${modul}`;
  const revino = () => {
    if (document.visibilityState !== "visible") return;
    document.title = titlu;
    document.removeEventListener("visibilitychange", revino);
  };
  document.addEventListener("visibilitychange", revino);

  if ("Notification" in window && Notification.permission === "granted") {
    try {
      new Notification(reusit ? `${modul}: documentul e gata` : `${modul}: generarea a eșuat`, {
        body: reusit ? "Revino în tab ca să-l descarci." : "Deschide tabul ca să vezi motivul.",
        tag: "ai-tools-generare",
      });
    } catch {
      // unele browsere permit notificări doar din service worker — titlul tabului rămâne
    }
  }
}

export type Faza = "idle" | "processing" | "done" | "error";

export type Unelte = {
  /** Urcă un fișier în storage, cu verificarea limitei și reîncercarea la pornirea serverului. */
  incarca: (file: File, tool: Tool) => Promise<string>;
  /** Textul de lângă bara de progres, până când serverul începe să raporteze pași. */
  eticheta: (text: string) => void;
};

/**
 * Mecanica comună a paginilor care generează un document: încărcarea,
 * pornirea jobului, urmărirea lui, rezultatul sau eroarea, renunțarea.
 *
 * `start` urcă fișierele și pornește jobul, întorcând `job_id`; `citesteJob`
 * îl citește de pe server. Pagina rămâne doar cu formularul și cu rezultatul.
 */
export function useGenerare<J extends JobStatus>({
  modul,
  etichetaPas,
}: {
  /** Numele modulului, pentru titlul tabului la final. */
  modul: string;
  /** Pasul raportat de server, pe înțeles („gen:2/5" → „lotul 2 din 5"). */
  etichetaPas?: (step: string) => string;
}) {
  const [faza, setFaza] = useState<Faza>("idle");
  const [eroare, setEroare] = useState("");
  const [eticheta, setEticheta] = useState("");
  const [step, setStep] = useState<string | null>(null);
  const [rezultat, setRezultat] = useState<J | null>(null);
  // se schimbă după fiecare document nou, ca lista „Recent" să se reîncarce
  const [recentKey, setRecentKey] = useState(0);
  const anulatRef = useRef(false);

  // Pagina părăsită oprește urmărirea; jobul continuă pe server.
  useEffect(
    () => () => {
      anulatRef.current = true;
    },
    []
  );

  async function porneste(
    start: (u: Unelte) => Promise<string>,
    citesteJob: (jobId: string) => Promise<J>
  ) {
    anulatRef.current = false;
    const anulat = () => anulatRef.current;
    setFaza("processing");
    setEroare("");
    setStep(null);
    setEticheta("Se pregătește...");
    try {
      const jobId = await start({
        incarca: (file, tool) => incarcaFisier(file, tool, anulat),
        eticheta: setEticheta,
      });
      if (anulat()) return;
      const job = await pollJob(() => citesteJob(jobId), {
        cancelled: anulat,
        onStep: (s) => {
          setStep(s);
          setEticheta(etichetaPas ? etichetaPas(s) : "Se procesează...");
        },
      });
      if (!job) return;
      setRezultat(job);
      setFaza("done");
      setRecentKey((k) => k + 1);
      anuntaTerminarea(modul, true);
    } catch (err: unknown) {
      if (anulat() || err instanceof Anulat) return;
      setEroare(err instanceof Error ? err.message : "Eroare necunoscută");
      setFaza("error");
      anuntaTerminarea(modul, false);
    }
  }

  /** Înapoi la formular, pentru o generare nouă. */
  function reset() {
    anulatRef.current = true;
    setRezultat(null);
    setEroare("");
    setFaza("idle");
  }

  /** Oprește doar urmărirea din pagină — jobul rulează mai departe pe server. */
  function renunta() {
    anulatRef.current = true;
    setFaza("idle");
  }

  return { faza, eroare, eticheta, step, rezultat, recentKey, porneste, reset, renunta };
}
