"use client";
import type { ScopCoreElement } from "@/lib/api";

export type ElementUI = ScopCoreElement & { id: string };

type Props = {
  el: ElementUI;
  plasari: { cheie: string; titlu: string }[];
  onActualizeaza: (id: string, patch: Partial<ElementUI>) => void;
  onSterge: (id: string) => void;
};

/** Un element suplimentar propus din documentul suplimentar (mod „capitol”) — titlu, text și
 * plasarea lui într-un modul CORE sau capitol propriu. Extras din pagină fără nicio schimbare
 * de comportament. */
export default function ElementCard({ el, plasari, onActualizeaza, onSterge }: Props) {
  return (
    <div className="border border-slate-200 rounded-lg p-3 flex flex-col gap-2">
      <div className="flex items-start gap-2">
        <input
          type="text"
          value={el.titlu}
          onChange={(e) => onActualizeaza(el.id, { titlu: e.target.value })}
          placeholder="Titlu"
          className="flex-1 border border-slate-300 rounded-lg px-2 py-1.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#18257f]"
        />
        <button
          onClick={() => onSterge(el.id)}
          className="shrink-0 text-xs text-slate-400 hover:text-red-600 px-2 py-1.5"
          title="Șterge acest element"
        >
          ✕ Șterge
        </button>
      </div>
      <textarea
        value={el.text}
        onChange={(e) => onActualizeaza(el.id, { text: e.target.value })}
        rows={3}
        placeholder="Text"
        className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
      />
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-xs font-semibold text-slate-500 shrink-0">Plasare:</label>
        <select
          value={el.plasare}
          onChange={(e) => onActualizeaza(el.id, { plasare: e.target.value })}
          className="border border-[#8a93cf] bg-[#eef0f8] text-[#131e66] rounded-lg px-2 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[#18257f]"
        >
          {plasari.map((p) => (
            <option key={p.cheie} value={p.cheie}>
              {p.titlu}
            </option>
          ))}
        </select>
        {el.fluxuri_legate.length > 0 && (
          <span className="text-[11px] text-slate-400">
            Fluxuri legate: {el.fluxuri_legate.join(", ")}
          </span>
        )}
      </div>
    </div>
  );
}
