import type { Faza } from "@/lib/generare";

/**
 * Același parcurs pe toate modulele: datele de intrare → generarea → rezultatul.
 * Primul și ultimul pas își iau numele de la modul („Transcript", „Minuta").
 */
export default function Etape({
  faza,
  intrare,
  rezultat,
}: {
  faza: Faza;
  intrare: string;
  rezultat: string;
}) {
  const curent = faza === "idle" ? 0 : faza === "done" ? 2 : 1;
  const pasi = [intrare, "Generare", rezultat];

  return (
    <ol className="flex items-center gap-2 mb-4 text-xs" aria-label="Etapele generării">
      {pasi.map((nume, i) => {
        const facut = i < curent;
        const activ = i === curent;
        const eroare = activ && faza === "error";
        return (
          <li key={nume} className="flex items-center gap-2">
            {i > 0 && <span className={`w-6 h-px ${facut || activ ? "bg-[#18257f]" : "bg-slate-300"}`} />}
            <span
              aria-current={activ ? "step" : undefined}
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${
                eroare
                  ? "bg-red-50 text-red-700 border border-red-200"
                  : activ
                  ? "bg-[#18257f] text-white"
                  : facut
                  ? "bg-[#eef0f8] text-[#18257f]"
                  : "bg-white text-slate-400 border border-slate-200"
              }`}
            >
              <span className="tabular-nums">{facut ? "✓" : eroare ? "!" : i + 1}</span>
              {nume}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
