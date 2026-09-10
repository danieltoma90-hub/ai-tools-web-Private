"use client";
import { useEffect, useRef, useState } from "react";
import { citatPentru } from "@/lib/citate";
import { evenimenteleZilei, type EvenimentIstoric } from "@/lib/istorie";
import { calculeazaProgres, type Etapa } from "@/lib/progres";

const SCHIMBA_CITATUL_LA_S = 14;

function mmss(secunde: number): string {
  const m = Math.floor(secunde / 60);
  const s = secunde % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ProcessingSpinner({
  label,
  onCancel,
  etape,
  step = null,
}: {
  label?: string;
  /** Oprește urmărirea din pagină. Generarea continuă pe server. */
  onCancel?: () => void;
  /** Etapele jobului; fără ele se afișează doar cronometrul. */
  etape?: Etapa[];
  /** Pasul brut raportat de server ("chunk:3/8"). */
  step?: string | null;
} = {}) {
  const [secunde, setSecunde] = useState(0);
  const [secundeInEtapa, setSecundeInEtapa] = useState(0);
  const [istorie, setIstorie] = useState<EvenimentIstoric[]>([]);
  const samanta = useRef(Math.floor(Math.random() * 1000));

  useEffect(() => {
    const t = setInterval(() => {
      setSecunde((s) => s + 1);
      setSecundeInEtapa((s) => s + 1);
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Un pas nou de la server repornește mișcarea din interiorul etapei.
  useEffect(() => {
    setSecundeInEtapa(0);
  }, [step]);

  useEffect(() => {
    evenimenteleZilei().then(setIstorie).catch(() => {});
  }, []);

  const procent = etape
    ? Math.round(calculeazaProgres(etape, step, secundeInEtapa) * 100)
    : null;

  const citat = citatPentru(
    Math.floor(secunde / SCHIMBA_CITATUL_LA_S),
    samanta.current
  );
  const eveniment =
    istorie.length > 0
      ? istorie[
          (samanta.current + Math.floor(secunde / SCHIMBA_CITATUL_LA_S)) %
            istorie.length
        ]
      : null;

  return (
    <div className="flex flex-col items-center py-10 gap-5">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-5 h-5 border-2 border-[#c7ccf0] border-t-[#18257f] rounded-full animate-spin shrink-0" />
          <p className="text-sm text-slate-600 flex-1">
            {label ?? "Se generează documentul..."}
          </p>
          <p className="text-xs text-slate-400 tabular-nums">{mmss(secunde)}</p>
        </div>

        {procent !== null && (
          <>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-[#18257f] rounded-full transition-[width] duration-1000 ease-linear"
                style={{ width: `${procent}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-400 mt-1 text-right tabular-nums">
              {procent}%
            </p>
          </>
        )}

        {secunde >= 5 && secunde < 20 && (
          <p className="text-xs text-slate-400 text-center mt-2">
            Se pornește serverul, poate dura 10-15 secunde la prima utilizare din zi.
          </p>
        )}
      </div>

      {/* Așteptarea trece mai ușor cu ceva de citit — și rămâi cu ceva după. */}
      <div className="w-full max-w-md bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 min-h-[92px] flex flex-col justify-center">
        <p className="text-[13px] text-slate-600 italic leading-relaxed">
          „{citat.text}"
        </p>
        <p className="text-[11px] text-slate-400 mt-1.5">
          — {citat.atribuit ? "attributed to " : ""}
          {citat.autor}
        </p>
      </div>

      {eveniment && (
        <div className="w-full max-w-md px-4">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1">
            On this day · {eveniment.an}
          </p>
          <p className="text-[12px] text-slate-500 leading-relaxed">
            {eveniment.text}
          </p>
        </div>
      )}

      {onCancel && (
        <div className="text-center">
          <button
            onClick={onCancel}
            className="text-xs text-slate-400 hover:text-slate-600 underline"
          >
            Nu mai aștept
          </button>
          <p className="text-[10px] text-slate-300 mt-1 max-w-xs">
            Generarea continuă pe server, iar documentul apare în Repository.
          </p>
        </div>
      )}
    </div>
  );
}
