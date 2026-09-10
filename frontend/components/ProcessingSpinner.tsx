"use client";
import { useEffect, useState } from "react";

function mmss(secunde: number): string {
  const m = Math.floor(secunde / 60);
  const s = secunde % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ProcessingSpinner({
  label,
  onCancel,
}: {
  label?: string;
  /** Oprește urmărirea din pagină. Generarea continuă pe server. */
  onCancel?: () => void;
} = {}) {
  const [secunde, setSecunde] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setSecunde((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="w-10 h-10 border-4 border-[#c7ccf0] border-t-[#18257f] rounded-full animate-spin" />
      <div className="text-center">
        <p className="text-sm text-slate-600">{label ?? "Se generează documentul..."}</p>
        {/* Cat a trecut conteaza: fara cifra pe ecran, doua minute de asteptare
            se simt ca zece si utilizatorul da refresh peste o generare vie. */}
        <p className="text-xs text-slate-400 mt-1 tabular-nums">{mmss(secunde)}</p>
      </div>
      {secunde >= 5 && (
        <p className="text-xs text-slate-400 text-center max-w-xs">
          Se pornește serverul, poate dura 10-15 secunde la prima utilizare din
          zi.
        </p>
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
